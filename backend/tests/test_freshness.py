from datetime import UTC, date, datetime, timedelta

from app.services.assistant.freshness import VERIFICATION_DUE_AFTER, assess
from tests.factories import NOW

TODAY = NOW.date()


class TestDocumentAge:
    def test_a_recent_document_is_current(self) -> None:
        result = assess(TODAY - timedelta(days=40), NOW, NOW)

        assert result.age_days == 40
        assert not result.stale

    def test_a_document_is_stale_only_after_twelve_months(self) -> None:
        assert not assess(TODAY - timedelta(days=365), NOW, NOW).stale
        assert assess(TODAY - timedelta(days=366), NOW, NOW).stale  # SPEC rule R4

    def test_a_document_with_no_date_is_neither_stale_nor_dated(self) -> None:
        result = assess(None, NOW, NOW)

        assert result.age_days is None
        assert not result.stale

    def test_a_date_in_the_future_is_not_a_negative_age(self) -> None:
        assert assess(date(2027, 1, 1), NOW, NOW).age_days == 0


class TestVerificationAge:
    def test_a_recent_verification_is_not_due(self) -> None:
        assert not assess(None, NOW - timedelta(days=3), NOW).verification_due

    def test_a_verification_is_due_after_thirty_days(self) -> None:
        assert not assess(None, NOW - VERIFICATION_DUE_AFTER, NOW).verification_due
        assert assess(
            None, NOW - VERIFICATION_DUE_AFTER - timedelta(seconds=1), NOW
        ).verification_due

    def test_a_source_never_verified_is_due(self) -> None:
        assert assess(None, None, NOW).verification_due

    def test_a_time_without_a_zone_is_taken_as_utc(self) -> None:
        naive = datetime(2026, 10, 30, 12, 0)  # no time zone: that is the point of the test

        assert not assess(None, naive, NOW).verification_due
        assert naive.tzinfo is None
        assert assess(None, naive.replace(tzinfo=UTC), NOW) == assess(None, naive, NOW)
