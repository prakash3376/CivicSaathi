"""One error format for the whole API.

Every error response, whether raised on purpose, produced by validation or caused by a bug,
has the shape ``{"error": {"code": ..., "message": ..., "request_id": ...}}`` so clients only
need one parser. Handlers are wired up in ``app.main.create_app``.
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import REQUEST_ID_HEADER
from app.schemas.errors import ErrorBody, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An expected failure that should reach the user as a friendly, coded message.

    Subclass it for each failure the product has to explain (an unreadable scan, an unsupported
    document type, ...) and override ``default_code`` / ``default_status_code``.
    """

    default_code = "bad_request"
    default_status_code = HTTPStatus.BAD_REQUEST

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """``headers`` are sent with the error response (for example ``Retry-After``)."""
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.status_code = int(status_code or self.default_status_code)
        self.headers = headers


def _status_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:  # non-standard status code
        return "Error"


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[ErrorDetail] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id: str | None = getattr(request.state, "request_id", None)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details)
    )
    response = JSONResponse(
        body.model_dump(mode="json", exclude_none=True), status_code=status_code, headers=headers
    )
    if request_id:
        # Errors raised outside the request-id middleware's response path still carry the id.
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(request, exc.status_code, exc.code, exc.message, headers=exc.headers)


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
    if exc.status_code in {HTTPStatus.NO_CONTENT, HTTPStatus.NOT_MODIFIED}:
        return Response(status_code=exc.status_code, headers=exc.headers)  # bodies are forbidden
    phrase = _status_phrase(exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else phrase
    code = phrase.lower().replace(" ", "_")
    return _error_response(request, exc.status_code, code, message, headers=exc.headers)


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Only where and why a field failed is reported; the submitted value is never echoed back,
    # because it may be personal information from an uploaded document or a questionnaire.
    details = [
        ErrorDetail(loc=list(error["loc"]), message=error["msg"], type=error["type"])
        for error in exc.errors()
    ]
    return _error_response(
        request,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "validation_error",
        "Some of the information sent is missing or invalid.",
        details=details,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # This handler runs after the request-id context has been torn down, so pass the id explicitly.
    request_id = getattr(request.state, "request_id", "-")
    logger.error(
        "Unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
        extra={"request_id": request_id},
    )
    return _error_response(
        request,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        "internal_error",
        "Something went wrong on our side. Please try again.",
    )
