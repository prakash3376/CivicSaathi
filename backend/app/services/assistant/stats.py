"""What the assistant has been doing since the server started: counts, never content.

Nothing here keeps a question, a passage or an answer: only what happened (answered, not covered,
fallback, refused, a failure code) and how long it took. It exists so that an operator can see,
on the knowledge-base health page, whether the language model is failing and how fast answers are.
"""

import statistics
import threading
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime

_KEEP = 200  # the latest answers, for the average and the slow end
_RECENT_FAILURES = 10


@dataclass(frozen=True)
class Failure:
    at: datetime
    code: str


class AssistantStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._outcomes: Counter[str] = Counter()
        self._milliseconds: deque[float] = deque(maxlen=_KEEP)
        self._failures: deque[Failure] = deque(maxlen=_RECENT_FAILURES)

    def record(self, outcome: str, milliseconds: float, *, failure: str | None = None) -> None:
        with self._lock:
            self._outcomes[outcome] += 1
            self._milliseconds.append(milliseconds)
            if failure:
                self._failures.append(Failure(datetime.now(UTC), failure))

    def note_failure(self, code: str) -> None:
        """A model failure that the visitor did not see (the passages were shown instead)."""
        with self._lock:
            self._failures.append(Failure(datetime.now(UTC), code))

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            times = sorted(self._milliseconds)
            total = sum(self._outcomes.values())
            return {
                "questions": total,
                "outcomes": dict(self._outcomes),
                # Shares of all questions: how often the model could not be used (the visitor got
                # the passages) and how often a question failed outright.
                "fallback_rate": round(self._outcomes["fallback"] / total, 3) if total else None,
                "error_rate": round(self._outcomes["error"] / total, 3) if total else None,
                "mean_ms": round(statistics.fmean(times), 1) if times else None,
                "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1) if times else None,
                "recent_failures": [
                    {"at": failure.at.isoformat(timespec="seconds"), "code": failure.code}
                    for failure in reversed(self._failures)
                ],
            }
