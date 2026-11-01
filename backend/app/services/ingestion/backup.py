"""Snapshots of the index, checked before they are trusted, and a way back.

``ingest --rebuild`` throws the old index away first. If the sources then fail to download (the
network is down, a site has moved) the visitors would be left with nothing to search. So a rebuild
starts with a copy of the index, and the copy is *opened and counted* against the original: a
backup that has not been read back is a hope, not a backup. ``restore`` puts a snapshot back, and
keeps what it replaces, so that a restore can itself be undone. Nothing here deletes the index; the
only thing pruned is the oldest snapshots, and only inside the backups folder.

The index is derived data (``ingest`` can always rebuild it from the registry), so these are for
speed and for a rebuild that fails half way, not the only copy of anything irreplaceable.
"""

import logging
import shutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.domain.errors import IndexingError
from app.services.retrieval.store import VectorStore, mark_changed

logger = logging.getLogger(__name__)

PREFIX = "chroma-"
KEEP = 3  # snapshots kept; older ones are pruned after a new one is validated


def _stamp(now: datetime) -> str:
    return now.strftime("%Y%m%d-%H%M%S")


def list_snapshots(backups: Path) -> list[Path]:
    """Snapshots, oldest first (the names sort by time)."""
    if not backups.is_dir():
        return []
    return sorted(p for p in backups.iterdir() if p.is_dir() and p.name.startswith(PREFIX))


def snapshot_index(
    chroma: Path,
    backups: Path,
    *,
    embedding_model: str,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path | None:
    """Copy the index, prove the copy matches, prune old copies. None if there is nothing to copy.

    Raises ``IndexingError`` (and leaves the original untouched) if the copy cannot be read back
    with the same contents, so the caller must not go on to destroy the original.
    """
    if not chroma.is_dir() or not any(chroma.iterdir()):
        return None
    expected = _counts(chroma, embedding_model)
    target = backups / f"{PREFIX}{_stamp(now())}-{uuid.uuid4().hex[:4]}"
    backups.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(chroma, target)
        found = _counts(target, embedding_model)
        if found != expected:
            raise IndexingError(
                "The backup of the index did not match the index it was copied from "
                f"({sum(found.values())} passages against {sum(expected.values())}).",
                code="backup_invalid",
            )
    except BaseException as error:
        shutil.rmtree(target, ignore_errors=True)  # a bad copy must never look like a good one
        if isinstance(error, IndexingError):
            raise
        if isinstance(error, Exception):
            raise IndexingError(
                f"The index could not be backed up: {type(error).__name__}.", code="backup_failed"
            ) from error
        raise
    for old in list_snapshots(backups)[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)
    logger.info(
        "backed up the index: %d passages in %d sources", sum(expected.values()), len(expected)
    )
    return target


def restore_snapshot(
    snapshot: Path,
    chroma: Path,
    *,
    embedding_model: str,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path | None:
    """Put a snapshot in place of the index. Returns where the replaced index was moved to.

    The snapshot is read back first and refused if it is empty or unreadable. The index being
    replaced is moved aside, not deleted, so a mistaken restore can be reversed by hand. Raises
    ``IndexingError`` if the index is in use (stop the API first: on Windows an open index cannot
    be moved).
    """
    if not snapshot.is_dir():
        raise IndexingError(f"There is no backup at {snapshot}.", code="backup_missing")
    if sum(_counts(snapshot, embedding_model).values()) == 0:
        raise IndexingError(
            "That backup holds no passages; it was not restored.", code="backup_empty"
        )

    aside: Path | None = None
    staging = chroma.with_name(f"{chroma.name}.restoring-{uuid.uuid4().hex[:6]}")
    try:
        shutil.copytree(snapshot, staging)  # a failed copy leaves the index as it was
        if chroma.exists():
            aside = chroma.with_name(f"{chroma.name}.replaced-{_stamp(now())}")
            chroma.rename(aside)
        staging.rename(chroma)
    except OSError as error:
        shutil.rmtree(staging, ignore_errors=True)
        if aside is not None and not chroma.exists():
            aside.rename(chroma)  # put the original back
        raise IndexingError(
            "The index could not be replaced; stop the API (or any ingest) that has it open and "
            "try again. Nothing was changed.",
            code="restore_failed",
        ) from error
    mark_changed(chroma)  # a running API sees the new stamp and opens the restored index
    return aside


def _counts(directory: Path, embedding_model: str) -> dict[str, int]:
    """Passages per source, by opening the index as a reader would."""
    store = VectorStore(directory, embedding_model=embedding_model, cache_scans=False)
    try:
        return {source.id: source.passages for source in store.sources()}
    finally:
        store.close()
