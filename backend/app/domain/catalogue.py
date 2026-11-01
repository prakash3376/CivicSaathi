"""Types for the catalogue of programmes and services, and for the budget records.

The scholarship schemes in ``data/schemes`` are built for a questionnaire: tracks, rules, a
checklist. Most programmes need none of that: a person reads what they give, who they are for, what
to bring and where to apply. Those are ``Entry`` records in ``data/catalogue``. They hold the same
promise as the rules do: **every statement carries a quote from an official document**, and the
loader refuses a figure, month or address that the quote lacks.

A budget is not a scheme either. ``BudgetRecord`` keeps what a budget document says, with its
financial year and whether a figure is a Budget Estimate, a Revised Estimate or an Actual, so that
an allocation is never presented as money already spent.
"""

from datetime import date
from typing import Literal

from pydantic import Field

from app.domain.eligibility import Evidence, LocalText, Model, Sector

EntryKind = Literal["scheme", "service", "infrastructure"]
# Only what an official source has confirmed. A programme that cannot be confirmed is not added.
EntryStatus = Literal["active", "closed", "discontinued", "merged"]
Level = Literal["central", "state"]


class Cite(Evidence):
    """A quote, and where in the document it is ("page 4", "section 3.2") if that is known."""

    where: str = ""


class Statement(Model):
    """One fact about a programme, in English, with the official words that say so.

    The wording is English because the quotes are: translating a legal condition without a
    native-speaker review would risk changing it. Bengali and Hindi readers see the English
    statement with a notice, and can ask the assistant in their own language.
    """

    text: str = Field(min_length=3)
    evidence: list[Cite] = Field(min_length=1)


class Link(Model):
    """Where to apply, or where to use the service: an official address and its words."""

    label: str = Field(min_length=3)
    url: str
    evidence: list[Cite] = Field(default_factory=list)


class Entry(Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,62}$")
    name: str = Field(min_length=3)
    kind: EntryKind = "scheme"
    # One programme, any number of sectors: it is written once and listed under each.
    sectors: list[Sector] = Field(min_length=1)
    level: Level
    state: str | None = None
    applicable_states: list[str] = Field(default_factory=list)
    department: str = Field(min_length=3)
    status: EntryStatus = "active"
    status_note: str = ""
    source_ids: list[str] = Field(min_length=1)
    last_verified: date
    published_on: date | None = None
    effective_on: date | None = None
    summary: LocalText
    target: LocalText
    benefits: list[Statement] = Field(min_length=1)
    eligibility: list[Statement] = Field(default_factory=list)
    exclusions: list[Statement] = Field(default_factory=list)
    documents: list[Statement] = Field(default_factory=list)
    steps: list[Statement] = Field(default_factory=list)
    apply: Link
    # Things a person may expect to find that the documents do not say (SPEC rule R1).
    not_stated: list[str] = Field(default_factory=list)


# --- What the API shows -----------------------------------------------------------------------


class SourceRef(Model):
    id: str
    title: str
    url: str


class ProgrammeDetails(Model):
    """A catalogue entry for the detail page."""

    layout: Literal["info"] = "info"
    id: str
    name: str
    kind: EntryKind
    sectors: list[Sector]
    authority: str
    level: Level
    state: str | None
    applicable_states: list[str]
    status: EntryStatus
    status_note: str
    summary: LocalText
    target: LocalText
    source_ids: list[str]
    last_verified: date
    published_on: date | None
    effective_on: date | None
    benefits: list[Statement]
    eligibility: list[Statement]
    exclusions: list[Statement]
    documents: list[Statement]
    steps: list[Statement]
    apply: Link
    not_stated: list[str]
    sources: list[SourceRef]


# --- Budget -----------------------------------------------------------------------------------

# What a figure is. They are different things and are never mixed: an allocation is not spending.
Basis = Literal["budget_estimate", "revised_estimate", "actual"]
BudgetKind = Literal["allocation", "announcement", "tax"]
Unit = Literal["crore", "lakh_crore", "percent"]


class Figure(Model):
    basis: Basis
    year: str = Field(pattern=r"^\d{4}-\d{2}$")  # the financial year the figure is for: 2026-27
    amount: float
    unit: Unit = "crore"
    evidence: list[Cite] = Field(min_length=1)


class BudgetRecord(Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,62}$")
    budget_year: str = Field(pattern=r"^\d{4}-\d{2}$")  # the budget this record is from
    level: Level
    state: str | None = None
    sector: Sector | None = None  # None: not about one sector (taxation, the whole budget)
    kind: BudgetKind = "allocation"
    title: str = Field(min_length=3)
    department: str = Field(min_length=3)
    source_ids: list[str] = Field(min_length=1)
    last_verified: date
    summary: LocalText
    # What it means for an ordinary citizen, in plain words, from the document and no more.
    meaning: str = ""
    # Figures: the same measure, for different years or bases (BE, RE, Actual).
    figures: list[Figure] = Field(default_factory=list)
    # Announcements and tax changes carry statements instead of, or beside, figures.
    statements: list[Statement] = Field(default_factory=list)


class FigureView(Model):
    basis: Basis
    year: str
    amount: float
    unit: Unit
    evidence: list[Cite]


class BudgetView(Model):
    id: str
    budget_year: str
    level: Level
    state: str | None
    sector: Sector | None
    kind: BudgetKind
    title: str
    department: str
    last_verified: date
    summary: LocalText
    meaning: str
    figures: list[FigureView]
    statements: list[Statement]
    sources: list[SourceRef]
    not_actual_spending: bool  # True while no Actual figure is given: the money is a plan


class BudgetResponse(Model):
    records: list[BudgetView]
