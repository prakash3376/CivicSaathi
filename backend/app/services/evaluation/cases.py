"""The benchmark questions and where their answers are.

Two kinds, both pointing at evidence that was already checked against the real documents:

* **Handwritten** (``data/eval/questions.toml``): colloquial, Hindi and Bengali, cross-sector,
  follow-up and adversarial questions. Each names the catalogue entries or the sources that hold
  the answer, never the answer itself. A question with ``hi`` or ``bn`` is run in each language.
* **Derived** from the catalogue and the budget records: "What does X give?" and "Who is eligible
  for X?", where the evidence is the very quotes that ``catalogue-check`` found in the documents.

The derived questions name the scheme, so they are the easy half; the handwritten ones are the
test of whether a citizen's own words find the right document.
"""

import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.domain.catalogue import BudgetRecord, Cite, Entry, Statement

Language = Literal["en", "hi", "bn"]
LANGUAGES: tuple[Language, ...] = ("en", "hi", "bn")
MAX_DERIVED_BUDGET = 16


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    question: str
    language: Language = "en"
    intent: str | None = None
    sector: str | None = None
    history: tuple[str, ...] = ()
    sources: frozenset[str] = frozenset()  # a passage of any of these documents is evidence
    quotes: tuple[Cite, ...] = ()  # a passage that holds any of these words is the evidence
    answerable: bool = True
    origin: Literal["handwritten", "derived"] = "handwritten"
    extras: dict[str, Any] = field(default_factory=dict, compare=False)


def _statements(entry: Entry) -> Iterator[Statement]:
    yield from entry.benefits
    yield from entry.eligibility
    yield from entry.exclusions
    yield from entry.documents
    yield from entry.steps


def load_cases(
    entries: Sequence[Entry], records: Sequence[BudgetRecord], directory: Path
) -> list[Case]:
    by_id = {entry.id: entry for entry in entries}
    cases = [*_handwritten(directory / "questions.toml", by_id), *_derived(entries, records)]
    ids = [case.id for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("two benchmark cases have the same id")
    return cases


def _handwritten(path: Path, by_id: dict[str, Entry]) -> list[Case]:
    if not path.exists():
        return []
    cases: list[Case] = []
    for raw in tomllib.loads(path.read_text(encoding="utf-8")).get("cases", []):
        listed = [by_id[i] for i in raw.get("entries", []) if i in by_id]
        missing = [i for i in raw.get("entries", []) if i not in by_id]
        if missing:
            raise ValueError(f"case {raw['id']}: unknown entries {missing}")
        sources = frozenset(raw.get("sources", [])) | frozenset(
            s for entry in listed for s in entry.source_ids
        )
        quotes = tuple(c for entry in listed for st in _statements(entry) for c in st.evidence)
        sector = listed[0].sectors[0] if listed else raw.get("sector")
        answerable = bool(raw.get("answerable", True))
        if answerable and not sources:
            raise ValueError(f"case {raw['id']}: an answerable case needs entries or sources")
        for language in LANGUAGES:
            text = raw["question"] if language == "en" else raw.get(language)
            if not text:
                continue
            cases.append(
                Case(
                    id=raw["id"] if language == "en" else f"{raw['id']}.{language}",
                    group="multilingual" if language != "en" else raw["group"],
                    question=text,
                    language=language,
                    intent=raw.get("intent"),
                    sector=sector,
                    history=tuple(raw.get("history", [])),
                    sources=sources,
                    quotes=quotes,
                    answerable=answerable,
                    extras={"base": raw["id"], "kind": raw["group"]},
                )
            )
    return cases


def _derived(entries: Sequence[Entry], records: Sequence[BudgetRecord]) -> list[Case]:
    cases: list[Case] = []
    for entry in entries:
        sources = frozenset(entry.source_ids)
        sector = entry.sectors[0]
        benefit_quotes = tuple(c for st in entry.benefits[:2] for c in st.evidence)
        cases.append(
            Case(
                id=f"derived.benefit.{entry.id}",
                group="factual",
                question=f"What does {entry.name} give?",
                intent="scheme_information",
                sector=sector,
                sources=sources,
                quotes=benefit_quotes,
                origin="derived",
            )
        )
        who = entry.eligibility[:2] or entry.exclusions[:2]
        if who:
            cases.append(
                Case(
                    id=f"derived.who.{entry.id}",
                    group="eligibility",
                    question=(
                        f"Who is eligible for {entry.name}?"
                        if entry.eligibility
                        else f"Who cannot get {entry.name}?"
                    ),
                    intent="eligibility",
                    sector=sector,
                    sources=sources,
                    quotes=tuple(c for st in who for c in st.evidence),
                    origin="derived",
                )
            )
    with_figures = [r for r in records if r.figures]
    step = max(1, len(with_figures) // MAX_DERIVED_BUDGET)
    for record in with_figures[::step][:MAX_DERIVED_BUDGET]:
        cases.append(
            Case(
                id=f"derived.budget.{record.id}",
                group="numeric",
                question=f"What does the budget say about: {record.title}?",
                intent="budget",
                sector=record.sector or "budget",
                sources=frozenset(record.source_ids),
                quotes=tuple(c for fig in record.figures[:2] for c in fig.evidence),
                origin="derived",
            )
        )
    return cases
