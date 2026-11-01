"""One ingestion at a time: a lock file with a heartbeat, so a crash cannot lock everyone out.

Two ``ingest`` runs writing the same index at once damaged it once ("Failed to apply logs to the
hnsw segment writer"), and the index is what every answer is built on. The lock is a file made
with an exclusive create. While the holder lives, a background thread refreshes the file's
modification time (the heartbeat); a lock whose heartbeat is older than the lease belongs to a
process that died, and is taken over. It never asks the operating system whether a process id is
alive: that is unreliable across machines and, on Windows, ``os.kill`` with a signal of 0 would
terminate the process it was meant to look at.

Taking over a stale lock moves the old file aside first (an atomic rename that only one contender
can win), so two runs cannot both decide they are the new holder.
"""

import json
import logging
import os
import socket
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from app.domain.errors import IngestionError

logger = logging.getLogger(__name__)

DEFAULT_LEASE_SECONDS = 90.0  # a holder that has not refreshed for this long is presumed dead


class IngestBusyError(IngestionError):
    """Another ingestion is running (or died less than a lease ago)."""

    def __init__(self, holder: dict[str, object] | None, age_seconds: float) -> None:
        who = holder or {}
        message = (
            "Another ingestion is already running "
            f"(started {who.get('started', 'at an unknown time')}"
            f" by process {who.get('pid', '?')} on {who.get('host', '?')}; last sign of life "
            f"{age_seconds:.0f} s ago). Wait for it to finish. If it was killed, this check clears "
            "itself once its lock is older than the lease."
        )
        super().__init__(message, code="ingest_busy")
        self.holder = who


def read_holder(path: Path) -> tuple[dict[str, object] | None, float] | None:
    """Who holds the lock and how long ago it last refreshed, or None if nobody does."""
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        holder = data if isinstance(data, dict) else None
    except (OSError, ValueError):
        holder = None
    return holder, max(age, 0.0)


class IngestLock:
    """A context manager: ``with IngestLock(path): ...`` or ``IngestLock(path).acquire()``."""

    def __init__(
        self,
        path: Path,
        *,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        heartbeat_seconds: float | None = None,
    ) -> None:
        self._path = path
        self._lease = lease_seconds
        self._beat = heartbeat_seconds if heartbeat_seconds is not None else lease_seconds / 4
        self._token = uuid.uuid4().hex  # tells our file from one a successor wrote
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.took_over_stale = False

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                self._create()
            except FileExistsError:
                held = read_holder(self._path)
                if held is None:
                    continue  # it vanished between the two calls: try to create it again
                holder, age = held
                if age < self._lease:
                    raise IngestBusyError(holder, age) from None
                self._take_over(holder, age)
                continue
            self._start_heartbeat()
            return
        raise IngestBusyError(None, 0.0)

    def _create(self) -> None:
        body = json.dumps(
            {
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "started": datetime.now(UTC).isoformat(timespec="seconds"),
                "token": self._token,
            }
        )
        handle = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(body)

    def _take_over(self, holder: dict[str, object] | None, age: float) -> None:
        aside = self._path.with_name(f"{self._path.name}.stale-{uuid.uuid4().hex[:8]}")
        try:
            os.replace(self._path, aside)  # only one contender's rename can succeed
        except OSError:
            return  # someone else took it over first; the loop will see their fresh lock
        aside.unlink(missing_ok=True)
        self.took_over_stale = True
        logger.warning(
            "took over an ingestion lock that had not been refreshed for %.0f s (process %s)",
            age,
            (holder or {}).get("pid", "?"),
        )

    def _start_heartbeat(self) -> None:
        def beat() -> None:
            while not self._stop.wait(self._beat):
                try:
                    os.utime(self._path)
                except OSError:  # the lock file was removed: nothing to keep alive
                    return

        self._thread = threading.Thread(target=beat, name="ingest-lock-heartbeat", daemon=True)
        self._thread.start()

    def release(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        held = read_holder(self._path)
        # Remove only our own file: if we were presumed dead and replaced, it is not ours to delete.
        if held is not None and (held[0] or {}).get("token") == self._token:
            self._path.unlink(missing_ok=True)

    def __enter__(self) -> "IngestLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


def lock_state(path: Path, lease_seconds: float = DEFAULT_LEASE_SECONDS) -> dict[str, object]:
    """For the admin page: is an ingestion running, or did one die while holding the lock?"""
    held = read_holder(path)
    if held is None:
        return {"state": "idle"}
    holder, age = held
    return {
        "state": "running" if age < lease_seconds else "interrupted",
        "pid": (holder or {}).get("pid"),
        "started": (holder or {}).get("started"),
        "seconds_since_heartbeat": round(age),
    }
