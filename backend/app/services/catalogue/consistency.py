"""Do the records agree with each other? The loader proves each record against its own documents;
this looks across records for the mistakes that only show up in pairs.

* **Duplicates.** One programme written twice under two ids would be listed twice, and the two
  copies would drift apart when only one is updated.
* **Conflicting figures.** The same measure, for the same year and the same basis (budget estimate,
  revised estimate or actual), with two different amounts. Estimates and actuals *should* differ
  from each other; two figures of one kind must not. Neither is chosen over the other: a person
  reads both documents.
* **Impossible figures.** An actual for a year that had not ended when the budget was presented, or
  a revised estimate for a later year.
* **Impossible dates.** A document published after the day it was checked, or a check dated in the
  future.

Nothing here edits a record. A finding is for a person to settle; ``error`` ones stop
``catalogue-check`` from passing, ``warning`` ones are listed.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.domain.catalogue import BudgetRecord, Entry, Figure

Severity = Literal["error", "warning"]
_WORDS = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    ids: tuple[str, ...]
    detail: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.code}: {', '.join(self.ids)}: {self.detail}"


def _name(text: str) -> str:
    return _WORDS.sub(" ", text.lower()).strip()


def _start(year: str) -> int:
    return int(year[:4])


def _crore(figure: Figure) -> float:
    """The amount in crore, so that 1 lakh crore and 100000 crore are the same figure."""
    return figure.amount * 100_000 if figure.unit == "lakh_crore" else figure.amount


def check_consistency(
    entries: Sequence[Entry], records: Sequence[BudgetRecord], *, today: date
) -> list[Finding]:
    return [
        *_duplicate_entries(entries),
        *_entry_dates(entries, today),
        *_figures(records),
        *_record_dates(records, today),
    ]


def _duplicate_entries(entries: Sequence[Entry]) -> list[Finding]:
    seen: dict[tuple[str, str, str | None], list[str]] = defaultdict(list)
    for entry in entries:
        seen[(_name(entry.name), entry.level, entry.state)].append(entry.id)
    return [
        Finding("error", "duplicate_entry", tuple(ids), f"the same programme under {len(ids)} ids")
        for ids in seen.values()
        if len(ids) > 1
    ]


def _entry_dates(entries: Sequence[Entry], today: date) -> list[Finding]:
    found: list[Finding] = []
    for entry in entries:
        if entry.last_verified > today:
            found.append(
                Finding("error", "verified_in_future", (entry.id,), f"{entry.last_verified}")
            )
        if entry.published_on and entry.published_on > entry.last_verified:
            found.append(
                Finding(
                    "error",
                    "published_after_verified",
                    (entry.id,),
                    f"published {entry.published_on}, but last checked {entry.last_verified}",
                )
            )
    return found


def _record_dates(records: Sequence[BudgetRecord], today: date) -> list[Finding]:
    return [
        Finding("error", "verified_in_future", (record.id,), f"{record.last_verified}")
        for record in records
        if record.last_verified > today
    ]


def _figures(records: Sequence[BudgetRecord]) -> list[Finding]:
    found: list[Finding] = []
    measure: dict[tuple[object, ...], dict[float, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        for figure in record.figures:
            if figure.basis == "actual" and _start(figure.year) >= _start(record.budget_year):
                found.append(
                    Finding(
                        "error",
                        "impossible_actual",
                        (record.id,),
                        f"an actual for {figure.year} in the {record.budget_year} budget: that "
                        "year had not ended",
                    )
                )
            if figure.basis == "revised_estimate" and _start(figure.year) > _start(
                record.budget_year
            ):
                found.append(
                    Finding(
                        "error",
                        "impossible_revised",
                        (record.id,),
                        f"a revised estimate for {figure.year} in the {record.budget_year} budget",
                    )
                )
            key = (
                _name(record.title),
                _name(record.department),
                record.level,
                record.state,
                figure.year,
                figure.basis,
                "percent" if figure.unit == "percent" else "money",
            )
            measure[key][round(_crore(figure), 6)].append(record.id)
    for measured, amounts in measure.items():
        if len(amounts) > 1:
            ids = tuple(dict.fromkeys(i for owners in amounts.values() for i in owners))
            found.append(
                Finding(
                    "error",
                    "figure_conflict",
                    ids,
                    f"{measured[0]!r} {measured[4]} ({measured[5]}) is given as "
                    + " and as ".join(f"{amount:g}" for amount in amounts)
                    + ": the documents must be compared by a person",
                )
            )
    return found
