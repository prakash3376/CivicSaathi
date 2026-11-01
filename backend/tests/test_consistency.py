"""Records that disagree with each other: found, named, and never settled by guessing."""

from datetime import date
from typing import Any

from app.core.config import BUDGET_DIR, CATALOGUE_DIR
from app.domain.catalogue import BudgetRecord, Entry
from app.services.catalogue.consistency import check_consistency
from app.services.catalogue.loader import load_budget, load_catalogue
from app.services.ingestion.registry import load_registry

TODAY = date(2026, 11, 1)
QUOTE = {"source_id": "doc", "quote": "x" * 40}


def entry(ident: str, name: str = "PM Demo Scheme", **changes: Any) -> Entry:
    fields: dict[str, Any] = {
        "id": ident,
        "name": name,
        "sectors": ["agriculture"],
        "level": "central",
        "department": "Department of Demos",
        "source_ids": ["doc"],
        "last_verified": "2026-10-31",
        "summary": {"en": "x", "bn": "x", "hi": "x"},
        "target": {"en": "x", "bn": "x", "hi": "x"},
        "benefits": [{"text": "A benefit.", "evidence": [QUOTE]}],
        "apply": {"label": "Portal", "url": "https://demo.gov.in"},
    }
    return Entry.model_validate({**fields, **changes})


def figure(year: str, basis: str, amount: float, unit: str = "crore") -> dict[str, Any]:
    return {"year": year, "basis": basis, "amount": amount, "unit": unit, "evidence": [QUOTE]}


def record(ident: str, figures: list[dict[str, Any]], **changes: Any) -> BudgetRecord:
    fields: dict[str, Any] = {
        "id": ident,
        "budget_year": "2026-27",
        "level": "central",
        "sector": "agriculture",
        "title": "Allocation for Demo",
        "department": "Ministry of Demos",
        "source_ids": ["doc"],
        "last_verified": "2026-10-31",
        "summary": {"en": "x", "bn": "x", "hi": "x"},
        "figures": figures,
    }
    return BudgetRecord.model_validate({**fields, **changes})


def codes(entries: list[Entry] = (), records: list[BudgetRecord] = ()) -> list[str]:  # type: ignore[assignment]
    return [f.code for f in check_consistency(entries, records, today=TODAY)]


class TestDuplicates:
    def test_one_programme_under_two_ids_is_an_error(self) -> None:
        found = check_consistency(
            [entry("pm-demo"), entry("pm-demo-2", name="  PM  demo SCHEME ")], [], today=TODAY
        )

        assert [(f.severity, f.code, f.ids) for f in found] == [
            ("error", "duplicate_entry", ("pm-demo", "pm-demo-2"))
        ]

    def test_the_same_name_in_another_state_is_a_different_programme(self) -> None:
        a = entry("a-scheme", level="state", state="West Bengal")
        b = entry("b-scheme", level="state", state="Bihar")

        assert codes([a, b]) == []

    def test_a_central_and_a_state_programme_of_the_same_name_are_different(self) -> None:
        assert codes([entry("a-scheme"), entry("b-scheme", level="state", state="Bihar")]) == []


class TestFigures:
    def test_two_amounts_for_one_measure_year_and_basis_conflict(self) -> None:
        a = record("a-record", [figure("2026-27", "budget_estimate", 1000)])
        b = record("b-record", [figure("2026-27", "budget_estimate", 1200)])

        found = check_consistency([], [a, b], today=TODAY)

        assert [(f.code, f.ids) for f in found] == [("figure_conflict", ("a-record", "b-record"))]
        assert "1000" in found[0].detail
        assert "1200" in found[0].detail  # both are named: neither is chosen

    def test_estimates_and_actuals_are_expected_to_differ(self) -> None:
        rec = record(
            "a-record",
            [
                figure("2024-25", "actual", 900),
                figure("2025-26", "revised_estimate", 950),
                figure("2026-27", "budget_estimate", 1000),
                figure("2025-26", "budget_estimate", 1100),  # BE and RE of one year differ: normal
            ],
        )

        assert codes(records=[rec]) == []

    def test_the_same_amount_in_two_units_is_not_a_conflict(self) -> None:
        a = record("a-record", [figure("2026-27", "budget_estimate", 1, "lakh_crore")])
        b = record("b-record", [figure("2026-27", "budget_estimate", 100000, "crore")])

        assert codes(records=[a, b]) == []

    def test_the_same_amount_stated_twice_is_not_a_conflict(self) -> None:
        a = record("a-record", [figure("2026-27", "budget_estimate", 1000)])
        b = record("b-record", [figure("2026-27", "budget_estimate", 1000)])

        assert codes(records=[a, b]) == []

    def test_a_percent_is_never_compared_with_money(self) -> None:
        a = record("a-record", [figure("2026-27", "budget_estimate", 5, "percent")])
        b = record("b-record", [figure("2026-27", "budget_estimate", 5000)])

        assert codes(records=[a, b]) == []

    def test_different_departments_or_years_are_different_measures(self) -> None:
        a = record("a-record", [figure("2026-27", "budget_estimate", 1000)])
        b = record("b-record", [figure("2026-27", "budget_estimate", 2000)], department="Other")
        c = record("c-record", [figure("2027-28", "budget_estimate", 3000)])

        assert codes(records=[a, b, c]) == []

    def test_an_actual_for_a_year_that_had_not_ended_is_impossible(self) -> None:
        rec = record("a-record", [figure("2026-27", "actual", 1000)])

        assert codes(records=[rec]) == ["impossible_actual"]

    def test_an_actual_for_the_budget_year_or_a_later_one_is_impossible(self) -> None:
        same = record("a-record", [figure("2026-27", "actual", 1)], budget_year="2026-27")
        later = record("b-record", [figure("2027-28", "actual", 1)], budget_year="2026-27")

        assert codes(records=[same, later]) == ["impossible_actual", "impossible_actual"]

    def test_an_actual_for_an_earlier_year_is_what_a_budget_reports(self) -> None:
        rec = record("a-record", [figure("2024-25", "actual", 1)], budget_year="2026-27")

        assert codes(records=[rec]) == []

    def test_a_revised_estimate_for_a_later_year_is_impossible(self) -> None:
        rec = record("a-record", [figure("2027-28", "revised_estimate", 1000)])

        assert codes(records=[rec]) == ["impossible_revised"]


class TestDates:
    def test_a_check_dated_in_the_future_is_an_error(self) -> None:
        assert codes([entry("a-scheme", last_verified="2026-12-01")]) == ["verified_in_future"]
        assert codes(records=[record("a-record", [], last_verified="2026-12-01")]) == [
            "verified_in_future"
        ]

    def test_a_document_published_after_it_was_checked_is_an_error(self) -> None:
        found = codes([entry("a-scheme", published_on="2026-10-31", last_verified="2026-10-01")])

        assert found == ["published_after_verified"]

    def test_the_dates_are_kept_apart_an_old_document_checked_today_is_fine(self) -> None:
        old = entry(
            "a-scheme",
            published_on="2019-03-01",
            effective_on="2019-04-01",
            last_verified="2026-10-31",
        )

        assert codes([old]) == []
        assert old.published_on != old.last_verified  # never one standing in for the other


class TestTheRealData:
    def test_the_shipped_catalogue_and_budget_agree_with_themselves(self) -> None:
        urls = {spec.id: spec.url for spec in load_registry()}
        entries = load_catalogue(CATALOGUE_DIR, sources=urls)
        records = load_budget(BUDGET_DIR, sources=urls)

        found = check_consistency(entries, records, today=TODAY)

        assert [str(f) for f in found] == []
