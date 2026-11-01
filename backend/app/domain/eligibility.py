"""Types for schemes and the eligibility engine.

A scheme is data, not code: what it requires, in a form a program can evaluate, with the words of
the official document that say so (``Evidence``). What a person answers is a ``Profile`` (a plain
mapping of field to value, never stored). What follows is an ``EligibilityResult``.
"""

from datetime import date
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Scalar = bool | int | float | str
Outcome = Literal["eligible", "not_eligible", "need_more_info"]
Status = Literal["met", "not_met", "unknown"]
Operator = Literal["eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in"]
FieldType = Literal["number", "yes_no", "choice"]
DeadlineStatus = Literal["open", "closes_today", "closed"]
Applicability = Literal["needed", "maybe"]
# The sectors a scheme can belong to. The pages for them live in the frontend, which must list the
# same ids (`features/sectors/sectors.ts`); a scheme with an unknown sector is refused when loaded.
Sector = Literal[
    "education",
    "health",
    "agriculture",
    "women-child",
    "employment",
    "housing",
    "social-welfare",
    "business",
    "transport",
    "budget",
    "environment",
    "public-services",
]
SECTORS: tuple[Sector, ...] = get_args(Sector)  # in the order the home page shows them


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocalText(Model):
    """Wording in every language of the product. Figures are written with the digits 0-9."""

    en: str = Field(min_length=1)
    bn: str = Field(min_length=1)
    hi: str = Field(min_length=1)


class Evidence(Model):
    """Words of an official document that support a statement. Checked against the index."""

    source_id: str
    quote: str = Field(min_length=1)


# --- What is asked --------------------------------------------------------------------------


class Choice(Model):
    id: str
    label: LocalText


class Question(Model):
    """One question of the questionnaire. Answering it is always optional: a skipped question is
    an unknown, and an unknown can never produce "eligible"."""

    field: str
    type: FieldType
    text: LocalText
    hint: LocalText | None = None
    unit: LocalText | None = None
    choices: list[Choice] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = False


class FieldDef(Model):
    id: str
    type: FieldType
    question: LocalText
    hint: LocalText | None = None
    unit: LocalText | None = None
    display: LocalText | None = None  # how a number is shown back; "{value}" is the number
    choices: list[Choice] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = False


# --- What a scheme requires ------------------------------------------------------------------


class Condition(Model):
    """``field op value``. The value of ``in`` and ``not_in`` is a list of choice ids."""

    field: str
    op: Operator = "eq"
    value: Scalar | list[str]


class Criterion(Model):
    id: str
    label: LocalText
    condition: Condition
    # If all of these hold the criterion is not required of this person (an exemption the
    # document states, such as "not applicable for Board Toppers").
    waived_when: list[Condition] = Field(default_factory=list)
    ask: LocalText | None = None  # wording of the question, if the field's own does not fit
    note: LocalText | None = None
    evidence: list[Evidence] = Field(min_length=1)


class DocumentItem(Model):
    id: str
    label: LocalText
    detail: LocalText | None = None
    # Needed only if all of these hold; "maybe" while they cannot yet be decided.
    needed_when: list[Condition] = Field(default_factory=list)
    if_applicable: bool = False  # the document says "if applicable": shown as "maybe"
    evidence: list[Evidence] = Field(min_length=1)


class Step(Model):
    id: str
    text: LocalText
    evidence: list[Evidence] = Field(min_length=1)


class Contact(Model):
    id: str
    label: LocalText
    value: str  # an e-mail address or a phone number, exactly as in the document
    evidence: list[Evidence] = Field(min_length=1)


class Deadline(Model):
    id: str
    label: LocalText
    on: date
    # The document is a scan read by OCR: its figures may be misread and must be checked.
    scanned: bool = False
    evidence: list[Evidence] = Field(min_length=1)


class Caveat(Model):
    """Something the person must still check that the questionnaire does not decide."""

    id: str
    text: LocalText
    evidence: list[Evidence] = Field(min_length=1)


