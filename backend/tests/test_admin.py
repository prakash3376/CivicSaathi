import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.assistant import SourceSummary
from app.domain.catalogue import BudgetRecord, Cite
from app.domain.errors import AssistantError
from app.main import create_app
from app.services.admin.knowledge import build_report, latest_evaluations, sector_health
from app.services.assistant.stats import AssistantStats
from app.services.eligibility.loader import load_schemes
from app.services.eligibility.service import SchemeService
from app.services.ingestion.registry import load_registry
from tests.factories import FakeModel, make_runtime, make_spec
from tests.factories import make_draft as draft
from tests.test_assistant_service import GOOD
from tests.test_search import entry


def source(ident: str, passages: int, **changes: object) -> SourceSummary:
    fields: dict[str, object] = {
        "id": ident,
        "title": f"Title of {ident}",
        "scheme": "Demo",
        "authority": "Department",
        "level": "central",
        "doc_type": "guidelines",
        "format": "pdf",
        "url": f"https://x.gov.in/{ident}.pdf",
        "passages": passages,
        "verification": "verified",
    }
    fields.update(changes)
    return SourceSummary.model_validate(fields)


def budget(ident: str, sector: str | None, source_id: str) -> BudgetRecord:
    return BudgetRecord.model_validate(
        {
            "id": ident,
            "budget_year": "2026-27",
            "level": "central",
            "sector": sector,
            "title": "A budget record",
            "department": "Ministry",
            "source_ids": [source_id],
            "last_verified": "2026-10-31",
            "summary": {"en": "x", "bn": "x", "hi": "x"},
            "statements": [
                {
                    "text": "A statement.",
                    "evidence": [Cite(source_id=source_id, quote="q" * 40).model_dump()],
                }
            ],
        }
    )


ENTRIES = [
    entry("pm-kisan", "PM-KISAN", "farmer income support", "agriculture", "kisan"),
    entry("swasthya", "Swasthya Sathi", "health cover for families", "health", "health-doc"),
    entry("ghost", "Ghost scheme", "a scheme whose document never indexed", "housing", "ghost-doc"),
]


class TestSectorHealth:
    def rows(self) -> dict[str, object]:
        indexed = [
            source("kisan", 40),
            source("health-doc", 12, stale=True, verification_due=True, ocr=True),
            source("budget-doc", 7),
        ]
        records = [budget("b-health", "health", "budget-doc"), budget("b-tax", None, "budget-doc")]
        found = sector_health(schemes=[], entries=ENTRIES, records=records, indexed=indexed)
        return {row.sector: row for row in found}

    def test_every_sector_has_a_row_in_the_order_of_the_home_page(self) -> None:
        assert list(self.rows())[:3] == ["education", "health", "agriculture"]
        assert len(self.rows()) == 12

    def test_a_populated_sector_counts_its_documents_and_passages(self) -> None:
        row = self.rows()["agriculture"]

        assert (row.programmes, row.sources, row.indexed_sources, row.passages) == (1, 1, 1, 40)  # type: ignore[attr-defined]
        assert row.status == "populated"  # type: ignore[attr-defined]

    def test_what_is_old_due_or_scanned_is_counted(self) -> None:
        row = self.rows()["health"]

        assert (row.stale_sources, row.due_sources, row.scanned_sources) == (1, 1, 1)  # type: ignore[attr-defined]
        assert row.budget_records == 1  # type: ignore[attr-defined]
        assert row.passages == 12 + 7  # type: ignore[attr-defined]

    def test_a_sector_whose_document_is_not_indexed_is_incomplete_and_says_which(self) -> None:
        row = self.rows()["housing"]

        assert row.status == "incomplete"  # type: ignore[attr-defined]
        assert row.missing_sources == ["ghost-doc"]  # type: ignore[attr-defined]
        assert row.passages == 0  # type: ignore[attr-defined]

    def test_a_sector_with_nothing_is_empty(self) -> None:
        assert self.rows()["transport"].status == "empty"  # type: ignore[attr-defined]

    def test_the_budget_sector_holds_every_budget_record_including_those_without_a_sector(
        self,
    ) -> None:
        row = self.rows()["budget"]

        assert (row.budget_records, row.status) == (2, "populated")  # type: ignore[attr-defined]

    def test_the_counts_come_from_the_data_and_change_with_it(self) -> None:
        more = [*ENTRIES, entry("pm-two", "Another", "more farmer help", "agriculture", "kisan")]
        found = sector_health(schemes=[], entries=more, records=[], indexed=[source("kisan", 40)])

        assert {r.sector: r.programmes for r in found}["agriculture"] == 2


