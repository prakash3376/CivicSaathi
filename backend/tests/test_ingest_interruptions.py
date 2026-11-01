"""Ingestion stopped half way, at every stage, and run again: the index must end up correct.

The stages are: download, read, embed, write the new passages, remove the old ones, save the audit
record. A crash (a killed process, a full disk, an embedding failure) can fall between any two of
them. The promise tested here is that the next run heals the state, never duplicates a passage, and
never calls a half-written source "unchanged".
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.domain.documents import VerificationCheck, VerificationReport
from app.domain.errors import IndexingError
from app.services.ingestion.jobs import Job, JobLog, ingest_with_retry, read_status
from app.services.ingestion.pipeline import IngestResult
from app.services.ingestion.reconcile import reconcile
from tests.factories import make_spec
from tests.test_pipeline import Setup, guidelines_pdf

V2 = guidelines_pdf(income="3,00,000")


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


def publish_a_new_version(setup: Setup) -> None:
    setup.network.pages["/guidelines.pdf"] = (200, V2, "application/pdf")


def texts(setup: Setup) -> list[str]:
    hits = setup.store.search(setup.embedder.embed_query("family income ceiling"), k=50)
    return [hit.text for hit in hits]


class Crash(Exception):
    """A process dying: not a domain error, so nothing in the pipeline can catch it politely."""


class TestAnInterruptionBetweenTheStages:
    def test_a_failure_while_embedding_leaves_the_old_index_untouched(self, setup: Setup) -> None:
        first = setup.ingest()
        publish_a_new_version(setup)

        def broken(_texts: list[str]) -> Any:
            raise IndexingError("the embedding model failed", code="embedding_failed")

        setup.embedder.embed_documents = broken  # type: ignore[method-assign]

        with pytest.raises(IndexingError):
            setup.ingest()

        assert setup.store.counts() == {"demo-guidelines": first.chunks}
        assert any("2,50,000" in text for text in texts(setup))  # visitors still get the old text
        assert not any("3,00,000" in text for text in texts(setup))

    def test_a_crash_after_writing_the_new_passages_but_before_removing_the_old_heals_on_rerun(
        self, setup: Setup, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = setup.ingest()
        publish_a_new_version(setup)

        def die(**_where: Any) -> None:
            raise Crash

        monkeypatch.setattr(setup.store._collection, "delete", die)
        with pytest.raises(Crash):
            setup.ingest()
        monkeypatch.undo()
        assert setup.store.counts()["demo-guidelines"] > first.chunks  # old and new, mixed

        healed = setup.ingest()

        assert healed.outcome == "indexed"  # it did not call the mixed state "unchanged"
        assert setup.store.counts() == {"demo-guidelines": healed.chunks}
        assert len(texts(setup)) == len(set(texts(setup)))  # no passage twice
        assert not any("Rs.2,50,000" in text for text in texts(setup))
        assert any("3,00,000" in text for text in texts(setup))

    def test_a_half_written_source_is_never_taken_for_unchanged_even_if_the_index_looks_new(
        self, setup: Setup, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The worst luck: the crash left the new fingerprint on the passage the index reads first,
        # while the audit record still holds the old one. Trusting the index alone would skip it.
        setup.ingest()
        publish_a_new_version(setup)
        new_fingerprint = setup.pipeline._fingerprint(
            make_spec(),
            setup.pipeline._verifier.download(make_spec(), setup.now)[1],  # type: ignore[arg-type,index]
        )
        monkeypatch.setattr(setup.store, "fingerprint", lambda _source: new_fingerprint)

        result = setup.ingest()

        assert result.outcome == "indexed"

    def test_a_crash_after_indexing_but_before_the_record_is_saved_heals_without_duplicates(
        self, setup: Setup, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def die(_record: object) -> None:
            raise Crash

        monkeypatch.setattr(setup.artifacts, "save_record", die)
        with pytest.raises(Crash):
            setup.ingest()
        monkeypatch.undo()
        indexed_before = setup.store.counts()["demo-guidelines"]

        result = setup.ingest()

        assert result.outcome == "indexed"  # no record: it cannot be trusted as finished
        assert setup.store.counts() == {"demo-guidelines": indexed_before}  # same ids: no doubles
        assert len(texts(setup)) == len(set(texts(setup)))

    def test_a_rejected_run_never_touches_what_is_indexed(self, setup: Setup) -> None:
        first = setup.ingest()
        setup.network.pages["/guidelines.pdf"] = (503, b"", "text/plain")  # the site is down

        result = setup.ingest()

        assert result.outcome == "rejected"
        assert setup.store.counts() == {"demo-guidelines": first.chunks}

    def test_running_again_after_a_clean_run_changes_nothing(self, setup: Setup) -> None:
        setup.ingest()
        before = texts(setup)

        again = setup.ingest()

        assert again.outcome == "unchanged"
        assert texts(setup) == before


class TestReconciliation:
    def registered(self) -> set[str]:
        return {"demo-guidelines"}

    def test_a_consistent_installation_has_no_findings(self, setup: Setup) -> None:
        setup.ingest()

        assert (
            reconcile(
                registered=self.registered(),
                indexed=setup.store.counts(),
                artifacts=setup.artifacts,
            )
            == []
        )

    def test_passages_of_a_source_that_left_the_registry_are_reported_not_deleted(
        self, setup: Setup
    ) -> None:
        setup.ingest()

        found = reconcile(registered=set(), indexed=setup.store.counts(), artifacts=setup.artifacts)

        assert [(f.severity, f.code, f.subject) for f in found] == [
            ("error", "orphaned_passages", "demo-guidelines")
        ]
        assert setup.store.counts()  # reporting changed nothing

    def test_a_registered_source_with_nothing_indexed_is_a_warning(self, setup: Setup) -> None:
        found = reconcile(registered=self.registered(), indexed={}, artifacts=setup.artifacts)

        assert [(f.severity, f.code) for f in found] == [("warning", "not_indexed")]

    def test_a_partly_deleted_source_is_found_by_its_passage_count(
        self, setup: Setup, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = setup.ingest()
        some = setup.store._collection.get(limit=1, include=[])["ids"]
        setup.store._collection.delete(ids=some)
        setup.store._touch()

        found = reconcile(
            registered=self.registered(), indexed=setup.store.counts(), artifacts=setup.artifacts
        )

        assert [f.code for f in found] == ["passage_count_differs"]
        assert str(first.chunks) in found[0].detail
        assert "ingest --force" in found[0].detail  # and it says how to heal it

    def test_a_corrupt_record_is_reported(self, setup: Setup) -> None:
        setup.ingest()
        (setup.artifacts.root / "parsed" / "demo-guidelines.json").write_text("{ not json")

        found = reconcile(
            registered=self.registered(), indexed=setup.store.counts(), artifacts=setup.artifacts
        )

        assert [f.code for f in found] == ["record_unreadable"]

    def test_an_old_temp_file_is_a_warning_and_a_fresh_one_is_a_write_in_progress(
        self, setup: Setup
    ) -> None:
        setup.ingest()
        old = setup.artifacts.root / "parsed" / "x.json.tmp"
        fresh = setup.artifacts.root / "raw" / "y.tmp"
        old.write_text("half")
        fresh.parent.mkdir(parents=True, exist_ok=True)
        fresh.write_text("half")
        import os
        import time

        long_ago = time.time() - 7200
        os.utime(old, (long_ago, long_ago))

        found = reconcile(
            registered=self.registered(), indexed=setup.store.counts(), artifacts=setup.artifacts
        )

        assert [(f.code, f.subject) for f in found] == [
            ("leftover_temp_file", str(Path("parsed") / "x.json.tmp"))
        ]
        assert old.exists()  # reported, never deleted


def rejected(source_id: str = "demo-guidelines") -> IngestResult:
    report = VerificationReport(
        source_id=source_id,
        url="https://x.gov.in/a.pdf",
        status="rejected",
        checks=[VerificationCheck(name="download", status="fail", detail="timed out")],
        verified_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    return IngestResult(source_id, "rejected", report, 0, 0.1)


class TestOneFailingSourceNeverStopsTheRest:
    def test_a_domain_error_becomes_a_rejected_source_with_its_reason(self, tmp_path: Path) -> None:
        log = JobLog(tmp_path / "ingest.json")

        def ingest(_spec: object) -> IngestResult:
            raise IndexingError("the vector store failed", code="store_failed")

        result = ingest_with_retry(ingest, make_spec(), log=log, sleep=lambda _s: None)  # type: ignore[arg-type]

        assert result.outcome == "rejected"
        job = (read_status(tmp_path / "ingest.json") or {})["jobs"]["demo-guidelines"]  # type: ignore[index]
        assert job["state"] == "rejected"
        assert job["failed_check"] == "indexing"
        assert "vector store failed" in job["detail"]

    def test_a_bug_is_not_hidden_but_the_job_is_not_left_running(self, tmp_path: Path) -> None:
        log = JobLog(tmp_path / "ingest.json")
        log.update(Job("demo-guidelines", "running"))

        def ingest(_spec: object) -> IngestResult:
            raise ZeroDivisionError

        with pytest.raises(ZeroDivisionError):
            ingest_with_retry(ingest, make_spec(), log=log, sleep=lambda _s: None)  # type: ignore[arg-type]

        job = (read_status(tmp_path / "ingest.json") or {})["jobs"]["demo-guidelines"]  # type: ignore[index]
        assert job["state"] == "failed"  # never "running" for a process that is no longer there
        assert job["detail"] == "ZeroDivisionError"  # the kind of error only: never its text
