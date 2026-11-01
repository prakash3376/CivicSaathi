"""A circuit breaker around a language model, so that an outage costs seconds, not minutes.

Without it, every question asked while the provider is down waits for the full time limit (tens of
seconds) before the visitor is shown the matching official passages. With it, after a few failures
in a row the model is not asked at all for a short while: the answer is the passages at once. One
question is then let through to find out whether the provider is back.

Only failures that say "the provider is unwell" count (``llm_unavailable``, ``llm_busy``). A wrong
key or a rejected request is the operator's problem and would not heal by waiting; a blocked prompt
or a badly shaped reply is about one question, not about the provider. A success closes the breaker.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import Literal

from app.domain.errors import AssistantError
from app.services.llm.base import LanguageModel, T

logger = logging.getLogger(__name__)

State = Literal["closed", "open", "half_open"]
COUNTED = frozenset({"llm_unavailable", "llm_busy"})


class CircuitBreaker:
    def __init__(
        self,
        *,
        threshold: int = 5,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = max(1, threshold)
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False
        self._last_code: str | None = None
        self._opened_total = 0

    def allow(self) -> bool:
        """May the model be asked now? While open, only one probe is let through after the pause."""
        with self._lock:
            if self._opened_at is None:
                return True
            if self._clock() - self._opened_at < self._cooldown or self._probing:
                return False
            self._probing = True
            return True

    def success(self) -> None:
        with self._lock:
            if self._opened_at is not None:
                logger.info("the language model answered again; the circuit is closed")
            self._failures, self._opened_at, self._probing = 0, None, False

    def failure(self, code: str) -> None:
        with self._lock:
            self._last_code = code
            self._probing = False
            if code not in COUNTED:
                # The provider answered (with a refusal or a bad reply): it is reachable.
                self._failures, self._opened_at = 0, None
                return
            self._failures += 1
            if self._opened_at is not None or self._failures >= self._threshold:
                if self._opened_at is None:
                    self._opened_total += 1
                    logger.error(
                        "the language model failed %d times in a row (%s); not asking it for %d s",
                        self._failures,
                        code,
                        self._cooldown,
                    )
                self._opened_at = self._clock()

    def release(self) -> None:
        """A probe ended without telling anything about the provider: let another one try."""
        with self._lock:
            self._probing = False

    @property
    def state(self) -> State:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            return "half_open" if self._clock() - self._opened_at >= self._cooldown else "open"

    def snapshot(self) -> dict[str, object]:
        state = self.state
        with self._lock:
            return {
                "state": state,
                "consecutive_failures": self._failures,
                "last_failure": self._last_code,
                "times_opened": self._opened_total,
            }


class GuardedModel:
    """A ``LanguageModel`` that is not asked while its breaker is open."""

    def __init__(self, model: LanguageModel, breaker: CircuitBreaker | None = None) -> None:
        self._model = model
        self.breaker = breaker or CircuitBreaker()

    @property
    def name(self) -> str:
        return self._model.name

    @property
    def inner(self) -> LanguageModel:
        return self._model

    def health(self) -> dict[str, object]:
        return self.breaker.snapshot()

    def generate(self, *, system: str, prompt: str, schema: type[T]) -> T:
        if not self.breaker.allow():
            raise AssistantError(
                "The assistant did not respond. Please try again in a moment.",
                code="llm_unavailable",
            )
        try:
            result = self._model.generate(system=system, prompt=prompt, schema=schema)
        except AssistantError as error:
            self.breaker.failure(error.code)
            raise
        except BaseException:
            self.breaker.release()  # an unexpected error says nothing about the provider
            raise
        self.breaker.success()
        return result
