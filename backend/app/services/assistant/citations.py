"""Turning checked claims into what the user sees: citations to open, and warnings about sources.

Every distinct quote is its own citation, even when two quotes come from the same passage, so
that tapping a number highlights exactly the words that claim rests on (SPEC section 5, "Citation
grounding"). Two claims that rest on the same words share one number.
"""

from collections.abc import Collection, Sequence
from datetime import datetime

from app.domain.assistant import (
    AnswerClaim,
    AnswerWarning,
    Citation,
    Highlight,
    Language,
)
from app.services.assistant.freshness import assess
from app.services.assistant.messages import say
from app.services.grounding.verify import Support, VerifiedClaim


def build_citations(
    claims: Sequence[VerifiedClaim], now: datetime
) -> tuple[list[AnswerClaim], list[Citation]]:
    """The claims with the numbers of their citations, and the citations, numbered from 1."""
    numbered: dict[tuple[str, tuple[tuple[int, int], ...]], int] = {}
    citations: list[Citation] = []
    answer_claims: list[AnswerClaim] = []
    for claim in claims:
        numbers: list[int] = []
        for support in claim.support:
            key = (support.passage.chunk_id, support.located.spans)
            if key not in numbered:
                numbered[key] = len(citations) + 1
                citations.append(_citation(numbered[key], support, now))
            if numbered[key] not in numbers:
                numbers.append(numbered[key])
        answer_claims.append(AnswerClaim(text=claim.statement, citations=numbers))
    return answer_claims, citations


def _citation(number: int, support: Support, now: datetime) -> Citation:
    passage = support.passage
    freshness = assess(passage.document_date, passage.verified_at, now)
    return Citation(
        number=number,
        source_id=passage.source_id,
        title=passage.title,
        authority=passage.authority,
        url=passage.url,
        page_start=passage.page_start,
        page_end=passage.page_end,
        section=passage.section,
        clause=passage.clause,
        passage=passage.text,
        quote=support.quote,
        language=passage.language,
        highlights=[Highlight(start=start, end=end) for start, end in support.located.spans],
        document_date=passage.document_date,
        date_source=passage.date_source,
        verified_at=passage.verified_at,
        verification=passage.verification,
        age_days=freshness.age_days,
        stale=freshness.stale,
        ocr=passage.ocr,
    )


def warning(language: Language, code: str, *source_ids: str, **fields: str) -> AnswerWarning:
    """A warning whose text is the fixed message ``warn_<code>`` of the language."""
    return AnswerWarning(
        code=code, message=say(language, f"warn_{code}", **fields), source_ids=list(source_ids)
    )


def source_warnings(
    citations: Sequence[Citation],
    language: Language,
    now: datetime,
    *,
    sanitized_sources: Collection[str] = (),
) -> list[AnswerWarning]:
    """What to tell the user about the freshness and reliability of the sources they were shown.

    Rule R4: the effective date and the last verification are always shown with a citation; this
    adds a warning when a document is older than twelve months, has no readable date, is due for a
    new check, or was read from a scan. A source gets each warning once, however often it is cited.
    """
    first_citation: dict[str, Citation] = {}
    scanned: set[str] = set()
    for citation in citations:
        first_citation.setdefault(citation.source_id, citation)
        if citation.ocr:
            scanned.add(citation.source_id)

    warnings: list[AnswerWarning] = []
    for source_id, citation in first_citation.items():
        freshness = assess(citation.document_date, citation.verified_at, now)
        title = citation.title
        if citation.document_date is None:
            warnings.append(warning(language, "date_unknown", source_id, title=title))
        elif freshness.stale:
            date = citation.document_date.isoformat()
            warnings.append(warning(language, "stale", source_id, title=title, date=date))
        if freshness.verification_due and citation.verified_at is not None:
            date = citation.verified_at.date().isoformat()
            warnings.append(
                warning(language, "verification_due", source_id, title=title, date=date)
            )
        if source_id in scanned:
            warnings.append(warning(language, "scanned", source_id, title=title))
        if source_id in sanitized_sources:
            warnings.append(warning(language, "sanitized", source_id, title=title))
    return warnings
