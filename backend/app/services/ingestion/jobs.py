"""Ingestion as a job: bounded retries for trouble that passes, and a status record to inspect.

Ingestion is slow, touches the network and is run by a person (``python -m app.cli ingest``), so it
never blocks a visitor. What it lacked was a way to tell *a document that is wrong* from *a server
that was briefly unreachable*: both ended as "rejected", and a re-run was the only cure. Now:

* a rejection whose only failed check is the download itself (a timeout, a reset connection, a 5xx)
  is **transient** and is retried, up to ``attempts`` times with exponential backoff;
* anything else (wrong identity phrases, not an official host, a bad certificate, a file that is not
  a PDF) is **permanent**, is never retried, and says which check failed;
* every source's state is written to ``storage/jobs/ingest.json`` after each step, so an
  administrator can see what ran, what is running, and what failed and why.

Running it twice changes nothing: the pipeline compares fingerprints and skips what is unchanged.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.domain.errors import IngestionError

if TYPE_CHECKING:  # the pipeline pulls in the vector store; the API only reads the status file
    from app.domain.sources import SourceSpec
    from app.services.ingestion.pipeline import IngestResult

# Checks that fail because of the network, not because of the document.
TRANSIENT_CHECKS = frozenset({"download"})
DEFAULT_ATTEMPTS = 3
BASE_DELAY_SECONDS = 2.0
_DETAIL_CHARS = 200


def is_transient(result: IngestResult) -> bool:
    """A rejection caused only by trouble that may pass on its own."""
    failures = result.report.failures
    return (
        result.outcome == "rejected"
        and bool(failures)
        and all(check.name in TRANSIENT_CHECKS for check in failures)
    )


@dataclass
class Job:
    source_id: str
    state: str  # running, retrying, indexed, unchanged, rejected
    attempts: int = 0
    passages: int = 0
    seconds: float = 0.0
    failed_check: str | None = None
    detail: str | None = None  # why, in the words of the check (it never holds document text)
    at: str = ""


class JobLog:
    """The state of the latest ingestion run, kept as one small JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._jobs: dict[str, Job] = {}
        self._started = datetime.now(UTC).isoformat(timespec="seconds")
        self._finished: str | None = None

    def update(self, job: Job) -> None:
        job.at = datetime.now(UTC).isoformat(timespec="seconds")
        self._jobs[job.source_id] = job
        self._write()

    def finish(self) -> None:
        self._finished = datetime.now(UTC).isoformat(timespec="seconds")
        self._write()

    def _write(self) -> None:
        body = {
            "started_at": self._started,
            "finished_at": self._finished,
            "jobs": {name: asdict(job) for name, job in self._jobs.items()},
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(body, file, indent=2)
            os.replace(temporary, self._path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise


def read_status(path: Path) -> dict[str, object] | None:
    """The latest run as written, or None if there has been none (or the file is unreadable)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def ingest_with_retry(
    ingest: Callable[[SourceSpec], IngestResult],
    spec: SourceSpec,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = BASE_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    log: JobLog | None = None,
) -> IngestResult:
    """Ingest one source, trying again only when the failure was the network's.

    One source failing never stops the others: a domain error (the embedding model, the index, a
    file that cannot be read) is returned as a rejection that says why. Anything else is a bug, so
    it is raised, but not before the job is marked ``failed``: a record that says "running" for a
    process that is gone would mislead the person reading it.
    """

    def attempt() -> IngestResult:
        try:
            return ingest(spec)
        except IngestionError as error:
            return _failed(spec, error)
        except Exception as error:
            if log:
                log.update(Job(spec.id, "failed", detail=type(error).__name__))
            raise

    result = attempt()
    tried = 1
    while is_transient(result) and tried < attempts:
        if log:
            check, detail = _why(result)
            log.update(Job(spec.id, "retrying", attempts=tried, failed_check=check, detail=detail))
        sleep(base_delay * 2 ** (tried - 1))  # 2 s, 4 s, 8 s ...
        result = attempt()
        tried += 1
    if log:
        check, detail = _why(result) if result.outcome == "rejected" else (None, None)
        log.update(
            Job(
                spec.id,
                result.outcome,
                attempts=tried,
                passages=result.chunks,
                seconds=round(result.seconds, 1),
                failed_check=check,
                detail=detail,
            )
        )
    return result


def _failed(spec: SourceSpec, error: IngestionError) -> IngestResult:
    """A domain error while indexing, in the same shape as any other rejection."""
    from app.domain.documents import VerificationCheck
    from app.services.ingestion.pipeline import IngestResult
    from app.services.ingestion.verification import build_report

    check = VerificationCheck(name="indexing", status="fail", detail=error.message[:_DETAIL_CHARS])
    return IngestResult(spec.id, "rejected", build_report(spec, [check], datetime.now(UTC)), 0, 0.0)


def _why(result: IngestResult) -> tuple[str | None, str | None]:
    failures = result.report.failures
    first = failures[0] if failures else None
    return (first.name, first.detail[:_DETAIL_CHARS]) if first else (None, None)