class Benefit(Model):
    text: LocalText
    evidence: list[Evidence] = Field(min_length=1)


class Apply(Model):
    text: LocalText
    url: str
    evidence: list[Evidence] = Field(min_length=1)


class Track(Model):
    """A variant of a scheme with its own rules: a level of study, a course, a group."""

    id: str
    label: LocalText
    description: LocalText | None = None
    # Ids of the scheme's common criteria and documents that this track does not need.
    omit_common: list[str] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    documents: list[DocumentItem] = Field(default_factory=list)
    caveats: list[Caveat] = Field(default_factory=list)
    benefit: Benefit


class Scheme(Model):
    id: str
    name: str
    authority: str
    level: Literal["central", "state"]
    state: str | None = None
    sectors: list[Sector] = Field(min_length=1)
    summary: LocalText
    source_ids: list[str] = Field(min_length=1)
    criteria: list[Criterion] = Field(default_factory=list)  # common to every track
    documents: list[DocumentItem] = Field(default_factory=list)  # common to every track
    caveats: list[Caveat] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    contacts: list[Contact] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    apply: Apply
    # Things a person may expect to find that the documents do not say (rule R1).
    not_stated: list[LocalText] = Field(default_factory=list)
    tracks: list[Track] = Field(min_length=1)


# --- What the catalogue shows ------------------------------------------------------------------


class TrackStub(Model):
    id: str
    label: LocalText


class CriterionView(Model):
    id: str
    label: LocalText
    note: LocalText | None = None
    evidence: list[Evidence]


# --- What comes out --------------------------------------------------------------------------


class CriterionResult(Model):
    id: str
    label: LocalText
    status: Status
    waived: bool = False
    field: str
    answer_text: LocalText | None = None  # what the person answered, in words
    note: LocalText | None = None
    evidence: list[Evidence]


class ChecklistDocument(Model):
    id: str
    label: LocalText
    detail: LocalText | None = None
    applicability: Applicability
    evidence: list[Evidence]


class DeadlineView(Model):
    id: str
    label: LocalText
    on: date
    status: DeadlineStatus
    days_left: int | None = None  # None once it has passed
    scanned: bool = False
    evidence: list[Evidence]


class Checklist(Model):
    documents: list[ChecklistDocument]
    steps: list[Step]
    contacts: list[Contact]
    deadlines: list[DeadlineView]
    apply: Apply
    not_stated: list[LocalText]


class TrackView(Model):
    id: str
    label: LocalText
    description: LocalText | None = None
    benefit: Benefit
    criteria: list[CriterionView]
    questions: list[Question]
    documents: list[ChecklistDocument]  # "maybe" for any that depend on the answers
    caveats: list[Caveat]


class SchemeSummary(Model):
    id: str
    name: str
    authority: str
    level: Literal["central", "state"]
    state: str | None = None
    sectors: list[Sector]
    summary: LocalText
    source_ids: list[str]
    tracks: list[TrackStub]
    deadline: DeadlineView | None = None
    # The same card serves the questionnaire schemes and the information-only programmes.
    layout: Literal["check", "info"] = "check"
    kind: Literal["scheme", "service", "infrastructure"] = "scheme"
    status: Literal["active", "closed", "discontinued", "merged"] = "active"
    target: LocalText | None = None
    benefit: str | None = None
    last_verified: date | None = None


class SchemeDetails(Model):
    layout: Literal["check"] = "check"
    id: str
    name: str
    authority: str
    level: Literal["central", "state"]
    state: str | None = None
    sectors: list[Sector]
    summary: LocalText
    source_ids: list[str]
    tracks: list[TrackView]
    steps: list[Step]
    contacts: list[Contact]
    deadlines: list[DeadlineView]
    apply: Apply
    not_stated: list[LocalText]


class EligibilityResult(Model):
    scheme_id: str
    track_id: str
    outcome: Outcome
    criteria: list[CriterionResult]
    unanswered: list[str]  # question fields still needed, in the order they are asked
    caveats: list[Caveat]
    checklist: Checklist
    disclaimer: LocalText
