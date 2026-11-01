import json
from datetime import UTC, datetime
from pathlib import Path

from app.domain.documents import VerificationCheck, VerificationReport
from app.domain.sources import SourceSpec
from app.services.ingestion.jobs import (
    Job,
    JobLog,
    ingest_with_retry,
    is_transient,
    read_status,
)
from app.services.ingestion.pipeline import IngestResult
from tests.factories import make_spec


def result(outcome: str, *failed: str, chunks: int = 0) -> IngestResult:
    checks = [
        VerificationCheck(name=name, status="fail", detail=f"{name} failed") for name in failed
    ]
    report = VerificationReport(
        source_id="demo-guidelines",
        url="https://x.gov.in/a.pdf",
        status="rejected" if failed else "verified",
        checks=checks,
        verified_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    return IngestResult("demo-guidelines", outcome, report, chunks, 1.2)  # type: ignore[arg-type]


class Script:
    """An ingest that answers with scripted results, counting its calls."""

    def __init__(self, *results: IngestResult) -> None:
        self.results = list(results)
        self.calls = 0

    def __call__(self, _spec: SourceSpec) -> IngestResult:
        self.calls += 1
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


class TestWhatIsTransient:
    def test_a_download_that_failed_is_transient(self) -> None:
        assert is_transient(result("rejected", "download"))

    def test_a_document_that_is_wrong_is_not(self) -> None:
        assert not is_transient(result("rejected", "identity"))
        assert not is_transient(result("rejected", "official_domain"))
        assert not is_transient(result("rejected", "tls"))

    def test_a_download_failure_with_another_failure_is_not(self) -> None:
        assert not is_transient(result("rejected", "download", "identity"))

    def test_a_source_that_was_indexed_is_not_a_failure(self) -> None:
        assert not is_transient(result("indexed", chunks=5))


class TestRetrying:
    def test_a_transient_failure_is_retried_until_it_works(self) -> None:
        ingest = Script(
            result("rejected", "download"),
            result("rejected", "download"),
            result("indexed", chunks=7),
        )
        pauses: list[float] = []

        outcome = ingest_with_retry(ingest, make_spec(), sleep=pauses.append)

        assert outcome.outcome == "indexed"
        assert ingest.calls == 3
        assert pauses == [2.0, 4.0]  # exponential: 2 s, then 4 s

    def test_it_gives_up_after_the_attempts_it_is_allowed(self) -> None:
        ingest = Script(result("rejected", "download"))

        outcome = ingest_with_retry(ingest, make_spec(), attempts=3, sleep=lambda _s: None)

        assert outcome.outcome == "rejected"
        assert ingest.calls == 3

    def test_a_permanent_failure_is_not_retried(self) -> None:
        ingest = Script(result("rejected", "identity"))
        pauses: list[float] = []

        outcome = ingest_with_retry(ingest, make_spec(), sleep=pauses.append)

        assert outcome.outcome == "rejected"
        assert (ingest.calls, pauses) == (1, [])

    def test_success_and_unchanged_are_not_repeated(self) -> None:
        for outcome in ("indexed", "unchanged"):
            ingest = Script(result(outcome, chunks=3))

            ingest_with_retry(ingest, make_spec(), sleep=lambda _s: None)

            assert ingest.calls == 1


class TestTheStatusRecord:
    def test_every_source_ends_with_its_state_and_why_if_it_failed(self, tmp_path: Path) -> None:
        log = JobLog(tmp_path / "jobs" / "ingest.json")
        ingest_with_retry(Script(result("indexed", chunks=9)), make_spec(id="good-doc"), log=log)
        ingest_with_retry(Script(result("rejected", "identity")), make_spec(id="bad-doc"), log=log)
        log.finish()

        status = read_status(tmp_path / "jobs" / "ingest.json")

        assert status is not None
        assert status["finished_at"] is not None
        jobs = status["jobs"]
        assert jobs["good-doc"]["state"] == "indexed"  # type: ignore[index]
        assert jobs["good-doc"]["passages"] == 9  # type: ignore[index]
        assert jobs["bad-doc"]["state"] == "rejected"  # type: ignore[index]
        assert jobs["bad-doc"]["failed_check"] == "identity"  # type: ignore[index]

    def test_a_retry_in_progress_is_visible(self, tmp_path: Path) -> None:
        path = tmp_path / "ingest.json"
        log = JobLog(path)
        seen: list[str] = []

        def sleeping(_seconds: float) -> None:
            status = read_status(path)
            assert status is not None
            seen.append(status["jobs"]["demo-guidelines"]["state"])  # type: ignore[index]

        ingest_with_retry(
            Script(result("rejected", "download"), result("indexed", chunks=1)),
            make_spec(),
            sleep=sleeping,
            log=log,
        )

        assert seen == ["retrying"]
        assert read_status(path)["jobs"]["demo-guidelines"]["attempts"] == 2  # type: ignore[index]

    def test_the_file_is_replaced_whole_so_a_reader_never_sees_half_of_it(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "ingest.json"
        log = JobLog(path)

        for number in range(5):
            log.update(Job(f"doc-{number}", "running"))
            assert json.loads(path.read_text(encoding="utf-8"))["jobs"]

        assert [p.name for p in tmp_path.iterdir()] == ["ingest.json"]  # no temporary file left

    def test_a_missing_or_broken_file_reads_as_no_run(self, tmp_path: Path) -> None:
        (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

        assert read_status(tmp_path / "missing.json") is None
        assert read_status(tmp_path / "broken.json") is None

    def test_a_detail_is_kept_short(self, tmp_path: Path) -> None:
        long = result("rejected", "identity")
        long.report.checks[0].detail = "x" * 5000
        log = JobLog(tmp_path / "ingest.json")

        ingest_with_retry(Script(long), make_spec(), log=log)

        status = read_status(tmp_path / "ingest.json")
        assert len(status["jobs"]["demo-guidelines"]["detail"]) == 200  # type: ignore[index]
