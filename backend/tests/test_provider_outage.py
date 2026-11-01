"""The language model fails in every way the provider can, inside the real service and the real app.

For each failure the question must end in something a citizen can use (the matching official
passages, never a 500 and never an invented answer), the operator must be able to see why, and the
rest of the site (browsing, eligibility, the budget, the document list) must carry on unaffected.
The model here is the real ``GeminiClient`` behind the real circuit breaker; only the network under
it is replaced.
"""

import json
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

import app.api.deps as deps
from app.core.config import Settings
from app.domain.assistant import Draft, DraftClaim, Evidence
from app.domain.errors import SchemeDataError
from app.main import create_app
from app.services.eligibility.loader import load_schemes
from app.services.eligibility.service import SchemeService
from app.services.ingestion.registry import load_registry
from app.services.llm.gemini import GeminiClient
from app.services.llm.resilient import CircuitBreaker, GuardedModel
from tests.factories import make_runtime

QUESTION = "What is the family income ceiling?"
GOOD = Draft(
    answerable=True,
    claims=[
        DraftClaim(
            statement="Family income must be at most Rs 2,50,000 a year.",
            evidence=[Evidence(source="S1", quote="fixed at Rs.2,50,000/- per annum")],
        )
    ],
)

Handler = Callable[[httpx.Request], httpx.Response]
_handler: list[Handler] = []
_calls: list[int] = []


def _route(request: httpx.Request) -> httpx.Response:
    _calls.append(1)
    return _handler[-1](request)


def failing(status: int, **headers: str) -> Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        body = {"error": {"code": status, "message": "provider text", "status": "X"}}
        return httpx.Response(status, json=body, headers=headers)

    return handler


def raising(exception: Exception) -> Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise exception

    return handler


def replying(text: str | None, finish: str = "STOP") -> Handler:
    def handler(_request: httpx.Request) -> httpx.Response:
        candidate: dict[str, Any] = {"finishReason": finish, "index": 0}
        if text is not None:
            candidate["content"] = {"role": "model", "parts": [{"text": text}]}
        return httpx.Response(200, json={"candidates": [candidate]})

    return handler


@pytest.fixture(scope="module")
def gemini() -> GeminiClient:
    # The SDK takes about a second to set up, so one client serves every test in this module.
    return GeminiClient(
        api_key="test-key",
        model="gemini-test",
        attempts=2,
        retry_delay_seconds=0.0,
        sleep=lambda _seconds: None,
        http_client=httpx.Client(transport=httpx.MockTransport(_route)),
    )


@pytest.fixture
def service() -> SchemeService:
    book = load_schemes(sources={spec.id: spec.url for spec in load_registry()})
    return SchemeService(book, clock=lambda: date(2026, 10, 20))


@pytest.fixture
def site(
    tmp_path: Path, gemini: GeminiClient, service: SchemeService
) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def build(handler: Handler, *, threshold: int = 5) -> TestClient:
        _handler[:] = [handler]
        _calls.clear()
        model = GuardedModel(gemini, CircuitBreaker(threshold=threshold, cooldown_seconds=30))
        settings = Settings(
            _env_file=None,
            app_env="test",
            log_level="WARNING",
            admin_token="s3cret",
            gemini_api_key="test-key",
            assistant_rate_limit_per_minute=0,
        )
        app = create_app(settings, assistant=make_runtime(tmp_path, model), schemes=service)
        client = TestClient(app)
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.close()


def ask(client: TestClient) -> httpx.Response:
    return client.post("/api/v1/assistant/ask", json={"question": QUESTION})


