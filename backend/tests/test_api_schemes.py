import logging
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.errors import SchemeDataError
from app.main import create_app
from app.services.eligibility.loader import load_schemes
from app.services.eligibility.service import SchemeService
from app.services.ingestion.registry import load_registry

SCHEMES = "/api/v1/schemes"
PRAGATI = {
    "gender": "female",
    "girls_in_family": 1,
    "family_income": 500000,
    "receives_other_scholarship": False,
    "institution_aicte_approved": True,
    "admission_type": "first_year",
}


@pytest.fixture(scope="module")
def service() -> SchemeService:
    book = load_schemes(sources={spec.id: spec.url for spec in load_registry()})
    return SchemeService(book, clock=lambda: date(2026, 10, 20))


@pytest.fixture
def client(settings: Settings, service: SchemeService) -> Iterator[TestClient]:
    with TestClient(create_app(settings, schemes=service)) as test_client:
        yield test_client


def check(client: TestClient, scheme: str = "aicte-pragati", **body: Any) -> Any:
    body.setdefault("track", "degree")
    return client.post(f"{SCHEMES}/{scheme}/eligibility", json=body)


class TestCatalogue:
    def test_lists_the_schemes_with_their_tracks_and_deadline(self, client: TestClient) -> None:
        response = client.get(SCHEMES)

        assert response.status_code == 200
        schemes = {s["id"]: s for s in response.json()["schemes"]}
        assert set(schemes) == {"aicte-pragati", "svmcm"}
        assert [t["id"] for t in schemes["aicte-pragati"]["tracks"]] == ["degree", "diploma"]
        assert schemes["aicte-pragati"]["deadline"]["status"] == "open"
        assert schemes["aicte-pragati"]["deadline"]["days_left"] == 11
        assert schemes["svmcm"]["deadline"] is None

    def test_texts_come_in_both_languages(self, client: TestClient) -> None:
        scheme = client.get(SCHEMES).json()["schemes"][0]

        assert scheme["name"]  # a proper name, the same in both languages
        assert scheme["summary"]["en"]
        assert scheme["summary"]["bn"]

    def test_a_kept_copy_must_be_checked_every_time_because_a_deadline_depends_on_the_date(
        self, client: TestClient
    ) -> None:
        response = client.get(SCHEMES)

        assert response.headers["cache-control"] == "no-cache"
        assert (
            client.get(SCHEMES, headers={"If-None-Match": response.headers["etag"]}).status_code
            == 304
        )

    def test_the_same_list_on_a_later_day_has_a_new_hash_so_no_stale_deadline_is_kept(
        self, settings: Settings
    ) -> None:
        book = load_schemes(sources={spec.id: spec.url for spec in load_registry()})
        etags = []
        for today in (date(2026, 10, 20), date(2026, 10, 21)):
            service = SchemeService(book, clock=lambda today=today: today)
            with TestClient(create_app(settings, schemes=service)) as http:
                etags.append(http.get(SCHEMES).headers["etag"])

        assert etags[0] != etags[1]  # "11 days left" became "10 days left"


class TestDetails:
    def test_a_scheme_in_detail(self, client: TestClient) -> None:
        response = client.get(f"{SCHEMES}/svmcm")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "svmcm"
        ug = next(t for t in body["tracks"] if t["id"] == "ug")
        assert [c["id"] for c in ug["criteria"]] == [
            "in_west_bengal",
            "no_other_scholarship",
            "income",
            "marks",
        ]
        assert all(c["evidence"][0]["quote"] for c in ug["criteria"])
        assert ug["questions"][0]["field"] == "institution_in_west_bengal"
        assert body["not_stated"]

    def test_an_unknown_scheme_is_a_404_in_the_error_envelope(self, client: TestClient) -> None:
        response = client.get(f"{SCHEMES}/ghost")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "scheme_not_found"


