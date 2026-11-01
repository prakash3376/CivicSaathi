"""Polite, bounded downloads of official documents.

Certificates are always verified (against the operating system's trust store, so government
sites with incomplete chains still work). Redirects are followed by hand so that every hop is
checked against the official-domain rule *before* it is requested, the size limit is enforced
while streaming, and robots.txt is honoured.
"""

import hashlib
import logging
import ssl
import time
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx2
import truststore

from app.domain.documents import FetchedDocument, TlsInfo
from app.domain.errors import FetchError
from app.domain.sources import SourceSpec
from app.services.ingestion.verification import official_domain_reason

logger = logging.getLogger(__name__)

PRODUCT_TOKEN = "CivicSaathiBot"
USER_AGENT = f"{PRODUCT_TOKEN}/0.2 (policy explainer; downloads public official documents)"
MAX_REDIRECTS = 5
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_DEFAULT_MAX_BYTES = 25 * 1024 * 1024
# Python added the name in 3.12; the OpenSSL flag itself (0x4) works on every version we support.
_OP_LEGACY_SERVER_CONNECT: int = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)


class Fetcher:
    """Downloads the document behind a registry entry. Reusable; holds no connection state."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_bytes: int = _DEFAULT_MAX_BYTES,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._transport = transport  # tests inject a fake network here

    def fetch(self, spec: SourceSpec) -> FetchedDocument:
        """Download ``spec.url``. Raises ``FetchError`` for anything that should stop ingestion."""
        started = time.perf_counter()
        try:
            with self._client(legacy_tls=spec.legacy_tls) as client:
                robots = self._robots(client, spec.url)
                url, chain = spec.url, []
                for _ in range(MAX_REDIRECTS + 1):
                    with client.stream("GET", url) as response:
                        location = response.headers.get("location")
                        if response.status_code in _REDIRECT_STATUSES and location:
                            url = self._next_hop(url, location)
                            chain.append(url)
                            continue
                        return self._read(response, spec, url, chain, robots, started)
                raise FetchError("The server redirected too many times.", code="too_many_redirects")
        except httpx2.TimeoutException as error:
            raise FetchError("The server took too long to respond.", code="timeout") from error
        except httpx2.RequestError as error:
            raise _describe_network_error(error) from error

    def _client(self, *, legacy_tls: bool) -> httpx2.Client:
        verify: ssl.SSLContext | bool = True
        if self._transport is None:
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            if legacy_tls:
                context.options |= ssl.Options(_OP_LEGACY_SERVER_CONNECT)
            verify = context
        return httpx2.Client(
            verify=verify,
            transport=self._transport,
            timeout=httpx2.Timeout(self._timeout, connect=min(10.0, self._timeout)),
            follow_redirects=False,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.5",
                "Accept-Language": "en-IN,en;q=0.8,hi;q=0.5",
            },
        )

    @staticmethod
    def _next_hop(current: str, location: str) -> str:
        target = urljoin(current, location)
        if official_domain_reason(target) is None:
            raise FetchError(
                f"The server redirected to {target}, which is not an official domain.",
                code="redirect_off_domain",
            )
        return target

    @staticmethod
    def _robots(client: httpx2.Client, url: str) -> Literal["allowed", "absent"]:
        """Follow RFC 9309: a missing robots.txt allows everything, a broken one blocks us."""
        parts = urlsplit(url)
        response = client.get(f"{parts.scheme}://{parts.netloc}/robots.txt")
        if response.status_code >= 500:
            raise FetchError(
                f"{parts.netloc}'s robots.txt could not be read (server error). Not downloading; "
                "try again later.",
                code="robots_unreachable",
            )
        content_type = response.headers.get("content-type", "").lower()
        # Some sites answer every unknown path with their home page; that is not a robots file.
        if response.status_code != 200 or "text/plain" not in content_type:
            return "absent"
        rules = RobotFileParser()
        rules.parse(response.text.splitlines())
        if not rules.can_fetch(PRODUCT_TOKEN, url):
            raise FetchError(
                f"{parts.netloc}'s robots.txt does not allow automated downloads of this page.",
                code="robots_disallowed",
            )
        return "allowed"

    def _read(
        self,
        response: httpx2.Response,
        spec: SourceSpec,
        url: str,
        chain: list[str],
        robots: Literal["allowed", "absent"],
        started: float,
    ) -> FetchedDocument:
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > self._max_bytes:
            raise _too_large(self._max_bytes)
        body = bytearray()
        for piece in response.iter_bytes():
            body.extend(piece)
            if len(body) > self._max_bytes:
                raise _too_large(self._max_bytes)
        return FetchedDocument(
            url=spec.url,
            final_url=url,
            redirect_chain=chain,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            last_modified=response.headers.get("last-modified"),
            robots=robots,
            tls=_tls_info(response, legacy=spec.legacy_tls),
            size_bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            fetched_at=datetime.now(UTC),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            content=bytes(body),
        )


def _too_large(max_bytes: int) -> FetchError:
    return FetchError(
        f"The document is larger than the {max_bytes // (1024 * 1024)} MB limit.", code="too_large"
    )


def _describe_network_error(error: httpx2.RequestError) -> FetchError:
    detail = str(error)
    if "UNSAFE_LEGACY_RENEGOTIATION" in detail:
        return FetchError(
            "The server only supports legacy TLS renegotiation, which is refused by default. If "
            "you trust this official host, set legacy_tls = true on its registry entry.",
            code="tls_legacy_renegotiation",
        )
    if "CERTIFICATE" in detail.upper() or "SSL" in detail.upper():
        return FetchError(
            f"The server's TLS certificate could not be verified ({detail}). Not downloading.",
            code="tls_error",
        )
    return FetchError(f"Could not connect to the server ({detail}).", code="network_error")


def _tls_info(response: httpx2.Response, *, legacy: bool) -> TlsInfo | None:
    """Read what the handshake established; ``None`` if the transport exposes no TLS session."""
    stream: Any = response.extensions.get("network_stream")
    ssl_object: Any = stream.get_extra_info("ssl_object") if stream is not None else None
    if ssl_object is None:
        return None
    cert: dict[str, Any] = ssl_object.getpeercert() or {}
    issuer = _name(cert.get("issuer", ()))
    not_after = cert.get("notAfter")
    return TlsInfo(
        version=ssl_object.version() or "unknown",
        cipher=(ssl_object.cipher() or ("unknown",))[0],
        issuer=issuer.get("organizationName") or issuer.get("commonName"),
        subject_org=_name(cert.get("subject", ())).get("organizationName"),
        not_after=datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), UTC)
        if not_after
        else None,
        hostnames=[value for kind, value in cert.get("subjectAltName", ()) if kind == "DNS"],
        legacy_renegotiation=legacy,
    )


def _name(rdns: Any) -> dict[str, str]:
    """Flatten a certificate name, as ``ssl`` returns it, into ``{field: value}``."""
    return {key: value for rdn in rdns for key, value in rdn}
