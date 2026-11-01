from fastapi import APIRouter, Response

from app.api.deps import SchemeServiceDep
from app.core.errors import AppError
from app.domain.catalogue import BudgetResponse, ProgrammeDetails
from app.domain.eligibility import EligibilityResult, SchemeDetails
from app.schemas.schemes import EligibilityRequest, SchemesResponse
from app.services.eligibility.service import EligibilityInputError

router = APIRouter(prefix="/schemes", tags=["schemes"])

_STATUS = {"unknown_scheme": 404}  # anything else the check refuses is a 422


@router.get("", summary="The schemes, programmes and services")
def list_schemes(response: Response, service: SchemeServiceDep) -> SchemesResponse:
    """Everything in the catalogue, each with its sectors, who runs it, what it is for, and its
    deadline if the documents give one. ``layout`` says whether it has an eligibility check."""
    response.headers["Cache-Control"] = "no-store"  # a deadline's status depends on today's date
    return SchemesResponse(schemes=service.catalogue())


@router.get("/{scheme_id}", summary="One scheme or programme in detail")
def get_scheme(
    scheme_id: str, response: Response, service: SchemeServiceDep
) -> SchemeDetails | ProgrammeDetails:
    """What it requires (with the words of the document that say so), what it gives, which
    documents to gather, how to apply, and what the documents do not say."""
    response.headers["Cache-Control"] = "no-store"
    details = service.details(scheme_id)
    if details is None:
        raise AppError("There is no such scheme.", code="scheme_not_found", status_code=404)
    return details


@router.post("/{scheme_id}/eligibility", summary="Am I eligible?")
def check_eligibility(
    scheme_id: str, body: EligibilityRequest, response: Response, service: SchemeServiceDep
) -> EligibilityResult:
    """Decide from the answers whether the person is eligible: **eligible**, **not eligible**, or
    **need more info**, with a reason for each criterion and a checklist of documents.

    The decision is made by fixed rules, never by a language model: the same answers always give
    the same result, and a skipped question can never produce "eligible". The answers are not
    stored and are never logged.
    """
    response.headers["Cache-Control"] = "no-store"  # the response describes one person
    try:
        return service.check(scheme_id, body.track, body.answers)
    except EligibilityInputError as error:
        raise AppError(
            error.message, code=error.code, status_code=_STATUS.get(error.code, 422)
        ) from None


budget_router = APIRouter(prefix="/budget", tags=["budget"])


@budget_router.get("", summary="What the budget documents allocate")
def get_budget(response: Response, service: SchemeServiceDep) -> BudgetResponse:
    """Budget records with their financial year. A figure is a Budget Estimate, a Revised Estimate
    or an Actual, never mixed: an allocation is not money already spent."""
    response.headers["Cache-Control"] = "no-store"
    return BudgetResponse(records=service.budget())
