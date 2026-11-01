"""Checking that the quotes behind every catalogue and budget record are in the documents.

Loading (``loader.py``) checks that a statement's figures match its quote. This checks the other
half: that the quote is there, word for word, in the document that was indexed.
"""

from collections.abc import Callable, Iterator, Sequence

from app.domain.catalogue import BudgetRecord, Cite, Entry
from app.services.grounding.text import Squashed, find_quote, squash


def entry_cites(entry: Entry) -> Iterator[tuple[str, Cite]]:
    """Every quote an entry relies on, with a label saying what for."""
    for group, statements in (
        ("benefit", entry.benefits),
        ("eligibility", entry.eligibility),
        ("exclusion", entry.exclusions),
        ("document", entry.documents),
        ("step", entry.steps),
    ):
        for number, statement in enumerate(statements, start=1):
            for cite in statement.evidence:
                yield f"{group} {number}", cite
    for cite in entry.apply.evidence:
        yield "apply", cite


def budget_cites(record: BudgetRecord) -> Iterator[tuple[str, Cite]]:
    for number, figure in enumerate(record.figures, start=1):
        for cite in figure.evidence:
            yield f"figure {number}", cite
    for number, statement in enumerate(record.statements, start=1):
        for cite in statement.evidence:
            yield f"statement {number}", cite


def check_cites(
    labelled: Sequence[tuple[str, str, Cite]], source_text: Callable[[str], str | None]
) -> list[str]:
    """What is wrong: a quote missing from its document, or a document that is not indexed.

    ``labelled`` is (record id, what for, quote). ``source_text`` returns the text of a source, or
    None if it is not available.
    """
    problems: list[str] = []
    documents: dict[str, Squashed | None] = {}
    for ident, label, cite in labelled:
        if cite.source_id not in documents:
            text = source_text(cite.source_id)
            documents[cite.source_id] = squash(text) if text is not None else None
        document = documents[cite.source_id]
        if document is None:
            problems.append(f"{ident}: {label}: '{cite.source_id}' is not indexed")
        elif find_quote(cite.quote, document) is None:
            problems.append(f"{ident}: {label}: not found in {cite.source_id}: {cite.quote[:70]!r}")
    return problems


def all_labelled(
    entries: Sequence[Entry], records: Sequence[BudgetRecord]
) -> list[tuple[str, str, Cite]]:
    found = [(e.id, label, cite) for e in entries for label, cite in entry_cites(e)]
    found += [(r.id, label, cite) for r in records for label, cite in budget_cites(r)]
    return found
