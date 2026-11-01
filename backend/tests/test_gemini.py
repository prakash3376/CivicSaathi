import json
import logging
from collections.abc import Callable

import httpx
import pytest

from app.domain.assistant import Draft, DraftClaim, Evidence
from app.domain.errors import AssistantError
from app.services.llm.gemini import GeminiClient

KEY = "AIzaSy-test-key-do-not-leak"
DRAFT = Draft(
    answerable=True,
    claims=[
        DraftClaim(
            statement="Family income must be at most Rs 2,50,000 a year.",
            evidence=[Evidence(source="S1", quote="fixed at Rs.2,50,000/- per annum")],
        )
    ],
)

Handler = Callable[[httpx.Request], httpx.Response]


def reply(text: str | None, *, finish: str = "STOP", **extra: object) -> httpx.Response:
    candidate: dict[str, object] = {"finishReason": finish, "index": 0}
    if text is not None:
        candidate["content"] = {"role": "model", "parts": [{"text": text}]}
    body = {
        "candidates": [candidate],
        "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30},
        **extra,
    }
    return httpx.Response(200, json=body)


def failure(status: int) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": status, "message": "x", "status": "X"}})


# Building the SDK's client takes about a second (it sets up TLS), so a client is built once per
# set of options and reused. All of them send their requests through this one transport, which
# hands each request to the handler the running test installed.
_installed: list[Handler] = []
_clients: dict[tuple[tuple[str, object], ...], GeminiClient] = {}


def _route(request: httpx.Request) -> httpx.Response:
    return _installed[-1](request)


def client_for(handler: Handler, **options: object) -> GeminiClient:
    _installed[:] = [handler]
    settings: dict[str, object] = {"attempts": 1, "retry_delay_seconds": 0.0, **options}
    key = tuple(sorted(settings.items()))
    if key not in _clients:
        _clients[key] = GeminiClient(
            api_key=KEY,
            model="gemini-test",
            http_client=httpx.Client(transport=httpx.MockTransport(_route)),
            **settings,  # type: ignore[arg-type]
        )
    return _clients[key]


def ask(client: GeminiClient) -> Draft:
    return client.generate(system="rules", prompt="the prompt", schema=Draft)


def error_code(handler: Handler, **options: object) -> str:
    with pytest.raises(AssistantError) as error:
        ask(client_for(handler, **options))
    return error.value.code


