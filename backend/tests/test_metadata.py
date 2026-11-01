from datetime import UTC, date, datetime

import pytest

from app.services.retrieval.metadata import parse_date, parse_datetime, parse_page


@pytest.mark.parametrize(
    ("value", "expected"), [(3, 3), ("3", 3), (0, None), ("", None), (None, None)]
)
def test_a_page_of_zero_or_nothing_means_there_are_no_pages(
    value: object, expected: int | None
) -> None:
    assert parse_page(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-06-01", date(2026, 6, 1)),
        ("", None),
        (None, None),
        ("01/06/2026", None),
        ("2026-13-45", None),
        ("garbage", None),
    ],
)
def test_a_date_that_cannot_be_read_is_none_not_an_error(
    value: object, expected: date | None
) -> None:
    assert parse_date(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-30T09:00:00+00:00", datetime(2026, 10, 30, 9, 0, tzinfo=UTC)),
        ("2026-10-30T09:00:00", datetime(2026, 10, 30, 9, 0)),
        ("", None),
        (None, None),
        ("yesterday", None),
    ],
)
def test_a_time_that_cannot_be_read_is_none_not_an_error(
    value: object, expected: datetime | None
) -> None:
    assert parse_datetime(value) == expected
