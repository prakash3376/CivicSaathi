"""What the assistant can answer from, and how current each source is (SPEC rule R4).

This is the list a user sees before asking anything: which official documents are indexed, when
each is dated, when it was last verified, and whether it is old or due for a new check. Showing it
up front is the other half of the warnings that come with an answer.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from app.domain.assistant import SourceSummary
from app.domain.sources import SourceSpec
from app.services.assistant.freshness import assess
from app.services.retrieval.metadata import parse_date, parse_datetime
from app.services.retrieval.store import VectorStore


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SourceCatalog:
    def __init__(
        self,
        store: VectorStore,
        specs: Sequence[SourceSpec],
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._store = store
        self._specs = {spec.id: spec for spec in specs}
        self._clock = clock

    def sources(self) -> list[SourceSummary]:
        """Every indexed source, ordered by id. Sources that are registered but not indexed are
        left out: there is nothing to answer from yet."""
        now = self._clock()
        summaries: list[SourceSummary] = []
        for indexed in self._store.sources():
            metadata = indexed.metadata
            spec = self._specs.get(indexed.id)
            url = str(metadata.get("url", ""))
            document_date = parse_date(metadata.get("document_date"))
            verified_at = parse_datetime(metadata.get("verified_at"))
            freshness = assess(document_date, verified_at, now)
            summaries.append(
                SourceSummary(
                    id=indexed.id,
                    title=str(metadata.get("title", indexed.id)),
                    scheme=str(metadata.get("scheme", "")),
                    authority=str(metadata.get("authority", "")),
                    level=str(metadata.get("level", "")),
                    state=str(metadata.get("state") or "") or None,
                    doc_type=str(metadata.get("doc_type", "")),
                    format=spec.format
                    if spec
                    else ("pdf" if url.lower().endswith(".pdf") else "html"),
                    url=url,
                    passages=indexed.passages,
                    document_date=document_date,
                    date_source=str(metadata.get("date_source") or "") or None,
                    verified_at=verified_at,
                    verification=str(metadata.get("verification", "")),
                    age_days=freshness.age_days,
                    stale=freshness.stale,
                    verification_due=freshness.verification_due,
                    ocr=bool(metadata.get("ocr", False)),
                )
            )
        return summaries
