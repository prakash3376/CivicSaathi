"""The ChromaDB index of passages.

Vectors are always computed by us and handed to Chroma; the collection has no embedding function
of its own. A query by text therefore fails loudly instead of silently using a different model,
and the model that built the index is recorded so a mismatch is caught when the index is opened.

Two processes use the index: the API reads it for as long as it runs, and the ingest command
rewrites it. Chroma does not cope with that by itself. A reader that stays open while another
process replaces a source keeps a stale in-memory copy of the vector index, and its next search
fails. So every change leaves a stamp file in the index folder, and a reader that finds a new stamp
closes its Chroma client and opens the index again before it reads. If a search still meets an
inconsistent index (a write that left no stamp, or landed in the middle of the query) it opens the
index once more and retries. Access is serialised with a lock, so that opening the index again can
never pull the client away from a request that is using it.
"""

import logging
import threading
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.api.types import Where
from chromadb.config import Settings

from app.domain.errors import IndexingError

logger = logging.getLogger(__name__)

COLLECTION_NAME = "official_chunks"
_BATCH_SIZE = 200
_STAMP_FILE = "last-update"  # in the index folder; rewritten by every change
MetadataValue = str | int | float | bool


def _as_embeddings(vectors: Sequence[Sequence[float]]) -> list[Sequence[float] | Sequence[int]]:
    return [list(vector) for vector in vectors]


def mark_changed(directory: Path) -> None:
    """Leave a new change stamp in an index folder, so that a process reading it opens it again."""
    (directory / _STAMP_FILE).write_text(uuid.uuid4().hex, encoding="ascii")


@dataclass(frozen=True)
class SearchHit:
    id: str
    text: str
    score: float  # cosine similarity: 1.0 is identical meaning, near 0 is unrelated
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IndexedSource:
    """What the index holds for one source."""

    id: str
    passages: int
    # The metadata stored with the source's passages. ``ocr`` is true if any passage was read from
    # a scan.
    metadata: dict[str, Any]


