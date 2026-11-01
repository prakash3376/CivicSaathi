from fastapi import APIRouter, Response

from app.api.deps import AssistantRuntimeDep, index_unavailable
from app.domain.errors import IngestionError
from app.schemas.assistant import SourcesResponse

router = APIRouter(tags=["sources"])


@router.get("/sources", summary="The official documents the assistant answers from")
def list_sources(response: Response, runtime: AssistantRuntimeDep) -> SourcesResponse:
    """Each indexed source with its date, when it was last verified, and whether it is old.

    Documents older than twelve months or overdue for a new check are flagged (SPEC rule R4).
    """
    response.headers["Cache-Control"] = "no-store"  # the flags depend on today's date
    try:
        return SourcesResponse(sources=runtime.catalog.sources())
    except IngestionError as error:  # the index could not be read
        raise index_unavailable(error) from None
