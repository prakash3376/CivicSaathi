"""Reading back the metadata the ingestion pipeline stored with each passage.

The index keeps only strings, numbers and booleans, so a missing date is an empty string and a web
page, which has no pages, has page 0. These turn those back into values, and a value that cannot
be read is None rather than an error: a stale or odd record must not stop an answer.
"""

from datetime import date, datetime
from typing import Any


def parse_page(value: Any) -> int | None:
    return int(value) if value else None


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
