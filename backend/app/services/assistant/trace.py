"""A record of how each answer was reached, for an administrator: never what was asked.

For every question: what it was judged to be, which catalogue records the router matched, which
documents the evidence came from, how long retrieval and the model took, and whether the
verification kept every claim. A question, a passage and a reply are not here, and neither is any
personal detail: only identifiers of public records and numbers.
"""

import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

_KEEP = 50


@dataclass
class Trace:
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    language: str = ""
    intent: str | None = None
    needs_history: bool = False
    routed: list[str] = field(default_factory=list)  # catalogue or budget record ids
    sources: list[str] = field(default_factory=list)  # documents the passages came from
    passages: int = 0
    retrieval_ms: float = 0.0
    model_ms: float = 0.0
    outcome: str = ""  # answered, not_covered, refused, fallback
    claims_kept: int = 0
    claims_removed: bool = False  # verification dropped something the model wrote


class TraceLog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: deque[Trace] = deque(maxlen=_KEEP)

    def add(self, trace: Trace) -> None:
        with self._lock:
            self._items.append(trace)

    def summary(self) -> dict[str, object]:
        """Over the traces kept: how often verification removed what the model wrote."""
        with self._lock:
            items = list(self._items)
        answered = [item for item in items if item.outcome == "answered"]
        removed = sum(item.claims_removed for item in answered)
        return {
            "traces": len(items),
            "answered": len(answered),
            "answers_with_claims_removed": removed,
            "claims_removed_rate": round(removed / len(answered), 3) if answered else None,
        }

    def latest(self, count: int = 20) -> list[dict[str, object]]:
        with self._lock:
            return [asdict(item) for item in list(self._items)[-count:]][::-1]
