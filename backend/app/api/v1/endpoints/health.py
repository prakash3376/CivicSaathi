import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from app import SERVICE_NAME, __version__
from app.api.deps import SettingsDep, get_assistant_runtime, get_scheme_service
from app.core.errors import AppError
from app.domain.errors import IngestionError
from app.schemas.health import ComponentStatus, HealthResponse, ReadyResponse
from app.services.ingestion.lock import lock_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
async def get_health(request: Request, response: Response, settings: SettingsDep) -> HealthResponse:
    """Report that the API is up. It touches no external dependency, so it is cheap to poll."""
    response.headers["Cache-Control"] = "no-store"  # a cached "ok" would defeat the check
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=__version__,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
        uptime_seconds=round(time.monotonic() - request.app.state.started_at, 1),
    )


@router.get(
    "/health/ready",
    summary="Readiness: which parts work",
    responses={503: {"model": ReadyResponse}},
)
def get_ready(request: Request, response: Response, settings: SettingsDep) -> ReadyResponse:
    """Say which parts of the service work, one by one.

    Liveness (``/health``) says the process is up. This says what it can do. The answer is 200 when
    the site can serve visitors, even if one part is limited: a language-model outage or a missing
    document index makes it ``degraded``, never dead, because browsing schemes, checking eligibility
    and reading the budget do not need either. Only if the records themselves cannot be loaded is it
    503. Nothing here carries a path, a key or a question.
    """
    response.headers["Cache-Control"] = "no-store"
    parts: dict[str, ComponentStatus] = {}

    try:
        get_scheme_service(request)
        parts["records"] = ComponentStatus(status="ok")
    except AppError:
        parts["records"] = ComponentStatus(
            status="down", detail="the scheme and budget records could not be loaded"
        )

    try:
        runtime = get_assistant_runtime(request)
        passages = sum(source.passages for source in runtime.catalog.sources())
        parts["index"] = (
            ComponentStatus(status="ok")
            if passages
            else ComponentStatus(status="degraded", detail="the document index is empty")
        )
        circuit = runtime.service.model_health()
    except (AppError, IngestionError):
        parts["index"] = ComponentStatus(
            status="degraded", detail="the document index cannot be read"
        )
        circuit = None

    if settings.gemini_api_key is None:
        parts["assistant_model"] = ComponentStatus(status="off", detail="no API key is configured")
    elif circuit and circuit.get("state") != "closed":
        parts["assistant_model"] = ComponentStatus(
            status="degraded",
            detail=f"paused after repeated failures ({circuit.get('last_failure')})",
        )
    else:
        parts["assistant_model"] = ComponentStatus(status="ok")

    ingest = lock_state(settings.data_dir / "jobs" / "ingest.lock")
    parts["ingestion"] = (
        ComponentStatus(status="degraded", detail="the last ingestion stopped without finishing")
        if ingest["state"] == "interrupted"
        else ComponentStatus(status="ok", detail=str(ingest["state"]))
    )

    if parts["records"].status == "down":
        overall = "unavailable"
        response.status_code = 503
    elif any(part.status in {"degraded", "down"} for part in parts.values()):
        overall = "degraded"
    else:
        overall = "ok"
    return ReadyResponse(status=overall, timestamp=datetime.now(UTC), components=parts)
