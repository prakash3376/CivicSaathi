"""Checking that the quotes behind every rule are really in the official documents.

Loading the rules (``loader.py``) checks that a rule's figures match its quote. This checks the
other half: that the quote is there, word for word, in the document that was indexed. A rule
whose source has changed under it, or a quote copied wrongly, is found here and not by a citizen.
"""

from collections.abc import Callable, Iterator

from app.domain.eligibility import Evidence, Scheme
from app.services.eligibility.loader import SchemeBook
from app.services.grounding.text import Squashed, find_quote, squash


def all_evidence(scheme: Scheme) -> Iterator[tuple[str, Evidence]]:
    """Every quote a scheme relies on, with a label saying what for."""
    for criterion in (*scheme.criteria, *(c for t in scheme.tracks for c in t.criteria)):
        for item in criterion.evidence:
            yield f"criterion {criterion.id}", item
    for document in (*scheme.documents, *(d for t in scheme.tracks for d in t.documents)):
        for item in document.evidence:
            yield f"document {document.id}", item
    for caveat in (*scheme.caveats, *(c for t in scheme.tracks for c in t.caveats)):
        for item in caveat.evidence:
            yield f"caveat {caveat.id}", item
    for step in scheme.steps:
        for item in step.evidence:
            yield f"step {step.id}", item
    for contact in scheme.contacts:
        for item in contact.evidence:
            yield f"contact {contact.id}", item
    for deadline in scheme.deadlines:
        for item in deadline.evidence:
            yield f"deadline {deadline.id}", item
    for track in scheme.tracks:
        for item in track.benefit.evidence:
            yield f"benefit of {track.id}", item
    for item in scheme.apply.evidence:
        yield "apply", item


def check_evidence(book: SchemeBook, source_text: Callable[[str], str | None]) -> list[str]:
    """What is wrong: a quote missing from its document, or a document that is not indexed.

    ``source_text`` returns the text of an indexed source, or None if it is not indexed.
    """
    problems: list[str] = []
    documents: dict[str, Squashed | None] = {}
    for scheme in book.schemes:
        for label, evidence in all_evidence(scheme):
            if evidence.source_id not in documents:
                text = source_text(evidence.source_id)
                documents[evidence.source_id] = squash(text) if text is not None else None
            document = documents[evidence.source_id]
            if document is None:
                problems.append(f"{scheme.id}: {label}: '{evidence.source_id}' is not indexed")
            elif find_quote(evidence.quote, document) is None:
                problems.append(
                    f"{scheme.id}: {label}: not found in {evidence.source_id}: "
                    f"{evidence.quote[:70]!r}"
                )
    return problems