OUTAGES = {
    "http 400": failing(400),
    "http 401": failing(401),
    "http 403": failing(403),
    "http 404": failing(404),
    "http 408": failing(408),
    "http 429": failing(429),
    "http 429 with Retry-After": failing(429, **{"Retry-After": "3"}),
    "http 500": failing(500),
    "http 502": failing(502),
    "http 503": failing(503),
    "http 504": failing(504),
    "connection refused": raising(httpx.ConnectError("refused")),
    "dns failure": raising(httpx.ConnectError("[Errno 11001] getaddrinfo failed")),
    "read timeout": raising(httpx.ReadTimeout("slow")),
    "connection reset": raising(httpx.ReadError("reset")),
    "empty reply": replying(None),
    "empty text": replying(""),
    "not json": replying("<html>maintenance</html>"),
    "wrong shape": replying('{"answerable": "maybe"}'),
    "cut off at the token limit": replying('{"answerable": tr', finish="MAX_TOKENS"),
}


class TestEveryFailureEndsInSomethingUsable:
    @pytest.mark.parametrize("handler", OUTAGES.values(), ids=OUTAGES.keys())
    def test_the_citizen_gets_the_matching_passages_and_never_an_error(
        self, site: Callable[..., TestClient], handler: Handler
    ) -> None:
        response = ask(site(handler))

        assert response.status_code == 200
        body = response.json()
        assert (body["answerable"], body["fallback"], body["claims"]) == (False, True, [])
        [citation, *_] = body["citations"]
        assert citation["source_id"] == "guide"  # what the documents say, as they say it
        assert "Rs.2,50,000" in citation["quote"]
        assert "provider text" not in response.text  # nothing the provider said reaches a reader
        assert "test-key" not in response.text

    @pytest.mark.parametrize("handler", OUTAGES.values(), ids=OUTAGES.keys())
    def test_the_rest_of_the_site_is_unaffected_during_the_outage(
        self, site: Callable[..., TestClient], handler: Handler
    ) -> None:
        client = site(handler)
        ask(client)

        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/schemes").status_code == 200
        assert client.get("/api/v1/budget").status_code == 200
        assert client.get("/api/v1/sources").status_code == 200
        pragati = client.post(
            "/api/v1/schemes/aicte-pragati/eligibility",
            json={"track": "degree", "answers": {}},
        )
        assert pragati.status_code == 200  # deterministic rules need no model
        assert client.get("/api/v1/health/ready").status_code == 200  # degraded, not dead

    def test_a_successful_answer_still_works_when_the_provider_is_fine(
        self, site: Callable[..., TestClient]
    ) -> None:
        client = site(replying(GOOD.model_dump_json()))

        body = ask(client).json()

        assert body["answerable"] is True
        assert body["fallback"] is False


class TestRetriesAreBoundedAndSafe:
    def test_a_transient_failure_is_retried_once_and_the_visitor_never_notices(
        self, site: Callable[..., TestClient]
    ) -> None:
        answers = iter([failing(503), replying(GOOD.model_dump_json())])
        client = site(lambda request: next(answers)(request))

        body = ask(client).json()

        assert body["answerable"] is True
        assert len(_calls) == 2

    @pytest.mark.parametrize("status", [400, 401, 403, 404])
    def test_a_permanent_failure_is_not_retried_at_all(
        self, site: Callable[..., TestClient], status: int
    ) -> None:
        ask(site(failing(status)))

        assert len(_calls) == 1  # a wrong key does not heal by asking again

    def test_a_persistent_outage_costs_the_provider_a_bounded_number_of_calls(
        self, site: Callable[..., TestClient]
    ) -> None:
        ask(site(failing(503)))

        assert len(_calls) == 2  # the first try and one retry: never a loop


class TestTheCircuitBreakerSavesEveryoneTheWait:
    def test_after_repeated_failures_the_provider_is_left_alone_and_answers_stay_instant(
        self, site: Callable[..., TestClient]
    ) -> None:
        client = site(failing(503), threshold=3)
        for _ in range(3):
            ask(client)  # each costs a try and a retry
        seen = len(_calls)

        bodies = [ask(client).json() for _ in range(10)]

        assert len(_calls) == seen  # ten more questions, not one more call to the provider
        assert all(body["fallback"] and body["citations"] for body in bodies)

    def test_the_site_reports_itself_degraded_while_the_breaker_is_open(
        self, site: Callable[..., TestClient]
    ) -> None:
        client = site(failing(503), threshold=2)
        assert client.get("/api/v1/health/ready").json()["components"]["assistant_model"] == {
            "status": "ok",
            "detail": None,
        }
        for _ in range(2):
            ask(client)

        ready = client.get("/api/v1/health/ready")

        assert ready.status_code == 200  # an AI outage never marks the site dead
        body = ready.json()
        assert body["status"] == "degraded"
        assert body["components"]["assistant_model"]["status"] == "degraded"
        assert body["components"]["records"]["status"] == "ok"