class VectorStore:
    """A persistent Chroma collection holding every passage from every verified source."""

    def __init__(
        self,
        directory: Path,
        *,
        embedding_model: str,
        rebuild: bool = False,
        cache_scans: bool = True,
    ) -> None:
        """Open (or create) the index. ``rebuild`` discards what is there and starts empty.

        ``cache_scans`` keeps the result of reading every passage's metadata (the list of
        sources and their counts) until the index changes. The change stamp decides: every
        write, by this process or another, leaves a new one, so the copy is never older than
        the index.
        """
        directory.mkdir(parents=True, exist_ok=True)
        self._directory = directory
        self._embedding_model = embedding_model
        self._lock = threading.RLock()
        self._cache_scans = cache_scans
        self._scan: tuple[str | None, list[dict[str, Any]]] | None = None
        self.scan_hits = 0  # reads served from the copy, for the health page
        self.scan_misses = 0
        self._client: ClientAPI
        self._collection: chromadb.Collection
        self._stamp: str | None
        self._connect(rebuild=rebuild)
        if rebuild:
            self._touch()

    # --- keeping up with other processes ---------------------------------------------------

    def _connect(self, *, rebuild: bool = False) -> None:
        self._stamp = self._read_stamp()  # read first: a change after this is noticed next time
        # Anonymous telemetry is switched off: nothing about our documents or queries leaves here.
        self._client = chromadb.PersistentClient(
            path=str(self._directory), settings=Settings(anonymized_telemetry=False)
        )
        if rebuild:
            with suppress(Exception):  # nothing to delete on a first run
                self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._open()

    def _reconnect(self) -> None:
        """Close this process's Chroma client and open the index afresh."""
        close = getattr(self._client, "close", None)  # on Chroma's client, not on its interface
        if close is not None:
            with suppress(Exception):
                close()
        # Chroma hands out one client per folder per process; forget it, or the new client would
        # be the old, stale one.
        SharedSystemClient.clear_system_cache()
        self._connect()

    def close(self) -> None:
        """Let go of the index's files (a copy cannot be moved or deleted while it is open)."""
        close = getattr(self._client, "close", None)
        if close is not None:
            with suppress(Exception):
                close()
        SharedSystemClient.clear_system_cache()

    def _read_stamp(self) -> str | None:
        try:
            return (self._directory / _STAMP_FILE).read_text(encoding="ascii", errors="replace")
        except OSError:
            return None

    def _touch(self) -> None:
        """Record that the index changed, so that other processes reading it open it again."""
        stamp = uuid.uuid4().hex  # unique even when two changes land within one clock tick
        (self._directory / _STAMP_FILE).write_text(stamp, encoding="ascii")
        self._stamp = stamp

    def _follow_other_writers(self) -> None:
        if self._read_stamp() != self._stamp:
            logger.info("The index was changed by another process; opening it again")
            self._reconnect()

    # --- the index --------------------------------------------------------------------------

    def _open(self) -> chromadb.Collection:
        collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"embedding_model": self._embedding_model},
        )
        built_with = (collection.metadata or {}).get("embedding_model")
        if built_with != self._embedding_model:
            raise IndexingError(
                f"The index was built with '{built_with}' but '{self._embedding_model}' is "
                "configured. Vectors from different models cannot be compared: run the ingest "
                "command with --rebuild to re-embed everything with the configured model.",
                code="embedding_model_changed",
            )
        return collection

    def fingerprint(self, source_id: str) -> str | None:
        """The fingerprint the source was last indexed with, or ``None`` if it is not indexed."""
        with self._lock:
            self._follow_other_writers()
            found = self._collection.get(
                where={"source_id": source_id}, limit=1, include=["metadatas"]
            )
        metadatas = found["metadatas"] or []
        return str(metadatas[0]["fingerprint"]) if metadatas else None

    def replace_source(
        self,
        source_id: str,
        *,
        ids: Sequence[str],
        documents: Sequence[str],
        vectors: Sequence[Sequence[float]],
        metadatas: Sequence[Mapping[str, MetadataValue]],
        fingerprint: str,
    ) -> None:
        """Index a source's passages, then drop whatever was indexed for it before.

        New passages are written first and stale ones removed after, so a query during the
        update sees the old or the new version, never an empty source.
        """
        stamped: list[Mapping[str, Any]] = [
            {**metadata, "source_id": source_id, "fingerprint": fingerprint}
            for metadata in metadatas
        ]
        with self._lock:
            for start in range(0, len(ids), _BATCH_SIZE):
                end = start + _BATCH_SIZE
                self._collection.upsert(
                    ids=list(ids[start:end]),
                    documents=list(documents[start:end]),
                    embeddings=_as_embeddings(vectors[start:end]),
                    metadatas=stamped[start:end],
                )
            # Chroma types filter operators as literals, which mypy cannot infer for a nested dict.
            stale = cast(
                "Where",
                {"$and": [{"source_id": source_id}, {"fingerprint": {"$ne": fingerprint}}]},
            )
            self._collection.delete(where=stale)
            self._touch()

    def refresh_source(self, source_id: str, metadata: Mapping[str, MetadataValue]) -> None:
        """Update fields (such as when it was last verified) on a source's passages in place."""
        with self._lock:
            ids = self._collection.get(where={"source_id": source_id}, include=[])["ids"]
            for start in range(0, len(ids), _BATCH_SIZE):
                batch = ids[start : start + _BATCH_SIZE]
                self._collection.update(ids=batch, metadatas=[dict(metadata) for _ in batch])
            self._touch()

    def search(
        self, vector: Sequence[float], *, k: int = 5, source_ids: Sequence[str] | None = None
    ) -> list[SearchHit]:
        """The ``k`` passages closest in meaning to ``vector``, optionally within some sources."""
        with self._lock:
            self._follow_other_writers()
            try:
                return self._query(vector, k, source_ids)
            except Exception as first:
                # The index changed under us in a way no stamp announced. Look at it again.
                logger.warning("The index looked inconsistent (%s); opening it again", first)
                self._reconnect()
                try:
                    return self._query(vector, k, source_ids)
                except Exception as error:
                    raise IndexingError(
                        "The index could not be read. If this keeps happening, run the ingest "
                        "command with --rebuild.",
                        code="index_unreadable",
                    ) from error

    def _query(
        self, vector: Sequence[float], k: int, source_ids: Sequence[str] | None
    ) -> list[SearchHit]:
        # Chroma types filter operators as literals, which mypy cannot infer for a nested dict.
        only_these_sources = (
            cast("Where", {"source_id": {"$in": list(source_ids)}}) if source_ids else None
        )
        result = self._collection.query(
            query_embeddings=_as_embeddings([vector]),
            n_results=k,
            where=only_these_sources,
            include=["documents", "metadatas", "distances"],
        )
        ids = result["ids"][0]
        documents = (result["documents"] or [[]])[0]
        metadatas = (result["metadatas"] or [[]])[0]
        distances = (result["distances"] or [[]])[0]
        hits: list[SearchHit] = []
        for hit_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            if text is None or metadata is None:  # the vector index names a passage that is gone
                raise IndexingError("The vector index is out of date.", code="index_stale")
            hits.append(SearchHit(hit_id, text, 1.0 - distance, dict(metadata)))
        return hits

    def size(self) -> int:
        """How many passages the index holds in all."""
        with self._lock:
            self._follow_other_writers()
            return self._collection.count()

    def scan_stats(self) -> dict[str, int]:
        """Reads of the passages' metadata served from the copy, and reads that scanned them."""
        return {"hits": self.scan_hits, "misses": self.scan_misses}

    def version(self) -> str:
        """Changes whenever the index does, so that anything derived from it can be rebuilt."""
        with self._lock:
            self._follow_other_writers()
            return self._stamp or ""

    def corpus(self) -> list[tuple[str, str, dict[str, Any]]]:
        """Every passage as (id, text, metadata): for building a keyword index over the text."""
        with self._lock:
            self._follow_other_writers()
            found = self._collection.get(include=["documents", "metadatas"])
        ids = found["ids"]
        documents = found["documents"] or []
        metadatas = found["metadatas"] or []
        return [
            (ident, text, dict(meta))
            for ident, text, meta in zip(ids, documents, metadatas, strict=True)
            if text is not None and meta is not None
        ]

    def similarities(self, vector: Sequence[float], ids: Sequence[str]) -> dict[str, float]:
        """Cosine similarity of ``vector`` to the stored vectors of the given passages."""
        if not ids:
            return {}
        with self._lock:
            self._follow_other_writers()
            found = self._collection.get(ids=list(ids), include=["embeddings"])
        norm = sum(x * x for x in vector) ** 0.5 or 1.0
        result: dict[str, float] = {}
        embeddings = found["embeddings"]
        for ident, stored in zip(
            found["ids"], embeddings if embeddings is not None else [], strict=True
        ):
            other = [float(x) for x in stored]
            size = sum(x * x for x in other) ** 0.5 or 1.0
            result[ident] = sum(a * b for a, b in zip(vector, other, strict=True)) / (norm * size)
        return result

    def _metadatas(self) -> list[dict[str, Any]]:
        """The metadata of every passage. Reading it all is the slow part of listing sources,
        so it is kept until the index changes. The caller holds the lock."""
        self._follow_other_writers()
        if self._cache_scans and self._scan is not None and self._scan[0] == self._stamp:
            self.scan_hits += 1
            return self._scan[1]
        self.scan_misses += 1
        found = self._collection.get(include=["metadatas"])["metadatas"] or []
        metadatas = [dict(item) for item in found]
        if self._cache_scans:
            self._scan = (self._stamp, metadatas)
        return metadatas

    def counts(self) -> dict[str, int]:
        """How many passages each source has in the index."""
        with self._lock:
            metadatas = self._metadatas()
        return dict(Counter(str(metadata["source_id"]) for metadata in metadatas))

    def sources(self) -> list[IndexedSource]:
        """Every indexed source with its stored metadata, ordered by id."""
        with self._lock:
            metadatas = self._metadatas()
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for metadata in metadatas:
            grouped.setdefault(str(metadata["source_id"]), []).append(metadata)
        return [
            IndexedSource(
                id=source_id,
                passages=len(items),
                metadata={**items[0], "ocr": any(bool(item.get("ocr")) for item in items)},
            )
            for source_id, items in sorted(grouped.items())
        ]