class TestTheReport:
    def build(self, **changes: object) -> dict[str, object]:
        indexed = [source("kisan", 40), source("old", 5, verification_due=True)]
        arguments: dict[str, object] = {
            "schemes": [],
            "entries": ENTRIES[:1],
            "records": [],
            "specs": [make_spec(id="kisan"), make_spec(id="old"), make_spec(id="never")],
            "indexed": indexed,
            "stats": {"questions": 0},
            "provider": {"configured": True, "model": "m"},
            "evaluations": {},
        }
        arguments.update(changes)
        return build_report(**arguments)  # type: ignore[arg-type]

    def test_it_totals_what_is_registered_indexed_and_searchable(self) -> None:
        totals = self.build()["totals"]

        assert totals["registered_sources"] == 3  # type: ignore[index]
        assert (totals["indexed_sources"], totals["passages"]) == (2, 45)  # type: ignore[index]
        assert totals["verified_sources"] == 2  # type: ignore[index]

    def test_a_registered_source_that_is_not_indexed_is_a_failed_ingestion(self) -> None:
        assert self.build()["failed_ingestion"] == ["never"]

    def test_a_source_due_for_a_new_check_is_listed(self) -> None:
        assert self.build()["needs_new_check"] == ["old"]

    def test_the_last_verification_is_the_latest_one(self) -> None:
        indexed = [
            source("a", 1, verified_at=datetime(2026, 10, 1, tzinfo=UTC)),
            source("b", 1, verified_at=datetime(2026, 10, 30, 9, 0, tzinfo=UTC)),
        ]

        assert (
            self.build(indexed=indexed)["totals"]["last_verified_at"] == "2026-10-30T09:00:00+00:00"
        )  # type: ignore[index]


