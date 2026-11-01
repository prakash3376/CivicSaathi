"""Is this source what the registry says it is? Checks the URL, the download and the extracted text.

Every check ends in ``pass``, ``warn`` or ``fail``. A failure rejects the source. A warning keeps
it, but tells people what to double-check (an old document, a scan, a missing date). With neither,
the source is verified. The report is stored with the document and travels with every chunk, so
later stages can show a verification badge (SPEC feature 11).
"""

import ipaddress
import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlsplit

from app.domain.documents import (
    CheckStatus,
    FetchedDocument,
    ParsedDocument,
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.domain.sources import SourceSpec

# Hosts under these suffixes belong to the Government of India or the National Informatics Centre.
OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")
# Official hosts outside those suffixes, each with the evidence that it is official.
OFFICIAL_HOSTS: dict[str, str] = {
    "aicte-india.org": (
        "AICTE's own domain: AICTE's letterhead names it as the council's website and e-mail domain"
    ),
}

STALE_AFTER = timedelta(days=365)  # SPEC rule R4: warn about documents older than 12 months
CERTIFICATE_EXPIRY_WARNING = timedelta(days=14)
MIN_TEXT_CHARS = 200
_NOT_ALNUM = re.compile(r"[\W_]+")


def official_domain_reason(url: str) -> str | None:
    """Why this URL counts as an official source, or ``None`` if it does not.

    Strict on purpose: https only, the default port, no credentials, no IP addresses, no
    internationalised look-alike names, and the host must sit under a listed official domain.
    """
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return None
    if not host:
        return None
    host = host.rstrip(".")
    if not host.isascii() or any(label.startswith("xn--") for label in host.split(".")):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass  # not an IP address, which is what we want

    for suffix in OFFICIAL_SUFFIXES:
        if host.endswith(suffix):
            return f"a Government of India domain ({suffix})"
    for official, reason in OFFICIAL_HOSTS.items():
        if host == official or host.endswith(f".{official}"):
            return reason
    return None


def verify_url(spec: SourceSpec) -> list[VerificationCheck]:
    """Checks that need no download. A failure here means nothing is downloaded at all."""
    host = urlsplit(spec.url).hostname or spec.url
    reason = official_domain_reason(spec.url)
    if reason:
        return [_check("official_domain", "pass", f"{host} is {reason}.")]
    return [
        _check(
            "official_domain",
            "fail",
            f"{host} is not a recognised official domain (https on *.gov.in or *.nic.in, or a "
            "listed official host). Nothing was downloaded.",
        )
    ]


def verify_download(
    spec: SourceSpec, fetched: FetchedDocument, *, max_bytes: int, now: datetime
) -> list[VerificationCheck]:
    """Checks on what the server sent back."""
    return [
        _status_check(fetched),
        _redirect_check(fetched),
        _tls_check(fetched, now),
        _file_type_check(spec, fetched),
        _size_check(fetched, max_bytes),
        _robots_check(fetched),
    ]


def verify_content(
    spec: SourceSpec, parsed: ParsedDocument, now: datetime
) -> list[VerificationCheck]:
    """Checks on the text we extracted."""
    text = parsed.text
    if len(text) < MIN_TEXT_CHARS:
        return [
            _check(
                "text_extracted",
                "fail",
                f"Only {len(text)} characters of text could be extracted. The file may be a scan "
                "without a text layer; OCR is not available yet.",
            )
        ]
    checks = [
        _check(
            "text_extracted", "pass", f"{len(text):,} characters in {len(parsed.blocks)} blocks."
        ),
        _phrases_check(spec, text),
    ]
    if spec.expected_facts:
        checks.append(_facts_check(spec, text))
    checks.append(_date_check(parsed, now.date()))
    checks.append(_extraction_check(parsed))
    return checks


def build_report(
    spec: SourceSpec, checks: list[VerificationCheck], now: datetime
) -> VerificationReport:
    statuses = {check.status for check in checks}
    status: VerificationStatus
    if "fail" in statuses:
        status = "rejected"
    elif "warn" in statuses:
        status = "verified_with_warnings"
    else:
        status = "verified"
    return VerificationReport(
        source_id=spec.id, url=spec.url, status=status, checks=checks, verified_at=now
    )


def failed(checks: list[VerificationCheck]) -> bool:
    return any(check.status == "fail" for check in checks)


def _check(name: str, status: CheckStatus, detail: str) -> VerificationCheck:
    return VerificationCheck(name=name, status=status, detail=detail)


def _status_check(fetched: FetchedDocument) -> VerificationCheck:
    if fetched.status_code == 200:
        return _check("http_status", "pass", "The server answered 200 OK.")
    return _check(
        "http_status", "fail", f"The server answered HTTP {fetched.status_code}, not 200."
    )


def _redirect_check(fetched: FetchedDocument) -> VerificationCheck:
    hops = fetched.redirect_chain
    if not hops:
        return _check("redirects", "pass", "No redirects.")
    off_domain = [hop for hop in hops if official_domain_reason(hop) is None]
    if off_domain:
        return _check(
            "redirects", "fail", f"Redirected to a non-official address: {off_domain[0]}."
        )
    return _check("redirects", "pass", f"{len(hops)} redirect(s), all within official domains.")


def _tls_check(fetched: FetchedDocument, now: datetime) -> VerificationCheck:
    tls = fetched.tls
    if tls is None:
        return _check("tls", "warn", "TLS details were not available for this download.")

    summary = f"{tls.version}; certificate and hostname verified against the system trust store"
    if tls.issuer:
        summary += f", issued by {tls.issuer}"
    if tls.not_after:
        summary += f", valid until {tls.not_after:%Y-%m-%d}"
    summary += ". Revocation is not checked."

    concerns: list[str] = []
    if tls.not_after and tls.not_after - now < CERTIFICATE_EXPIRY_WARNING:
        concerns.append("the certificate expires within 14 days")
    if tls.legacy_renegotiation:
        concerns.append(
            "legacy TLS mode is enabled for this source because its server lacks secure "
            "renegotiation (RFC 5746); the certificate and hostname were still verified"
        )
    if concerns:
        return _check("tls", "warn", f"{summary} Note: {'; '.join(concerns)}.")
    return _check("tls", "pass", summary)


def _file_type_check(spec: SourceSpec, fetched: FetchedDocument) -> VerificationCheck:
    content_type = (fetched.content_type or "").split(";")[0].strip().lower()
    head = fetched.content[:2048]
    is_pdf = b"%PDF-" in head[:1024]
    if spec.format == "pdf":
        if not is_pdf:
            return _check(
                "file_type",
                "fail",
                f"Expected a PDF, but the file does not start like one (content type: "
                f"{content_type or 'unknown'}).",
            )
        if content_type and content_type != "application/pdf":
            return _check("file_type", "warn", f"A PDF, but the server labels it '{content_type}'.")
        return _check("file_type", "pass", "A PDF: the file header and the content type agree.")

    if is_pdf or "pdf" in content_type:
        return _check("file_type", "fail", "Expected a web page, but the server sent a PDF.")
    if "html" in content_type or b"<html" in head.lower():
        return _check("file_type", "pass", "A web page.")
    return _check("file_type", "fail", f"Expected a web page, got '{content_type or 'unknown'}'.")


def _size_check(fetched: FetchedDocument, max_bytes: int) -> VerificationCheck:
    if fetched.size_bytes == 0:
        return _check("size", "fail", "The download was empty.")
    if fetched.size_bytes > max_bytes:
        return _check(
            "size", "fail", f"{fetched.size_bytes:,} bytes exceeds the {max_bytes:,}-byte limit."
        )
    return _check("size", "pass", f"{fetched.size_bytes:,} bytes.")


def _robots_check(fetched: FetchedDocument) -> VerificationCheck:
    if fetched.robots == "allowed":
        return _check("robots", "pass", "robots.txt allows this download.")
    return _check("robots", "pass", "The site publishes no robots.txt rules, so none apply.")


def _squash(text: str) -> str:
    """Casefolded letters and digits only, so line wraps, hyphens and spacing do not matter."""
    return _NOT_ALNUM.sub("", text.casefold())


def _phrases_check(spec: SourceSpec, text: str) -> VerificationCheck:
    if not spec.expected_phrases:
        return _check("identity", "warn", "The registry lists no identity phrases to confirm.")
    haystack = _squash(text)
    missing = [phrase for phrase in spec.expected_phrases if _squash(phrase) not in haystack]
    if missing:
        return _check(
            "identity",
            "fail",
            "This does not look like the expected document; missing: "
            + ", ".join(f"'{phrase}'" for phrase in missing)
            + ".",
        )
    return _check("identity", "pass", f"Found all {len(spec.expected_phrases)} expected phrases.")


def _facts_check(spec: SourceSpec, text: str) -> VerificationCheck:
    haystack = _squash(text)
    missing = [fact for fact in spec.expected_facts if _squash(fact) not in haystack]
    if missing:
        return _check(
            "key_facts",
            "warn",
            "A figure a person confirmed is no longer in the text, so the document may have "
            "changed: " + ", ".join(f"'{fact}'" for fact in missing) + ". Re-check the source.",
        )
    return _check(
        "key_facts", "pass", f"All {len(spec.expected_facts)} confirmed figures are present."
    )


def _date_check(parsed: ParsedDocument, today: date) -> VerificationCheck:
    issued = parsed.document_date
    if issued is None:
        return _check(
            "document_date",
            "warn",
            "No issue date could be found, so the effective date is unknown (SPEC rule R4).",
        )
    source = parsed.date_source or "unknown source"
    age = datetime.combine(today, datetime.min.time(), UTC) - datetime.combine(
        issued, datetime.min.time(), UTC
    )
    if age < timedelta(days=-1):
        return _check(
            "document_date", "warn", f"The document date {issued} ({source}) is in the future."
        )
    if age > STALE_AFTER:
        return _check(
            "document_date",
            "warn",
            f"Dated {issued} ({source}): more than 12 months old, so it may have been superseded "
            "(SPEC rule R4). Look for a newer version.",
        )
    return _check("document_date", "pass", f"Dated {issued} ({source}).")


def _extraction_check(parsed: ParsedDocument) -> VerificationCheck:
    if parsed.warnings:
        return _check("extraction", "warn", " ".join(parsed.warnings))
    return _check("extraction", "pass", "No problems reading the document.")
