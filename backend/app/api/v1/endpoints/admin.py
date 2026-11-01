import time
from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import (
    AssistantRuntimeDep,
    SchemeServiceDep,
    SettingsDep,
    index_unavailable,
    require_admin,
)
from app.domain.errors import IngestionError
from app.services.admin.knowledge import build_report, latest_evaluations
from app.services.admin.system import build_system_report
from app.services.ingestion.lock import lock_state
from app.services.ingestion.registry import load_registry

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/knowledge", summary="The health of the knowledge base, sector by sector")
def knowledge(
    response: Response,
    settings: SettingsDep,
    runtime: AssistantRuntimeDep,
    schemes: SchemeServiceDep,
) -> dict[str, Any]:
    """Records, documents and searchable passages per sector, what failed to index, what is due for
    a new check, how the assistant and its provider have been doing since the server started, and
    the latest benchmark results. Counted from the real data and index, never written down.

    Needs the ``X-Admin-Token`` header; without ``ADMIN_TOKEN`` configured the page does not exist.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        indexed = runtime.catalog.sources()
    except IngestionError as error:
        raise index_unavailable(error) from None
    book_schemes, entries, records = schemes.knowledge()
    return build_report(
        schemes=book_schemes,
        entries=entries,
        records=records,
        specs=load_registry(),
        indexed=indexed,
        stats=runtime.service.stats.snapshot(),
        provider={
            "configured": settings.gemini_api_key is not None,
            "model": settings.gemini_model,
        },
        evaluations=latest_evaluations(settings.data_dir / "eval"),
    )


@router.get("/system", summary="How the running system is behaving")
def system(
    request: Request,
    response: Response,
    settings: SettingsDep,
    runtime: AssistantRuntimeDep,
) -> dict[str, Any]:
    """Request counts and latencies per route, cache hit rates, the index, the language model, the
    latest answers' traces (identifiers and timings, never a question), and the last ingestion run.

    Counted in this process since it started. Needs the ``X-Admin-Token`` header.
    """
    response.headers["Cache-Control"] = "no-store"
    store = getattr(getattr(runtime.catalog, "_store", None), "scan_stats", None)
    passages: int | None = None
    error: str | None = None
    try:
        passages = sum(source.passages for source in runtime.catalog.sources())
    except IngestionError as failure:
        error = failure.code
    return build_system_report(
        requests=request.app.state.metrics.snapshot(),
        scan_stats=store() if callable(store) else None,
        provider={
            "configured": settings.gemini_api_key is not None,
            "model": settings.gemini_model,
            "circuit": runtime.service.model_health(),
        },
        assistant=runtime.service.stats.snapshot(),
        traces=runtime.service.traces.latest(),
        jobs_path=settings.data_dir / "jobs" / "ingest.json",
        uptime_seconds=time.monotonic() - request.app.state.started_at,
        index_passages=passages,
        index_error=error,
        ingest_lock=lock_state(settings.data_dir / "jobs" / "ingest.lock"),
        verification=runtime.service.traces.summary(),
    )
