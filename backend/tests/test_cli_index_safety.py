"""The rebuild that goes wrong: the network is down, every source is rejected, and the index that
was serving visitors has just been emptied. The tools must have kept a verified copy and must be
able to put it back; and two ingestions must never run together."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app import cli
from app.core.config import get_settings
from app.domain.documents import VerificationCheck, VerificationReport
from app.domain.sources import SourceSpec
from app.services.ingestion.lock import IngestLock
from app.services.ingestion.pipeline import IngestResult
from app.services.retrieval.store import VectorStore
from tests.factories import FakeEmbedder


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


class Offline:
    """A pipeline for a network that is down: every source is rejected, nothing is indexed."""

    def __init__(self, **_options: Any) -> None:
        pass

    def ingest(self, spec: SourceSpec, *, force: bool = False) -> IngestResult:
        report = VerificationReport(
            source_id=spec.id,
            url=spec.url,
            status="rejected",
            checks=[VerificationCheck(name="reachable", status="fail", detail="could not connect")],
            verified_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
        return IngestResult(spec.id, "rejected", report, 0, 0.1)


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "IngestionPipeline", Offline)
    monkeypatch.setattr(cli, "OnnxE5Embedder", lambda *_a, **_k: FakeEmbedder())
    monkeypatch.setattr(cli, "_verifier", lambda _settings: None)
    monkeypatch.setattr(cli, "select_sources", lambda specs, _ids: specs[:2])
    monkeypatch.setattr("app.services.ingestion.jobs.time.sleep", lambda _s: None)


def serving_index(directory: Path) -> int:
    """Put a working index in place, as a running site has; returns how many passages."""
    model = get_settings().embedding_model
    store = VectorStore(directory / "chroma", embedding_model=model)
    store.replace_source(
        "wb-svmcm-guidelines",
        ids=["a:0", "a:1", "a:2"],
        documents=["income limit", "marks needed", "how to apply"],
        vectors=[[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
        metadatas=[{"title": "t", "page_start": n} for n in (1, 2, 3)],
        fingerprint="f1",
    )
    store.close()
    return 3


def passages(directory: Path) -> int:
    store = VectorStore(
        directory / "chroma", embedding_model=get_settings().embedding_model, cache_scans=False
    )
    try:
        return sum(source.passages for source in store.sources())
    finally:
        store.close()


def test_a_rebuild_with_every_source_failing_can_be_undone_from_the_backup(
    data_dir: Path, offline: None, capsys: pytest.CaptureFixture[str]
) -> None:
    held = serving_index(data_dir)

    status = cli.main(["ingest", "--rebuild"])

    captured = capsys.readouterr()
    assert status == 1  # reported as a failure, not as success
    assert passages(data_dir) == 0  # the rebuild did empty the index, as it always has
    assert "Backed up the current index" in captured.out
    assert "index-restore" in captured.err  # and it says exactly how to go back

    assert cli.main(["index-restore"]) == 0

    assert passages(data_dir) == held  # everything that was serving visitors is back
    assert "Restored" in capsys.readouterr().out


def test_the_backup_is_listed(
    data_dir: Path, offline: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["index-backups"]) == 0
    assert "No snapshots yet" in capsys.readouterr().out

    serving_index(data_dir)
    cli.main(["ingest", "--rebuild"])
    capsys.readouterr()

    assert cli.main(["index-backups"]) == 0
    assert capsys.readouterr().out.startswith("chroma-")


def test_a_rebuild_on_an_empty_installation_has_nothing_to_back_up(
    data_dir: Path, offline: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["ingest", "--rebuild"]) == 1

    assert "Backed up" not in capsys.readouterr().out


def test_an_ordinary_ingest_that_fails_never_touches_the_index(
    data_dir: Path, offline: None
) -> None:
    held = serving_index(data_dir)

    assert cli.main(["ingest"]) == 1  # every source rejected

    assert passages(data_dir) == held  # no --rebuild: the index is exactly as it was


def test_a_second_ingestion_is_refused_with_its_own_exit_status(
    data_dir: Path, offline: None, capsys: pytest.CaptureFixture[str]
) -> None:
    held = serving_index(data_dir)

    with IngestLock(data_dir / "jobs" / "ingest.lock"):
        status = cli.main(["ingest", "--rebuild"])

    assert status == 3
    assert "already running" in capsys.readouterr().err
    assert passages(data_dir) == held  # refused before anything was touched, not even backed up


def test_the_lock_is_released_after_a_run_so_the_next_one_can_start(
    data_dir: Path, offline: None
) -> None:
    cli.main(["ingest"])

    assert not (data_dir / "jobs" / "ingest.lock").exists()
    assert cli.main(["ingest"]) == 1  # ran again, was not told another one is running


def test_restoring_with_nothing_to_restore_says_so(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["index-restore"]) == 1

    assert "no snapshot" in capsys.readouterr().err.lower()


def test_restoring_a_named_snapshot_that_does_not_exist_changes_nothing(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    held = serving_index(data_dir)

    assert cli.main(["index-restore", "chroma-nope"]) == 2

    assert "no backup" in capsys.readouterr().err.lower()
    assert passages(data_dir) == held
