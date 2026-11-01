"""What the API is doing: one timed, structured line per request, and counters an operator can read.

Four small pieces, all plain ASGI so that nothing is buffered that did not have to be:

``ObservabilityMiddleware``   times each request, adds a ``Server-Timing`` header, writes one log
                              line (method, route, status, milliseconds; the request id is stamped
                              by the logging filter) and feeds ``RequestMetrics``.
``RequestMetrics``            per-route counts, errors, rate-limit refusals and the latest
                              latencies, in memory (``GET /api/v1/admin/system`` shows them).
``SecurityHeadersMiddleware`` the headers that make a browser treat an API reply as data only.
``ETagMiddleware``            a content hash on cacheable GET replies, and ``304 Not Modified``
                              when the client already has them. Bytes are saved, never freshness:
                              the reply is always recomputed, so a deadline cannot go stale.

No query string, body or header value is logged: a question or a questionnaire answer can be
personal (SPEC AC9).
"""

import hashlib
import logging
import statistics
import threading
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import ClassVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.access")

_KEEP = 500  # latencies remembered per route
_ID_LIKE = "{id}"


def route_of(scope: Scope) -> str:
    """The route as written (``/api/v1/schemes/{scheme_id}``), not the address asked for.

    Grouping by the template keeps the counters small and keeps ids out of the log. Before routing
    has matched anything (a 404) the path is shown as ``unmatched``.
    """
    route = scope.get("route")
    template = getattr(route, "path", None)
    return str(template) if template else "unmatched"


@dataclass
class _Route:
    calls: int = 0
    errors: int = 0  # 5xx
    refused: int = 0  # 429
    not_modified: int = 0  # 304
    milliseconds: deque[float] = field(default_factory=lambda: deque(maxlen=_KEEP))


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._routes: dict[str, _Route] = defaultdict(_Route)
        self._cache: Counter[str] = Counter()

    def record(self, method: str, route: str, status: int, milliseconds: float) -> None:
        with self._lock:
            entry = self._routes[f"{method} {route}"]
            entry.calls += 1
            entry.errors += status >= 500
            entry.refused += status == 429
            entry.not_modified += status == 304
            entry.milliseconds.append(milliseconds)

    def count(self, name: str, hit: bool) -> None:
        """A cache lookup, so that the hit rate can be reported."""
        with self._lock:
            self._cache[f"{name}.{'hit' if hit else 'miss'}"] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            routes = {}
            for name, entry in sorted(self._routes.items()):
                times = sorted(entry.milliseconds)
                routes[name] = {
                    "calls": entry.calls,
                    "errors": entry.errors,
                    "rate_limited": entry.refused,
                    "not_modified": entry.not_modified,
                    "p50_ms": round(statistics.median(times), 1) if times else None,
                    "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1) if times else None,
                }
            names = {key.rsplit(".", 1)[0] for key in self._cache}
            caches = {
                name: {
                    "hits": self._cache[f"{name}.hit"],
                    "misses": self._cache[f"{name}.miss"],
                    "hit_rate": round(
                        self._cache[f"{name}.hit"]
                        / (self._cache[f"{name}.hit"] + self._cache[f"{name}.miss"]),
                        3,
                    ),
                }
                for name in sorted(names)
            }
            return {"routes": routes, "caches": caches}


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp, metrics: RequestMetrics, *, log: bool = True) -> None:
        self.app = app
        self.metrics = metrics
        self.log = log

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def send_timed(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                elapsed = (time.perf_counter() - started) * 1000
                MutableHeaders(scope=message)["Server-Timing"] = f"app;dur={elapsed:.1f}"
            await send(message)

        try:
            await self.app(scope, receive, send_timed)
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            route = route_of(scope)
            method = str(scope.get("method", "?"))
            self.metrics.record(method, route, status, elapsed)
            if self.log:
                logger.info("%s %s -> %d in %.1f ms", method, route, status, elapsed)


class SecurityHeadersMiddleware:
    """Headers that stop a browser from guessing, framing or leaking from an API reply."""

    HEADERS: ClassVar[dict[str, str]] = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
        "Cross-Origin-Resource-Policy": "same-site",
        "Permissions-Policy": "camera=(), geolocation=(), payment=()",
    }

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_secure(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_secure)


class ETagMiddleware:
    """Hash a cacheable GET reply and answer ``304`` when the client already has it.

    Only the paths in ``prefixes`` and only ``200`` replies are touched. The reply is always
    computed afresh: the saving is the body that is not sent again, so a changed deadline or a
    re-indexed document shows at once (the hash changes with it). The browser is told
    ``no-cache``, which means "ask me every time", never "use it for a while".
    """

    def __init__(
        self, app: ASGIApp, prefixes: tuple[str, ...], metrics: RequestMetrics | None = None
    ) -> None:
        self.app = app
        self.prefixes = prefixes
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        if (
            scope["type"] != "http"
            or scope.get("method") != "GET"
            or not path.startswith(self.prefixes)
        ):
            await self.app(scope, receive, send)
            return

        sent_start: Message | None = None
        body = bytearray()

        async def capture(message: Message) -> None:
            nonlocal sent_start
            if message["type"] == "http.response.start":
                sent_start = message
                return
            if message["type"] == "http.response.body":
                body.extend(message.get("body", b""))
                if message.get("more_body"):
                    return
                await self._finish(scope, sent_start, bytes(body), send)

        await self.app(scope, receive, capture)

    async def _finish(self, scope: Scope, start: Message | None, body: bytes, send: Send) -> None:
        assert start is not None
        if start["status"] != 200:
            await send(start)
            await send({"type": "http.response.body", "body": body})
            return
        etag = '"' + hashlib.sha1(body, usedforsecurity=False).hexdigest()[:20] + '"'
        headers = MutableHeaders(scope=start)
        headers["ETag"] = etag
        headers["Cache-Control"] = "no-cache"
        wanted = Headers(scope=scope).get("if-none-match", "")
        if etag in {part.strip().removeprefix("W/") for part in wanted.split(",")}:
            if self.metrics:
                self.metrics.count("etag", True)
            for name in ("content-length", "content-type"):
                del headers[name]
            start["status"] = 304
            await send(start)
            await send({"type": "http.response.body", "body": b""})
            return
        if self.metrics:
            self.metrics.count("etag", False)
        headers["Content-Length"] = str(len(body))
        await send(start)
        await send({"type": "http.response.body", "body": body})
