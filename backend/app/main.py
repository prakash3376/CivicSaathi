"""Application factory and ASGI entry point: ``uvicorn app.main:app``."""

import logging
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import SERVICE_NAME, __version__
from app.api.v1.router import API_V1_PREFIX, api_router
from app.core.config import Settings, get_settings
from app.core.errors import (
    AppError,
    handle_app_error,
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
)
from app.core.logging_config import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, BodyLimitMiddleware, RequestIdMiddleware
from app.core.observability import (
    ETagMiddleware,
    ObservabilityMiddleware,
    RequestMetrics,
    SecurityHeadersMiddleware,
)
from app.core.rate_limit import RateLimiter
from app.services.assistant.runtime import AssistantRuntime
from app.services.eligibility.service import SchemeService

logger = logging.getLogger(__name__)

# Public, read-only lists that are the same for everyone: a client may ask again with the hash
# it has and be told 304. Personal replies (an answer, an eligibility result) are POSTs.
CACHEABLE_PREFIXES = (
    f"{API_V1_PREFIX}/schemes",
    f"{API_V1_PREFIX}/budget",
    f"{API_V1_PREFIX}/sources",
)
GZIP_MINIMUM_BYTES = 1000
# Starlette's default is 9, which compresses these lists about as small as 5 does but costs several
# times the CPU, and it runs on the event loop: measured in docs/BENCHMARKS.md.
GZIP_LEVEL = 5


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown hook. Shared resources (LLM client, caches) belong here."""
    settings: Settings = app.state.settings
    logger.info("%s v%s starting (environment=%s)", SERVICE_NAME, __version__, settings.app_env)
    yield
    logger.info("%s shutting down", SERVICE_NAME)


def create_app(
    settings: Settings | None = None,
    *,
    assistant: AssistantRuntime | None = None,
    schemes: SchemeService | None = None,
) -> FastAPI:
    """Build the app. Tests pass their own ``settings``; production reads the environment.

    ``assistant`` and ``schemes`` are ready-made services to use (tests give the assistant a fake
    model and the schemes a fixed date). Without them they are built the first time a request
    needs them.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=SERVICE_NAME,
        version=__version__,
        description="Plain-language, multilingual explainers for government policy documents.",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_V1_PREFIX}/openapi.json" if settings.docs_enabled else None,
        exception_handlers={
            AppError: handle_app_error,
            StarletteHTTPException: handle_http_exception,
            RequestValidationError: handle_validation_error,
            Exception: handle_unexpected_error,
        },
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.started_at = time.monotonic()
    app.state.assistant_runtime = assistant
    app.state.assistant_lock = threading.Lock()
    app.state.schemes = schemes
    app.state.schemes_lock = threading.Lock()
    app.state.rate_limiter = RateLimiter(settings.assistant_rate_limit_per_minute)
    app.state.admin_limiter = RateLimiter(settings.admin_rate_limit_per_minute)
    app.state.metrics = RequestMetrics()

    # The last middleware added is the outermost. CORS wraps everything so that even error
    # responses carry its headers; the request id is then attached closest to the app.
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ObservabilityMiddleware, metrics=app.state.metrics, log=settings.access_log)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ETagMiddleware, prefixes=CACHEABLE_PREFIXES, metrics=app.state.metrics)
    if settings.compress_responses:
        app.add_middleware(
            GZipMiddleware, minimum_size=GZIP_MINIMUM_BYTES, compresslevel=GZIP_LEVEL
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],  # lets the frontend show it in "Report an error"
    )

    app.include_router(api_router, prefix=API_V1_PREFIX)

    if settings.frontend_dir is not None and (settings.frontend_dir / "index.html").is_file():
        _serve_website(app, settings.frontend_dir)
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict[str, str]:
            links = {
                "service": SERVICE_NAME,
                "version": __version__,
                "health": f"{API_V1_PREFIX}/health",
            }
            if settings.docs_enabled:
                links["docs"] = "/docs"
            return links

    return app


def _serve_website(app: FastAPI, directory: Path) -> None:
    """Serve the built frontend: its files, and ``index.html`` for every page route.

    The pages are routes of the single-page app (``/schemes/...``), so a reload or a shared link
    must get ``index.html``. An address under ``/api`` that matches nothing stays a 404 in the API's
    own error format, never a page. Registered last so that the API and ``/docs`` match first.
    """
    root = directory.resolve()
    index = root / "index.html"
    api_prefix = "api/"

    @app.get("/{path:path}", include_in_schema=False)
    async def website(path: str) -> FileResponse:
        if path.startswith(api_prefix):
            raise StarletteHTTPException(status_code=404, detail="Not found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            # Built assets have a hash in their name, so they never change under one name.
            immutable = candidate.parent.name == "assets"
            cache = "public, max-age=31536000, immutable" if immutable else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})  # a page of the app


app = create_app()
