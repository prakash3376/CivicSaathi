"""Request and response bodies of the assistant endpoints."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.assistant import Answer, LanguageChoice, SourceSummary
from app.domain.eligibility import Sector

SourceId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,62}$")]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The limit that matters (ASSISTANT_MAX_QUESTION_CHARS) is applied by the assistant, with a
    # friendlier message; this one only keeps absurd request bodies out.
    question: str = Field(min_length=1, max_length=2000, description="The question to answer.")
    language: LanguageChoice = Field(
        default="auto",
        description=(
            "'en', 'bn' or 'hi' sets the language of the answer; 'auto' follows the question."
        ),
    )
    source_ids: list[SourceId] | None = Field(
        default=None,
        max_length=20,
        description="Only answer from these sources (see GET /sources); by default, from all.",
    )
    history: list[Annotated[str, StringConstraints(max_length=500)]] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Earlier questions of the same conversation, oldest first. They help to find the "
            "documents for a question such as 'what documents do I need for it?' and are never "
            "sent to the language model."
        ),
    )
    sector: Sector | None = Field(
        default=None,
        description=(
            "The sector the person is looking at. It nudges that sector's documents up; it never "
            "hides another sector's, so a question about something else is still answered."
        ),
    )


# An answer is returned as the assistant produced it.
AskResponse = Answer


class SourcesResponse(BaseModel):
    sources: list[SourceSummary]
