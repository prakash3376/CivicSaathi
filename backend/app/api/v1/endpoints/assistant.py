from fastapi import APIRouter, Depends, Response

from app.api.deps import AssistantRuntimeDep, enforce_rate_limit, index_unavailable
from app.core.errors import AppError
from app.domain.errors import AssistantError, IngestionError
from app.schemas.assistant import AskRequest, AskResponse

router = APIRouter(prefix="/assistant", tags=["assistant"])

# How each way the assistant can fail reaches the client. A failure on our side or the model's is
# a 5xx; a question that cannot be answered as sent is a 4xx.
_STATUS = {
    "question_empty": 422,
    "question_too_long": 422,
    "llm_busy": 429,
    "llm_bad_output": 502,
    "assistant_not_configured": 503,
    "index_empty": 503,
    "llm_unavailable": 503,
    "llm_auth": 503,
    "llm_rejected": 503,
}
_RETRY_AFTER_SECONDS = "30"


def _as_http_error(error: AssistantError) -> AppError:
    status = _STATUS.get(error.code, 500)
    headers = {"Retry-After": _RETRY_AFTER_SECONDS} if status == 429 else None
    return AppError(error.message, code=error.code, status_code=status, headers=headers)


@router.post(
    "/ask",
    summary="Ask a question about the official documents",
    dependencies=[Depends(enforce_rate_limit)],
)
def ask(body: AskRequest, response: Response, runtime: AssistantRuntimeDep) -> AskResponse:
    """Answer a question from the official documents, in English, Hindi or Bengali.

    Every statement in the answer comes with a quote from an official document that it was checked
    against. If the documents do not say, the answer says so instead of guessing. This is a plain
    ``def`` so that FastAPI runs it in a worker thread: it waits on the embedding model and on the
    language model.
    """
    response.headers["Cache-Control"] = "no-store"  # an answer may echo what the user asked about
    try:
        return runtime.service.ask(
            body.question,
            language=body.language,
            source_ids=body.source_ids,
            history=body.history,
            sector=body.sector,
        )
    except AssistantError as error:
        raise _as_http_error(error) from None
    except IngestionError as error:  # the index could not be read
        raise index_unavailable(error) from None