class TestEvaluations:
    def test_the_latest_run_of_each_strategy_is_summarised(self, tmp_path: Path) -> None:
        (tmp_path / "latest-dense.json").write_text(
            json.dumps(
                {
                    "strategy": "dense",
                    "at": "2026-11-01T10:00:00+00:00",
                    "retrieval": {"overall": {"cases": 10}, "intent_accuracy": 0.9},
                    "answers": None,
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "latest-broken.json").write_text("{not json", encoding="utf-8")

        found = latest_evaluations(tmp_path)

        assert list(found) == ["dense"]
        assert found["dense"]["retrieval"] == {"cases": 10}
        assert found["dense"]["intent_accuracy"] == 0.9

    def test_no_runs_is_not_an_error(self, tmp_path: Path) -> None:
        assert latest_evaluations(tmp_path / "missing") == {}


class TestStats:
    def test_it_counts_outcomes_and_times_and_keeps_recent_failures(self) -> None:
        stats = AssistantStats()
        stats.record("answered", 100.0)
        stats.record("answered", 300.0)
        stats.record("error", 50.0, failure="llm_busy")

        snapshot = stats.snapshot()

        assert snapshot["questions"] == 3
        assert snapshot["outcomes"] == {"answered": 2, "error": 1}
        assert snapshot["mean_ms"] == 150.0
        assert [f["code"] for f in snapshot["recent_failures"]] == ["llm_busy"]  # type: ignore[attr-defined]

    def test_an_empty_history_has_no_averages(self) -> None:
        assert AssistantStats().snapshot()["mean_ms"] is None

    def test_the_service_counts_each_question_and_never_keeps_what_was_asked(
        self, tmp_path: Path
    ) -> None:
        runtime = make_runtime(tmp_path, FakeModel(draft(GOOD)))

        runtime.service.ask("What is the family income ceiling for the scholarship?")
        busy = make_runtime(tmp_path / "b", FakeModel(AssistantError("busy", code="llm_busy")))
        busy.service.ask("What is the family income ceiling for the scholarship?")
        with pytest.raises(AssistantError):
            make_runtime(tmp_path / "c", None).service.ask("What is the income ceiling?")

        assert runtime.service.stats.snapshot()["outcomes"] == {"answered": 1}
        assert busy.service.stats.snapshot()["outcomes"] == {"fallback": 1}
        assert "ceiling" not in json.dumps(runtime.service.stats.snapshot())


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, app_env="test", log_level="WARNING", admin_token="s3cret")
    book = load_schemes(sources={spec.id: spec.url for spec in load_registry()})
    runtime = make_runtime(tmp_path, FakeModel(draft(GOOD)))
    app = create_app(settings, assistant=runtime, schemes=SchemeService(book))
    with TestClient(app) as test_client:
        yield test_client


class TestTheAdminPage:
    URL = "/api/v1/admin/knowledge"

    def test_without_the_token_it_is_refused(self, client: TestClient) -> None:
        response = client.get(self.URL)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "admin_denied"

    def test_with_the_wrong_token_it_is_refused(self, client: TestClient) -> None:
        assert client.get(self.URL, headers={"X-Admin-Token": "nope"}).status_code == 401

    def test_with_the_token_it_shows_every_sector_from_the_real_data(
        self, client: TestClient
    ) -> None:
        response = client.get(self.URL, headers={"X-Admin-Token": "s3cret"})

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert len(body["sectors"]) == 12
        education = next(s for s in body["sectors"] if s["sector"] == "education")
        assert education["schemes"] == 2
        assert body["provider"] == {"configured": False, "model": "gemini-3.6-flash"}
        assert body["totals"]["registered_sources"] >= 4

    def test_without_a_token_configured_the_page_does_not_exist(self, tmp_path: Path) -> None:
        settings = Settings(_env_file=None, app_env="test", log_level="WARNING")
        runtime = make_runtime(tmp_path, FakeModel(draft(GOOD)))
        with TestClient(create_app(settings, assistant=runtime)) as plain:
            response = plain.get(self.URL, headers={"X-Admin-Token": "anything"})

        assert response.status_code == 404

    def test_the_token_is_never_in_a_response(self, client: TestClient) -> None:
        text = client.get(self.URL, headers={"X-Admin-Token": "s3cret"}).text

        assert "s3cret" not in text


class TestTheOperationalNumbers:
    def test_the_share_of_questions_that_fell_back_or_failed_is_reported(self) -> None:
        stats = AssistantStats()
        assert stats.snapshot()["fallback_rate"] is None  # no questions: no rate, not a zero

        for outcome in ("answered", "answered", "fallback", "error"):
            stats.record(outcome, 10.0)

        snapshot = stats.snapshot()
        assert snapshot["fallback_rate"] == 0.25
        assert snapshot["error_rate"] == 0.25

    def test_a_failure_the_visitor_never_saw_is_still_listed_for_the_operator(self) -> None:
        stats = AssistantStats()
        stats.record("fallback", 10.0)
        stats.note_failure("llm_auth")

        assert [f["code"] for f in stats.snapshot()["recent_failures"]] == ["llm_auth"]  # type: ignore[attr-defined]

    def test_how_often_verification_removed_what_the_model_wrote_is_reported(self) -> None:
        from app.services.assistant.trace import Trace, TraceLog

        log = TraceLog()
        assert log.summary()["claims_removed_rate"] is None
        log.add(Trace(outcome="answered", claims_removed=True))
        log.add(Trace(outcome="answered"))
        log.add(Trace(outcome="fallback"))  # not an answer: not counted in the rate

        assert log.summary() == {
            "traces": 3,
            "answered": 2,
            "answers_with_claims_removed": 1,
            "claims_removed_rate": 0.5,
        }
