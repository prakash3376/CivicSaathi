"""Types for answering a question: what is retrieved, what the model drafts, what the user sees."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "bn", "hi"]
LanguageChoice = Literal["auto", "en", "bn", "hi"]


class Passage(BaseModel):
    """A retrieved passage with what is needed to cite it and to judge how fresh it is."""

    ref: str = Field(default="", description="How the model refers to it (S1, S2, ...).")
    chunk_id: str
    source_id: str
    title: str
    scheme: str = ""
    authority: str = ""
    url: str
    text: str
    page_start: int | None = None
    page_end: int | None = None
    section: str = ""
    clause: str = ""
    document_date: date | None = None
    date_source: str | None = None
    verified_at: datetime | None = None
    verification: str = ""
    ocr: bool = False
    language: str | None = Field(
        default=None,
        description="Language of the passage (en, bn, hi, ...), judged from its script.",
    )
    score: float = 0.0


# --- What the model is asked to return -------------------------------------------------------


class Evidence(BaseModel):
    source: str = Field(description="The id of the source the quote comes from, such as S1.")
    quote: str = Field(
        description="Words copied exactly, without changes, from that source, that support it."
    )


class DraftClaim(BaseModel):
    statement: str = Field(description="One fact of the answer, as one or two short sentences.")
    evidence: list[Evidence] = Field(
        description="At least one exact quote supporting the statement."
    )


class Draft(BaseModel):
    answerable: bool = Field(description="False if the sources do not contain the answer.")
    claims: list[DraftClaim] = Field(
        description="The facts of the answer; empty if not answerable."
    )
    not_stated: list[str] = Field(
        default_factory=list,
        description="Short phrases for parts of the question the sources do not cover.",
    )


class Guidance(BaseModel):
    """What the model is asked to return when the documents do not cover a question."""

    on_topic: bool = Field(
        description="False if the question is not about government schemes, services, "
        "documents, benefits or rights."
    )
    reply: str = Field(
        default="",
        description="Two to five short spoken sentences of general, practical help; empty if "
        "the question is not on topic.",
    )
    follow_up: str = Field(
        default="",
        description="One short friendly question that helps the next turn; empty if none.",
    )


# --- What the user is shown ------------------------------------------------------------------


class Highlight(BaseModel):
    """Where a quote sits inside the cited passage's text."""

    start: int
    end: int


class Citation(BaseModel):
    number: int = Field(description="The number shown beside the claims that rely on it.")
    source_id: str
    title: str
    authority: str = ""
    url: str
    page_start: int | None = None
    page_end: int | None = None
    section: str = ""
    clause: str = ""
    passage: str = Field(description="The full text of the cited passage, as in the document.")
    quote: str = Field(description="The words of the passage that support the claim.")
    language: str | None = Field(
        default=None, description="Language of the passage and quote, so they can be read aloud."
    )
    highlights: list[Highlight] = Field(default_factory=list)
    document_date: date | None = None
    date_source: str | None = None
    verified_at: datetime | None = None
    verification: str = ""
    age_days: int | None = Field(
        default=None, description="Age of the document, if its date is known."
    )
    stale: bool = Field(default=False, description="Older than 12 months (SPEC rule R4).")
    ocr: bool = Field(default=False, description="Read from a scan: figures may be misread.")


class AnswerClaim(BaseModel):
    text: str
    citations: list[int]


class AnswerWarning(BaseModel):
    code: str
    message: str
    source_ids: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    answerable: bool
    language: Language
    text: str
    claims: list[AnswerClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    not_stated: list[str] = Field(
        default_factory=list, description="Parts of the question the documents do not cover (R1)."
    )
    warnings: list[AnswerWarning] = Field(default_factory=list)
    disclaimer: str
    model: str | None = None
    intent: str | None = Field(
        default=None, description="What the question was judged to be for (rule based)."
    )
    fallback: bool = Field(
        default=False,
        description="The model could not answer: the citations are the passages that best "
        "match the question, shown as they are in the documents, with no explanation.",
    )
    guidance: bool = Field(
        default=False,
        description="The documents do not cover the question, so `text` is general help that "
        "does NOT come from an official document: it has no citations and no figures.",
    )
    guidance_intro: str = Field(
        default="",
        description="Fixed text that says so, to be shown or read before `text` when `guidance`.",
    )
    follow_up: str = Field(
        default="",
        description="A short question that keeps a conversation going (general help only).",
    )
    conversational: bool = Field(
        default=False,
        description="A greeting, thanks or a question about the assistant: not an explainer, so "
        "there is nothing to cite.",
    )


class SourceSummary(BaseModel):
    """What is indexed for one source and how fresh it is."""

    id: str
    title: str
    scheme: str
    authority: str
    level: str
    state: str | None = None
    doc_type: str
    format: str
    url: str
    passages: int
    document_date: date | None = None
    date_source: str | None = None
    verified_at: datetime | None = None
    verification: str = ""
    age_days: int | None = None
    stale: bool = False
    verification_due: bool = Field(
        default=False, description="Last verified long enough ago that it should be re-run."
    )
    ocr: bool = False