class TestTheOperatorCanSeeWhatTheCitizenDidNot:
    def test_a_rejected_key_is_visible_to_the_admin_even_though_visitors_got_passages(
        self, site: Callable[..., TestClient]
    ) -> None:
        client = site(failing(401))
        assert ask(client).json()["fallback"] is True

        system = client.get("/api/v1/admin/system", headers={"X-Admin-Token": "s3cret"}).json()

        codes = [failure["code"] for failure in system["assistant"]["recent_failures"]]
        assert codes == ["llm_auth"]
        assert system["assistant"]["outcomes"] == {"fallback": 1}
        assert system["provider"]["circuit"]["state"] == "closed"  # a bad key is not an outage
        assert "provider text" not in json.dumps(system)

    def test_the_breaker_state_and_its_cause_are_on_the_admin_page(
        self, site: Callable[..., TestClient]
    ) -> None:
        client = site(failing(503), threshold=2)
        for _ in range(2):
            ask(client)

        circuit = client.get("/api/v1/admin/system", headers={"X-Admin-Token": "s3cret"}).json()[
            "provider"
        ]["circuit"]

        assert circuit["state"] == "open"
        assert circuit["last_failure"] == "llm_unavailable"
        assert circuit["times_opened"] == 1


class TestReadiness:
    def test_a_healthy_site_is_ok(self, site: Callable[..., TestClient]) -> None:
        body = site(replying(GOOD.model_dump_json())).get("/api/v1/health/ready").json()

        assert body["status"] == "ok"
        assert {name: part["status"] for name, part in body["components"].items()} == {
            "records": "ok",
            "index": "ok",
            "assistant_model": "ok",
            "ingestion": "ok",
        }

    def test_the_records_failing_to_load_is_the_one_thing_that_makes_it_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def unreadable(**_options: object) -> None:
            raise SchemeDataError("a rule file is malformed")

        monkeypatch.setattr(deps, "load_schemes", unreadable)
        settings = Settings(_env_file=None, app_env="test", log_level="WARNING")
        app = create_app(settings, assistant=make_runtime(tmp_path, None))  # no scheme service

        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unavailable"
        assert body["components"]["records"]["status"] == "down"
        assert "malformed" not in response.text  # the file's problem is for the log, not the reply

    def test_no_api_key_is_off_not_broken(self, tmp_path: Path, service: SchemeService) -> None:
        settings = Settings(_env_file=None, app_env="test", log_level="WARNING")
        app = create_app(settings, assistant=make_runtime(tmp_path, None), schemes=service)

        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")

        assert response.status_code == 200
        assert response.json()["components"]["assistant_model"]["status"] == "off"

    def test_an_empty_index_is_degraded_and_browsing_still_works(
        self, tmp_path: Path, service: SchemeService
    ) -> None:
        settings = Settings(_env_file=None, app_env="test", log_level="WARNING")
        runtime = make_runtime(tmp_path, None, texts=())
        app = create_app(settings, assistant=runtime, schemes=service)

        with TestClient(app) as client:
            ready = client.get("/api/v1/health/ready")
            schemes = client.get("/api/v1/schemes")

        assert ready.json()["components"]["index"]["status"] == "degraded"
        assert schemes.status_code == 200

    def test_it_is_never_cached(self, site: Callable[..., TestClient]) -> None:
        response = site(replying(GOOD.model_dump_json())).get("/api/v1/health/ready")

        assert response.headers["cache-control"] == "no-store"
