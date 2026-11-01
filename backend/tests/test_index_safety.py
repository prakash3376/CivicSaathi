"""The index is what every answer is built on: it is backed up before a rebuild, the backup is read
back, restoring is proven to bring everything back, and only one ingestion may write at a time."""

import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.errors import IndexingError
from app.services.ingestion.backup import (
    KEEP,
    list_snapshots,
    restore_snapshot,
    snapshot_index,
)
from app.services.ingestion.lock import IngestBusyError, IngestLock, lock_state
from app.services.retrieval.store import VectorStore

MODEL = "model-a"


def fill(chroma: Path, sources: dict[str, int]) -> VectorStore:
    store = VectorStore(chroma, embedding_model=MODEL)
    for source_id, count in sources.items():
        store.replace_source(
            source_id,
            ids=[f"{source_id}:{n}" for n in range(count)],
            documents=[f"{source_id} text {n}" for n in range(count)],
            vectors=[[1.0, float(n)] for n in range(count)],
            metadatas=[{"title": source_id, "page_start": n + 1} for n in range(count)],
            fingerprint="f1",
        )
    return store


def counts(chroma: Path) -> dict[str, int]:
    store = VectorStore(chroma, embedding_model=MODEL, cache_scans=False)
    try:
        return {s.id: s.passages for s in store.sources()}
    finally:
        store.close()


def at(second: int) -> datetime:
    return datetime(2026, 11, 1, 12, 0, second, tzinfo=UTC)


def dead_lock(path: Path, pid: int = 4242) -> None:
    path.write_text(f'{{"pid": {pid}, "host": "gone", "started": "earlier", "token": "dead"}}')
    old = time.time() - 600
    os.utime(path, (old, old))  # no heartbeat for ten minutes


class TestBackup:
    def test_there_is_nothing_to_back_up_before_the_first_ingest(self, tmp_path: Path) -> None:
        found = snapshot_index(tmp_path / "chroma", tmp_path / "backups", embedding_model=MODEL)

        assert found is None

    def test_a_snapshot_is_read_back_and_holds_what_the_index_held(self, tmp_path: Path) -> None:
        live = tmp_path / "chroma"
        fill(live, {"a": 3, "b": 2}).close()

        snapshot = snapshot_index(live, tmp_path / "backups", embedding_model=MODEL)

        assert snapshot is not None
        assert counts(snapshot) == {"a": 3, "b": 2}

    def test_restoring_brings_back_everything_after_the_index_was_destroyed(
        self, tmp_path: Path
    ) -> None:
        # The whole point: the rebuild wipes the index, the sources fail, and the visitors must not
        # be left with nothing. This is the recovery, executed.
        live = tmp_path / "chroma"
        fill(live, {"a": 3, "b": 2}).close()
        snapshot = snapshot_index(live, tmp_path / "backups", embedding_model=MODEL)
        assert snapshot is not None
        VectorStore(live, embedding_model=MODEL, rebuild=True).close()  # what --rebuild does first
        assert counts(live) == {}  # the index is empty

        replaced = restore_snapshot(snapshot, live, embedding_model=MODEL, now=lambda: at(5))

        assert counts(live) == {"a": 3, "b": 2}
        assert replaced is not None
        assert counts(replaced) == {}  # what was replaced is kept, not deleted

    def test_a_restored_index_can_be_searched_like_the_original(self, tmp_path: Path) -> None:
        live = tmp_path / "chroma"
        fill(live, {"a": 2}).close()
        snapshot = snapshot_index(live, tmp_path / "backups", embedding_model=MODEL)
        assert snapshot is not None
        VectorStore(live, embedding_model=MODEL, rebuild=True).close()
        restore_snapshot(snapshot, live, embedding_model=MODEL)

        store = VectorStore(live, embedding_model=MODEL)
        hits = store.search([1.0, 0.0], k=2)
        store.close()

        assert {hit.text for hit in hits} == {"a text 0", "a text 1"}

    def test_a_running_reader_is_told_to_open_the_restored_index(self, tmp_path: Path) -> None:
        live = tmp_path / "chroma"
        fill(live, {"a": 2}).close()
        snapshot = snapshot_index(live, tmp_path / "backups", embedding_model=MODEL)
        assert snapshot is not None
        VectorStore(live, embedding_model=MODEL, rebuild=True).close()
        stamp_before = (live / "last-update").read_text()

        restore_snapshot(snapshot, live, embedding_model=MODEL)

        assert (live / "last-update").read_text() not in {stamp_before, ""}

    def test_an_empty_backup_is_refused_rather_than_restored_over_a_good_index(
        self, tmp_path: Path
    ) -> None:
        live = tmp_path / "chroma"
        fill(live, {"a": 2}).close()
        empty = tmp_path / "backups" / "chroma-empty"
        VectorStore(empty, embedding_model=MODEL).close()

        with pytest.raises(IndexingError) as error:
            restore_snapshot(empty, live, embedding_model=MODEL)

        assert error.value.code == "backup_empty"
        assert counts(live) == {"a": 2}  # untouched

    def test_a_missing_backup_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(IndexingError) as error:
            restore_snapshot(tmp_path / "nope", tmp_path / "chroma", embedding_model=MODEL)

        assert error.value.code == "backup_missing"

    def test_a_backup_that_does_not_match_is_deleted_and_the_original_left_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app.services.ingestion.backup as backup

        live = tmp_path / "chroma"
        fill(live, {"a": 3}).close()
        real = backup._counts
        calls: list[Path] = []

        def lying(directory: Path, model: str) -> dict[str, int]:
            calls.append(directory)
            return real(directory, model) if len(calls) == 1 else {"a": 1}  # the copy "lost" rows

        monkeypatch.setattr(backup, "_counts", lying)

        with pytest.raises(IndexingError) as error:
            snapshot_index(live, tmp_path / "backups", embedding_model=MODEL)

        assert error.value.code == "backup_invalid"
        assert list_snapshots(tmp_path / "backups") == []  # a bad copy never looks like a good one
        assert counts(live) == {"a": 3}

    def test_only_the_newest_snapshots_are_kept(self, tmp_path: Path) -> None:
        live = tmp_path / "chroma"
        fill(live, {"a": 1}).close()

        for second in range(KEEP + 2):
            snapshot_index(
                live, tmp_path / "backups", embedding_model=MODEL, now=lambda s=second: at(s)
            )

        assert len(list_snapshots(tmp_path / "backups")) == KEEP
        assert counts(live) == {"a": 1}  # pruning never touches the index itself


