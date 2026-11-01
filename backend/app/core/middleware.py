"""ASGI middleware.

Written as plain ASGI rather than ``BaseHTTPMiddleware`` so streaming responses (such as the
text and audio explainers) are never buffered.
"""

import re
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging_config import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"

# A client-supplied id is only trusted if it is short and made of harmless characters,
# so it cannot be used to inject lines or markup into logs.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RequestIdMiddleware:
    """Give every request an id, make it available to logs and handlers, echo it in the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = supplied if _SAFE_REQUEST_ID.fullmatch(supplied) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id  # read as request.state.request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        token = request_id_var.set(request_id)
        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)


class _BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """Refuse a request body above ``max_bytes`` before any of it is processed.

    A declared ``Content-Length`` is checked at once, so a huge upload is turned away without
    reading it; a body sent in chunks (or with a false length) is counted as it arrives and stops
    when it passes the limit. Every endpoint of this API takes a few hundred bytes of JSON, so a
    large body is a mistake or an attack, and answering 413 with the usual error body keeps the
    server's memory and time for real visitors.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length", "")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self._refuse(scope, receive, send)
            return

        received = 0
        started = False  # has the application begun its own reply?
        refused = False  # have we answered 413 ourselves?

        async def counted() -> Message:
            nonlocal received, refused
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes and not started and not refused:
                    # Answer here and now: a framework that reads the body catches what is raised
                    # from this function and turns it into its own 400, so raising is not enough.
                    refused = True
                    await self._refuse(scope, receive, send)
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def watching(message: Message) -> None:
            nonlocal started
            if refused:
                return  # whatever the application now says, the visitor has had the 413
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, counted, watching)
        except _BodyTooLarge:
            if not refused:
                raise  # the reply had begun: too late to change it, the connection is cut

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_id = scope.get("state", {}).get("request_id")
        body = {
            "error": {
                "code": "payload_too_large",
                "message": "The request is too large.",
                **({"request_id": request_id} if request_id else {}),
            }
        }
        await JSONResponse(body, status_code=413, headers={"Connection": "close"})(
            scope, receive, send
        )
