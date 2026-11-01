"""The circuit breaker: an outage must cost seconds, and recovery must be noticed."""

import threading

import pytest

from app.domain.assistant import Draft
from app.domain.errors import AssistantError
from app.services.llm.resilient import CircuitBreaker, GuardedModel


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Scripted:
    """A model that does what it is told, one thing per call, and counts the calls."""

    name = "scripted"

    def __init__(self, *outcomes: str) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate(self, *, system: str, prompt: str, schema: type[Draft]) -> Draft:
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else "ok"
        if outcome == "ok":
            return Draft(answerable=False, claims=[])
        if outcome == "crash":
            raise RuntimeError("a bug, not the provider")
        raise AssistantError("x", code=outcome)


def ask(model: GuardedModel) -> str:
    try:
        model.generate(system="s", prompt="p", schema=Draft)
    except AssistantError as error:
        return error.code
    return "ok"


def guarded(model: Scripted, clock: Clock, threshold: int = 3) -> GuardedModel:
    return GuardedModel(
        model, CircuitBreaker(threshold=threshold, cooldown_seconds=30, clock=clock)
    )


def test_it_stays_closed_below_the_threshold() -> None:
    model = Scripted("llm_unavailable", "llm_unavailable", "ok")
    clock = Clock()
    guard = guarded(model, clock)

    assert [ask(guard) for _ in range(3)] == ["llm_unavailable", "llm_unavailable", "ok"]
    assert guard.breaker.state == "closed"


def test_after_the_threshold_the_model_is_not_asked_at_all() -> None:
    model = Scripted(*["llm_unavailable"] * 3)
    guard = guarded(model, Clock())
    for _ in range(3):
        ask(guard)

    results = [ask(guard) for _ in range(10)]

    assert results == ["llm_unavailable"] * 10  # the same code, so the visitor gets the passages
    assert model.calls == 3  # and the provider was spared the 10 calls
    assert guard.breaker.state == "open"


def test_a_rate_limit_counts_as_much_as_an_outage() -> None:
    guard = guarded(Scripted("llm_busy", "llm_busy", "llm_busy"), Clock())
    for _ in range(3):
        ask(guard)

    assert guard.breaker.state == "open"


@pytest.mark.parametrize("code", ["llm_auth", "llm_rejected", "llm_blocked", "llm_bad_output"])
def test_failures_that_are_not_the_providers_health_never_open_it(code: str) -> None:
    model = Scripted(*[code] * 20)
    guard = guarded(model, Clock())

    assert [ask(guard) for _ in range(20)] == [code] * 20
    assert guard.breaker.state == "closed"
    assert model.calls == 20  # each was really asked


def test_after_the_cooldown_exactly_one_probe_is_let_through() -> None:
    model = Scripted(*["llm_unavailable"] * 3, "ok")
    clock = Clock()
    guard = guarded(model, clock)
    for _ in range(3):
        ask(guard)
    clock.now += 31

    assert guard.breaker.state == "half_open"
    assert guard.breaker.allow() is True  # the probe
    assert guard.breaker.allow() is False  # everyone else still waits for its result


def test_a_successful_probe_closes_it() -> None:
    model = Scripted(*["llm_unavailable"] * 3, "ok", "ok")
    clock = Clock()
    guard = guarded(model, clock)
    for _ in range(3):
        ask(guard)
    clock.now += 31

    assert [ask(guard), ask(guard)] == ["ok", "ok"]
    assert guard.breaker.state == "closed"
    assert guard.breaker.snapshot()["consecutive_failures"] == 0


def test_a_failed_probe_opens_it_again_for_a_full_cooldown() -> None:
    model = Scripted(*["llm_unavailable"] * 4, "ok")
    clock = Clock()
    guard = guarded(model, clock)
    for _ in range(3):
        ask(guard)
    clock.now += 31
    assert ask(guard) == "llm_unavailable"  # the probe fails

    clock.now += 10
    assert guard.breaker.state == "open"
    assert ask(guard) == "llm_unavailable"
    assert model.calls == 4  # not asked again within the new cooldown
    clock.now += 21
    assert ask(guard) == "ok"


def test_a_success_in_between_resets_the_streak() -> None:
    model = Scripted(
        "llm_unavailable", "llm_unavailable", "ok", "llm_unavailable", "llm_unavailable"
    )
    guard = guarded(model, Clock())

    for _ in range(5):
        ask(guard)

    assert guard.breaker.state == "closed"  # never three in a row


def test_a_bug_in_our_code_is_not_blamed_on_the_provider_and_frees_the_probe() -> None:
    model = Scripted(*["llm_unavailable"] * 3, "crash", "ok")
    clock = Clock()
    guard = guarded(model, clock)
    for _ in range(3):
        ask(guard)
    clock.now += 31

    with pytest.raises(RuntimeError):
        guard.generate(system="s", prompt="p", schema=Draft)

    assert ask(guard) == "ok"  # the next question may probe: the breaker is not stuck half open


def test_the_state_is_reported_for_the_admin_page() -> None:
    guard = guarded(Scripted(*["llm_unavailable"] * 3), Clock())
    for _ in range(3):
        ask(guard)

    assert guard.health() == {
        "state": "open",
        "consecutive_failures": 3,
        "last_failure": "llm_unavailable",
        "times_opened": 1,
    }
    assert guard.name == "scripted"


def test_many_threads_failing_at_once_leave_it_consistent() -> None:
    model = Scripted(*["llm_unavailable"] * 200)
    guard = guarded(model, Clock(), threshold=5)

    threads = [threading.Thread(target=lambda: [ask(guard) for _ in range(20)]) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert guard.breaker.state == "open"
    assert guard.breaker.snapshot()["times_opened"] == 1
    assert model.calls < 200  # most of the 200 questions never reached the provider