class TestEligibility:
    def test_an_eligible_profile(self, client: TestClient) -> None:
        response = check(client, answers=PRAGATI)

        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "eligible"
        assert body["unanswered"] == []
        assert all(c["status"] == "met" for c in body["criteria"])
        assert body["checklist"]["documents"]
        assert body["disclaimer"]["en"].startswith("Informational summary, not legal advice")

    def test_the_income_boundary(self, client: TestClient) -> None:
        body = check(client, answers={**PRAGATI, "family_income": 800000}).json()

        assert body["outcome"] == "not_eligible"
        income = next(c for c in body["criteria"] if c["id"] == "income")
        assert income["status"] == "not_met"
        assert income["answer_text"]["en"] == "Rs 8,00,000 a year"

    def test_a_skipped_question_needs_more_info(self, client: TestClient) -> None:
        answers = {k: v for k, v in PRAGATI.items() if k != "family_income"}

        body = check(client, answers=answers).json()

        assert body["outcome"] == "need_more_info"
        assert body["unanswered"] == ["family_income"]

    def test_null_is_a_skipped_question_too(self, client: TestClient) -> None:
        body = check(client, answers={**PRAGATI, "family_income": None}).json()

        assert body["outcome"] == "need_more_info"

    def test_no_answers_at_all_is_allowed(self, client: TestClient) -> None:
        assert check(client).json()["outcome"] == "need_more_info"

    def test_the_response_describes_one_person_and_is_never_cached(
        self, client: TestClient
    ) -> None:
        response = check(client, answers=PRAGATI)

        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-request-id"]

    def test_the_same_answers_give_the_same_response(self, client: TestClient) -> None:
        assert check(client, answers=PRAGATI).json() == check(client, answers=PRAGATI).json()


class TestRefusals:
    SECRET = "SECRET-ANSWER-9876"

    def refused(self, response: Any, status: int, code: str) -> None:
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert self.SECRET not in response.text

    def test_an_unknown_scheme(self, client: TestClient) -> None:
        self.refused(check(client, "ghost", answers={}), 404, "unknown_scheme")

    def test_an_unknown_track(self, client: TestClient) -> None:
        self.refused(check(client, track="ghost", answers={}), 422, "unknown_track")

    def test_an_unknown_question_is_not_echoed(self, client: TestClient) -> None:
        self.refused(check(client, answers={self.SECRET: 1}), 422, "unknown_question")

    def test_a_wrong_kind_of_answer_is_not_echoed(self, client: TestClient) -> None:
        self.refused(check(client, answers={"family_income": self.SECRET}), 422, "invalid_answer")

    def test_an_out_of_range_answer(self, client: TestClient) -> None:
        self.refused(check(client, answers={"family_income": -5}), 422, "invalid_answer")

    def test_an_answer_that_is_a_list_is_refused_by_validation_without_echo(
        self, client: TestClient
    ) -> None:
        response = check(client, answers={"family_income": [self.SECRET]})

        assert response.status_code == 422
        assert self.SECRET not in response.text

    def test_extra_fields_are_refused(self, client: TestClient) -> None:
        response = check(client, answers={}, name=self.SECRET)

        assert response.status_code == 422
        assert self.SECRET not in response.text

    def test_too_many_answers_are_refused(self, client: TestClient) -> None:
        answers = {f"q{i}": 1 for i in range(21)}

        assert check(client, answers=answers).status_code == 422

    def test_a_missing_track_is_refused(self, client: TestClient) -> None:
        response = client.post(f"{SCHEMES}/svmcm/eligibility", json={"answers": {}})

        assert response.status_code == 422

    def test_answers_are_never_logged(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            check(client, answers={**PRAGATI, "family_income": 123457})
            check(client, answers={"family_income": self.SECRET})

        assert "123457" not in caplog.text
        assert self.SECRET not in caplog.text


class TestWhenTheRulesCannotLoad:
    def test_the_schemes_are_unavailable_but_the_health_check_is_not(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken(**_: Any) -> None:
            raise SchemeDataError("data/schemes/x.toml: invalid")

        monkeypatch.setattr("app.api.deps.load_schemes", broken)

        with TestClient(create_app(settings)) as client:
            response = client.get(SCHEMES)

            assert response.status_code == 503
            assert response.json()["error"]["code"] == "schemes_unavailable"
            assert "x.toml" not in response.text  # for the operator's log, not the user
            assert client.get("/api/v1/health").status_code == 200

    def test_the_real_rules_load_when_no_service_is_given(self, settings: Settings) -> None:
        with TestClient(create_app(settings)) as client:
            assert client.get(SCHEMES).status_code == 200
