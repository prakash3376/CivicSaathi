"""Request and response bodies of the scheme endpoints."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.eligibility import SchemeSummary


class SchemesResponse(BaseModel):
    schemes: list[SchemeSummary]


class EligibilityRequest(BaseModel):
    """The track (course or group) being checked, and the answers given so far.

    A question left out, or answered with ``null``, is skipped: an unknown, which can never make
    the result "eligible". The answers are used to build one response and are never stored.
    """

    model_config = ConfigDict(extra="forbid")

    track: str = Field(min_length=1, max_length=40)
    answers: dict[str, bool | int | float | str | None] = Field(default_factory=dict, max_length=20)