class TestRequest:
    def test_sends_the_instruction_prompt_and_schema_and_returns_the_parsed_object(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return reply(DRAFT.model_dump_json())

        result = client_for(handler, max_output_tokens=1234).generate(
            system="the rules", prompt="the question and passages", schema=Draft
        )

        assert result == DRAFT
        [request] = seen
        assert request.url.path == "/v1beta/models/gemini-test:generateContent"
        body = json.loads(request.content)
        assert body["contents"] == [
            {"parts": [{"text": "the question and passages"}], "role": "user"}
        ]
        assert body["systemInstruction"]["parts"] == [{"text": "the rules"}]
        config = body["generationConfig"]
        assert config["responseMimeType"] == "application/json"
        assert config["maxOutputTokens"] == 1234
        assert config["temperature"] == 0.2
        assert {"answerable", "claims"} <= set(config["responseSchema"]["properties"])

    def test_the_key_travels_in_a_header_never_in_the_address(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return reply(DRAFT.model_dump_json())

        ask(client_for(handler))

        assert seen[0].headers["x-goog-api-key"] == KEY
        assert KEY not in str(seen[0].url)

    def test_nothing_is_stored_and_no_thinking_setting_is_sent_unless_asked_for(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return reply(DRAFT.model_dump_json())

        ask(client_for(handler))

        body = json.loads(seen[0].content)
        assert "store" not in body
        assert "thinkingConfig" not in body["generationConfig"]

    def test_a_thinking_level_is_sent_when_configured(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return reply(DRAFT.model_dump_json())

        ask(client_for(handler, thinking_level="low"))

        thinking = json.loads(seen[0].content)["generationConfig"]["thinkingConfig"]
        assert list(thinking.values()) == ["LOW"]  # the SDK's own spelling of the field name

    def test_another_address_can_be_configured(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return reply(DRAFT.model_dump_json())

        ask(client_for(handler, base_url="https://gateway.example/proxy"))

        assert seen[0].url.host == "gateway.example"

    def test_the_model_name_is_exposed(self) -> None:
        assert client_for(lambda _request: reply("{}")).name == "gemini-test"


class TestFailures:
    @pytest.mark.parametrize(
        ("status", "code"),
        [
            (401, "llm_auth"),
            (403, "llm_auth"),
            (429, "llm_busy"),
            (400, "llm_rejected"),
            (404, "llm_rejected"),
            (500, "llm_unavailable"),
            (503, "llm_unavailable"),
        ],
    )
    def test_an_http_error_becomes_a_coded_assistant_error(self, status: int, code: str) -> None:
        assert error_code(lambda _request: failure(status)) == code

    @pytest.mark.parametrize("exception", [httpx.ConnectError("down"), httpx.ReadTimeout("slow")])
    def test_a_network_failure_or_timeout_is_unavailable(self, exception: Exception) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise exception

        assert error_code(handler) == "llm_unavailable"

    def test_a_blocked_prompt_is_reported_as_blocked(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})

        assert error_code(handler) == "llm_blocked"

    @pytest.mark.parametrize("finish", ["SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION"])
    def test_a_reply_stopped_by_the_provider_is_reported_as_blocked(self, finish: str) -> None:
        assert error_code(lambda _request: reply("{}", finish=finish)) == "llm_blocked"

    def test_a_reply_cut_off_at_the_token_limit_is_bad_output(self) -> None:
        cut = reply('{"answerable": tr', finish="MAX_TOKENS")

        assert error_code(lambda _request: cut) == "llm_bad_output"

    @pytest.mark.parametrize(
        "text",
        [None, "", "not json at all", '{"answerable": "maybe"}', '{"claims": []}', "[1, 2]"],
    )
    def test_a_reply_that_is_not_the_requested_shape_is_bad_output(self, text: str | None) -> None:
        assert error_code(lambda _request: reply(text)) == "llm_bad_output"

    def test_json_wrapped_in_a_code_fence_is_accepted(self) -> None:
        fenced = f"```json\n{DRAFT.model_dump_json()}\n```"

        assert ask(client_for(lambda _request: reply(fenced))) == DRAFT

    def test_an_answer_with_no_claims_is_valid(self) -> None:
        answer = ask(client_for(lambda _request: reply('{"answerable": false, "claims": []}')))

        assert answer == Draft(answerable=False, claims=[])
        assert answer.not_stated == []

    def test_what_the_user_may_be_told_is_safe_to_show(self) -> None:
        with pytest.raises(AssistantError) as error:
            ask(client_for(lambda _request: failure(401)))

        assert KEY not in error.value.message
        assert "key" not in error.value.message.lower()  # no hint about credentials
        assert error.value.__cause__ is None  # the provider's text is not chained on


class TestRetries:
    def test_a_server_error_is_retried_once_and_can_then_succeed(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return failure(503) if len(calls) == 1 else reply(DRAFT.model_dump_json())

        assert ask(client_for(handler, attempts=2)) == DRAFT
        assert len(calls) == 2

    def test_a_rate_limit_that_persists_is_reported_after_the_attempts(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return failure(429)

        assert error_code(handler, attempts=2) == "llm_busy"
        assert len(calls) == 2

    def test_a_wrong_key_is_not_retried(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return failure(401)

        assert error_code(handler, attempts=3) == "llm_auth"
        assert len(calls) == 1


class Pauses:
    """A stand-in for time: records each pause instead of waiting, and moves a fake clock."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def with_pauses(pauses: Pauses, **options: object) -> dict[str, object]:
    return {
        "sleep": pauses.sleep,
        "clock": pauses.clock,
        "jitter": lambda: 1.0,  # the longest the random pause can be
        "retry_delay_seconds": 2.0,
        **options,
    }


def failing_then_ok(status: int, times: int, **headers: str) -> tuple[Handler, list[int]]:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) <= times:
            response = failure(status)
            response.headers.update(headers)
            return response
        return reply(DRAFT.model_dump_json())

    return handler, calls


class TestHowRetriesWait:
    def test_the_pause_doubles_with_each_attempt_and_is_never_zero(self) -> None:
        pauses = Pauses()
        handler, calls = failing_then_ok(503, 2)

        ask(client_for(handler, **with_pauses(pauses, attempts=3, deadline_seconds=100)))

        assert len(calls) == 3
        assert pauses.slept == [2.0, 4.0]  # jitter is 1.0 here: the ceiling of each pause

    def test_jitter_spreads_the_pause_between_half_and_all_of_the_delay(self) -> None:
        for roll, expected in ((0.0, 1.0), (0.5, 1.5), (1.0, 2.0)):
            pauses = Pauses()
            handler, _ = failing_then_ok(503, 1)

            ask(
                client_for(
                    handler,
                    **{**with_pauses(pauses, attempts=2), "jitter": lambda roll=roll: roll},
                )
            )

            assert pauses.slept == [expected]

    def test_the_providers_retry_after_is_obeyed_instead_of_the_guess(self) -> None:
        pauses = Pauses()
        handler, calls = failing_then_ok(429, 1, **{"Retry-After": "7"})

        ask(client_for(handler, **with_pauses(pauses, attempts=2)))

        assert pauses.slept == [7.0]
        assert len(calls) == 2

    def test_a_retry_after_that_is_too_long_is_not_waited_for(self) -> None:
        pauses = Pauses()
        handler, calls = failing_then_ok(429, 5, **{"Retry-After": "120"})

        assert error_code(handler, **with_pauses(pauses, attempts=3)) == "llm_busy"

        assert pauses.slept == []  # the visitor is not made to wait two minutes
        assert len(calls) == 1

    @pytest.mark.parametrize("value", ["soon", "-5", "Wed, 21 Oct 2026 07:28:00 GMT"])
    def test_an_unusable_retry_after_falls_back_to_the_doubling_delay(self, value: str) -> None:
        pauses = Pauses()
        handler, _ = failing_then_ok(503, 1, **{"Retry-After": value})

        ask(client_for(handler, **with_pauses(pauses, attempts=2)))

        assert pauses.slept == [2.0]

    def test_no_retry_is_started_that_cannot_finish_inside_the_deadline(self) -> None:
        pauses = Pauses()
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            pauses.now += 48  # the first attempt used almost the whole 50 s
            return failure(503)

        code = error_code(handler, **with_pauses(pauses, attempts=3, deadline_seconds=50))

        assert code == "llm_unavailable"
        assert len(calls) == 1  # 2 s were left: not enough for a call

    def test_each_attempt_is_given_only_the_time_that_is_left(self) -> None:
        pauses = Pauses()
        timeouts: list[float | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            timeouts.append(request.extensions.get("timeout", {}).get("read"))
            pauses.now += 20
            return failure(503) if len(timeouts) == 1 else reply(DRAFT.model_dump_json())

        ask(client_for(handler, **with_pauses(pauses, attempts=2, deadline_seconds=50)))

        first, second = timeouts
        assert first == pytest.approx(45.0)  # the configured timeout, as it is under the deadline
        assert second == pytest.approx(50 - 20 - 2.0)  # what the deadline had left after the pause

    def test_a_refused_connection_is_retried_because_nothing_was_sent(self) -> None:
        pauses = Pauses()
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                raise httpx.ConnectError("refused")
            return reply(DRAFT.model_dump_json())

        assert ask(client_for(handler, **with_pauses(pauses, attempts=2))) == DRAFT
        assert len(calls) == 2

    def test_a_read_timeout_is_not_retried_because_it_already_cost_the_whole_timeout(self) -> None:
        pauses = Pauses()
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            raise httpx.ReadTimeout("slow")

        assert error_code(handler, **with_pauses(pauses, attempts=3)) == "llm_unavailable"
        assert len(calls) == 1

    @pytest.mark.parametrize("status", [400, 401, 403, 404])
    def test_a_permanent_error_is_never_retried_however_many_attempts_are_allowed(
        self, status: int
    ) -> None:
        pauses = Pauses()
        handler, calls = failing_then_ok(status, 9)

        error_code(handler, **with_pauses(pauses, attempts=5))

        assert len(calls) == 1
        assert pauses.slept == []

    @pytest.mark.parametrize("status", [408])
    def test_other_statuses_are_reported_as_unavailable(self, status: int) -> None:
        assert error_code(lambda _request: failure(status)) == "llm_unavailable"


class TestPrivacy:
    def test_neither_the_prompt_nor_the_reply_nor_the_key_is_ever_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        secret_reply = Draft(
            answerable=True,
            claims=[
                DraftClaim(
                    statement="PRIVATE-REPLY-TEXT",
                    evidence=[Evidence(source="S1", quote="PRIVATE-QUOTE-TEXT")],
                )
            ],
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return reply(secret_reply.model_dump_json())

        with caplog.at_level(logging.DEBUG):
            client_for(handler).generate(
                system="PRIVATE-SYSTEM-TEXT", prompt="PRIVATE-QUESTION-TEXT", schema=Draft
            )
            error_code(lambda _request: failure(400))
            error_code(lambda _request: reply("PRIVATE-GARBAGE-NOT-JSON"))

        logged = caplog.text
        for secret in ("PRIVATE-", KEY):
            assert secret not in logged
        assert "gemini-test" in logged  # the model and timing are logged, nothing else