class TestLock:
    def test_a_second_ingestion_is_refused_while_the_first_runs(self, tmp_path: Path) -> None:
        path = tmp_path / "jobs" / "ingest.lock"

        with IngestLock(path):
            with pytest.raises(IngestBusyError) as error:
                IngestLock(path).acquire()
            assert error.value.code == "ingest_busy"
            assert "already running" in error.value.message

        again = IngestLock(path)
        again.acquire()  # released on exit: the next one may run
        again.release()

    def test_threads_racing_for_the_lock_have_exactly_one_winner(self, tmp_path: Path) -> None:
        path = tmp_path / "ingest.lock"
        winners: list[IngestLock] = []
        losers: list[str] = []
        barrier = threading.Barrier(8)

        def contend() -> None:
            lock = IngestLock(path, heartbeat_seconds=60)
            barrier.wait()
            try:
                lock.acquire()
                winners.append(lock)
            except IngestBusyError:
                losers.append("busy")

        threads = [threading.Thread(target=contend) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert (len(winners), len(losers)) == (1, 7)
        winners[0].release()

    def test_a_lock_left_by_a_killed_process_is_taken_over_once_its_lease_has_run_out(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "ingest.lock"
        dead_lock(path)

        lock = IngestLock(path, lease_seconds=90)
        lock.acquire()

        assert lock.took_over_stale
        lock.release()
        assert not path.exists()

    def test_a_lock_that_is_still_beating_is_never_taken_over(self, tmp_path: Path) -> None:
        path = tmp_path / "ingest.lock"
        path.write_text('{"pid": 4242, "host": "busy", "started": "now", "token": "alive"}')

        with pytest.raises(IngestBusyError):
            IngestLock(path, lease_seconds=90).acquire()

        assert path.exists()  # and the real holder's file was not touched

    def test_the_heartbeat_keeps_a_long_ingestion_from_looking_dead(self, tmp_path: Path) -> None:
        path = tmp_path / "ingest.lock"
        with IngestLock(path, lease_seconds=1.0, heartbeat_seconds=0.1):
            time.sleep(1.6)  # longer than the lease: without a heartbeat it would be stale

            with pytest.raises(IngestBusyError):
                IngestLock(path, lease_seconds=1.0).acquire()

    def test_release_does_not_delete_a_lock_that_a_successor_now_owns(self, tmp_path: Path) -> None:
        path = tmp_path / "ingest.lock"
        first = IngestLock(path, lease_seconds=1.0, heartbeat_seconds=60)
        first.acquire()
        old = time.time() - 600
        os.utime(path, (old, old))  # the first looks dead (its heartbeat is slow)
        second = IngestLock(path, lease_seconds=1.0, heartbeat_seconds=60)
        second.acquire()

        first.release()  # the presumed-dead one wakes up and finishes

        assert path.exists()  # the successor's lock survives
        second.release()
        assert not path.exists()

    def test_the_state_is_reported_for_the_admin_page(self, tmp_path: Path) -> None:
        path = tmp_path / "ingest.lock"
        assert lock_state(path) == {"state": "idle"}

        with IngestLock(path):
            assert lock_state(path)["state"] == "running"

        dead_lock(path, pid=7)
        report = lock_state(path)
        assert (report["state"], report["pid"]) == ("interrupted", 7)
