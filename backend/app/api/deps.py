"""Dependencies shared by route handlers."""

import logging
import secrets
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.errors import AppError
from app.domain.catalogue import SourceRef
from app.domain.errors import IngestionError, RegistryError, SchemeDataError
from app.services.assistant.runtime import AssistantRuntime
from app.services.catalogue.loader import load_budget, load_catalogue
from app.services.eligibility.loader import load_schemes
from app.services.eligibility.service import SchemeService
from app.services.ingestion.registry import load_registry

logger = logging.getLogger(__name__)


def get_request_settings(request: Request) -> Settings:
    """Return the settings the running app was built with (tests can build one with their own)."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_request_settings)]


def index_unavailable(error: IngestionError) -> AppError:
    """The error to send when the document index cannot be opened or read."""
    # The message names files and commands: for the operator, not the user.
    logger.error("The document index could not be used: %s", error.message)
    return AppError(
        "The library of official documents is not ready. Please try again later.",
        code="index_unavailable",
        status_code=503,
    )


def get_assistant_runtime(request: Request) -> AssistantRuntime:
    """The assistant and the source catalog, built the first time a request needs them.

    Building lazily means a missing index or API key cannot stop the rest of the API from
    starting. If building fails it is tried again on the next request, so fixing the problem
    (running the ingest command, say) does not need a restart of the server.
    """
    state = request.app.state
    if state.assistant_runtime is None:
        with state.assistant_lock:
            if state.assistant_runtime is None:
                # Imported here, not at the top: it pulls in ChromaDB, ONNX Runtime and the Gemini
                # SDK, which take seconds to load and are needed only from the first question.
                from app.services.assistant.factory import build_runtime

                try:
                    state.assistant_runtime = build_runtime(state.settings)
                except IngestionError as error:
                    raise index_unavailable(error) from None
    runtime: AssistantRuntime = state.assistant_runtime
    return runtime


AssistantRuntimeDep = Annotated[AssistantRuntime, Depends(get_assistant_runtime)]


def get_scheme_service(request: Request) -> SchemeService:
    """The scheme rules, loaded the first time they are asked for.

    They are checked as they load (``app.services.eligibility.loader``). A rule file that fails the
    checks is a mistake of whoever edited it: it is logged in full and shown to nobody, and the
    rest of the API keeps working.
    """
    state = request.app.state
    if state.schemes is None:
        with state.schemes_lock:
            if state.schemes is None:
                try:
                    registry = load_registry()
                    urls = {spec.id: spec.url for spec in registry}
                    state.schemes = SchemeService(
                        load_schemes(sources=urls),
                        entries=load_catalogue(sources=urls),
                        budget=load_budget(sources=urls),
                        sources={
                            spec.id: SourceRef(id=spec.id, title=spec.title, url=spec.url)
                            for spec in registry
                        },
                    )
                except (SchemeDataError, RegistryError) as error:
                    logger.error("The scheme rules could not be loaded: %s", error.message)
                    raise AppError(
                        "The schemes are not available right now. Please try later.",
                        code="schemes_unavailable",
                        status_code=503,
                    ) from None
    service: SchemeService = state.schemes
    return service


SchemeServiceDep = Annotated[SchemeService, Depends(get_scheme_service)]


def require_admin(request: Request) -> None:
    """Let in only whoever knows the admin token. Without a token configured, the page is off.

    Wrong guesses are counted per client, so the token cannot be found by trying; a client that
    sends the right one is never slowed down.
    """
    token = request.app.state.settings.admin_token
    if token is None:
        raise AppError("Not found.", code="not_found", status_code=404)
    sent = request.headers.get("x-admin-token", "")
    if secrets.compare_digest(sent.encode(), token.get_secret_value().encode()):
        return
    client = request.client.host if request.client else "unknown"
    wait = request.app.state.admin_limiter.retry_after(client)
    if wait is not None:
        raise AppError(
            "Too many wrong tokens. Please wait.",
            code="rate_limited",
            status_code=429,
            headers={"Retry-After": str(wait)},
        )
    raise AppError("The admin token is missing or wrong.", code="admin_denied", status_code=401)


def enforce_rate_limit(request: Request) -> None:
    """Refuse a client that is asking too fast, before any work is done for it."""
    client = request.client.host if request.client else "unknown"
    wait = request.app.state.rate_limiter.retry_after(client)
    if wait is not None:
        raise AppError(
            "You are asking too quickly. Please wait a moment and try again.",
            code="rate_limited",
            status_code=429,
            headers={"Retry-After": str(wait)},
        )
