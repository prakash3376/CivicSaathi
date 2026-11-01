from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """One problem found while validating a request."""

    loc: list[str | int] = Field(description="Where the problem is, e.g. ['body', 'language'].")
    message: str
    type: str


class ErrorBody(BaseModel):
    code: str = Field(description="Stable, machine-readable identifier such as 'not_found'.")
    message: str = Field(description="Plain-language explanation that is safe to show to users.")
    request_id: str | None = Field(
        default=None, description="Quote this id when reporting a problem."
    )
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """The single shape of every error the API returns."""

    error: ErrorBody
