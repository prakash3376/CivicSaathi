"""A small in-memory limit on how often one client may ask for something expensive.

Each question costs a call to a paid, rate-limited model, so an unthrottled endpoint is an easy way
to run up a bill or to exhaust the quota for everyone else. The limit is per client address over a
sliding minute. It lives in this process's memory: with several server processes each keeps its
own count, and a restart forgets it. That is enough to stop a runaway script or one noisy client;
a deployment that needs a hard shared limit should add one at the proxy.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

_WINDOW_SECONDS = 60.0
_PRUNE_AT = 5_000  # clients remembered before the ones that have gone quiet are forgotten


class RateLimiter:
    def __init__(self, per_minute: int, *, clock: Callable[[], float] = time.monotonic) -> None:
        """``per_minute`` of 0 switches the limit off."""
        self._limit = per_minute
        self._clock = clock
        self._seen: dict[str, deque[float]] = {}
        self._lock = threading.Lock()  # request handlers run in a thread pool

    def retry_after(self, client: str) -> int | None:
        """Record a request. None if it is allowed, else the seconds to wait before the next."""
        if self._limit <= 0:
            return None
        now = self._clock()
        with self._lock:
            times = self._seen.setdefault(client, deque())
            while times and now - times[0] >= _WINDOW_SECONDS:
                times.popleft()
            if len(times) >= self._limit:
                return max(1, int(_WINDOW_SECONDS - (now - times[0])) + 1)
            times.append(now)
            if len(self._seen) > _PRUNE_AT:
                self._forget_quiet_clients(now)
            return None

    def _forget_quiet_clients(self, now: float) -> None:
        quiet = [
            client
            for client, times in self._seen.items()
            if not times or now - times[-1] >= _WINDOW_SECONDS
        ]
        for client in quiet:
            del self._seen[client]
