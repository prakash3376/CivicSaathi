"""How current a source is, for SPEC rule R4: show when it was verified and warn about age.

Two different things go stale. The *document* has a date, and one older than twelve months may
have been replaced; the *verification* has a date too, and one that is old means nobody has
re-checked that the document still says what we indexed. A source whose date could not be read is
not called stale, because that would be a guess, but it is not called fresh either: the user is
told the date is unknown.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.services.ingestion.verification import STALE_AFTER

VERIFICATION_DUE_AFTER = timedelta(days=30)


@dataclass(frozen=True)
class Freshness:
    age_days: int | None  # None when the document carries no date we could read
    stale: bool
    verification_due: bool


def assess(document_date: date | None, verified_at: datetime | None, now: datetime) -> Freshness:
    """``now`` must carry a time zone; a ``verified_at`` without one is taken to be UTC."""
    age_days = max((now.date() - document_date).days, 0) if document_date else None
    if verified_at is not None and verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=UTC)
    return Freshness(
        age_days=age_days,
        stale=age_days is not None and age_days > STALE_AFTER.days,
        verification_due=verified_at is None or now - verified_at > VERIFICATION_DUE_AFTER,
    )
