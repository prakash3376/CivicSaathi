import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from app.core.config import BACKEND_DIR
from app.domain.errors import IndexingError
from app.services.retrieval.store import VectorStore


def open_store(tmp_path: Path, model: str = "model-a", *, rebuild: bool = False) -> VectorStore:
    return VectorStore(tmp_path / "chroma", embedding_model=model, rebuild=rebuild)


def index(
    store: VectorStore,
    source_id: str,
    vectors: list[list[float]],
    *,
    fingerprint: str = "f1",
    texts: list[str] | None = None,
) -> None:
    texts = texts or [f"{source_id} passage {n}" for n in range(len(vectors))]
    store.replace_source(
        source_id,
        ids=[f"{source_id}:{fingerprint}:{n}" for n in range(len(vectors))],
        documents=texts,
        vectors=vectors,
        metadatas=[
            {"title": f"Title of {source_id}", "page_start": n + 1} for n in range(len(vectors))
        ],
        fingerprint=fingerprint,
    )


class TestSearch:
    def test_returns_the_closest_passages_with_a_similarity_score_and_metadata(
        self, tmp_path: Path
    ) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0], [0.0, 1.0]], texts=["about income", "about marks"])

        hits = store.search([0.9, 0.1], k=2)

        assert [hit.text for hit in hits] == ["about income", "about marks"]
        assert hits[0].score > 0.99 > hits[1].score
        assert hits[0].metadata["title"] == "Title of a"
        assert hits[0].metadata["source_id"] == "a"  # stamped by the store

    def test_can_be_limited_to_one_source(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0]])
        index(store, "b", [[1.0, 0.1]])

        hits = store.search([1.0, 0.0], k=5, source_ids=["b"])

        assert {hit.metadata["source_id"] for hit in hits} == {"b"}

    def test_can_be_limited_to_several_sources(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0]])
        index(store, "b", [[1.0, 0.1]])
        index(store, "c", [[1.0, 0.2]])

        hits = store.search([1.0, 0.0], k=5, source_ids=["a", "c"])

        assert {hit.metadata["source_id"] for hit in hits} == {"a", "c"}

    def test_an_unknown_source_finds_nothing(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0]])

        assert store.search([1.0, 0.0], k=5, source_ids=["nope"]) == []

    def test_an_empty_index_returns_nothing(self, tmp_path: Path) -> None:
        assert open_store(tmp_path).search([1.0, 0.0]) == []


class TestReplaceSource:
    def test_remembers_the_fingerprint_it_was_indexed_with(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        assert store.fingerprint("a") is None

        index(store, "a", [[1.0, 0.0]], fingerprint="f1")

        assert store.fingerprint("a") == "f1"

    def test_replacing_a_source_drops_its_old_passages_but_leaves_other_sources(
        self, tmp_path: Path
    ) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]], fingerprint="f1")
        index(store, "b", [[1.0, 1.0]], fingerprint="f1")

        index(store, "a", [[1.0, 0.2]], fingerprint="f2", texts=["the new version"])

        assert store.counts() == {"a": 1, "b": 1}
        assert store.fingerprint("a") == "f2"
        assert [hit.text for hit in store.search([1.0, 0.2], k=1, source_ids=["a"])] == [
            "the new version"
        ]

    def test_re_indexing_the_same_version_does_not_duplicate_passages(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)

        index(store, "a", [[1.0, 0.0], [0.0, 1.0]])
        index(store, "a", [[1.0, 0.0], [0.0, 1.0]])

        assert store.counts() == {"a": 2}

    def test_handles_more_passages_than_one_batch(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)

        index(store, "big", [[1.0, float(n)] for n in range(450)])

        assert store.counts() == {"big": 450}


class TestSize:
    def test_counts_every_passage_of_every_source(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        assert store.size() == 0

        index(store, "a", [[1.0, 0.0], [0.0, 1.0]])
        index(store, "b", [[1.0, 1.0]])

        assert store.size() == 3


class TestSources:
    def test_lists_each_source_once_with_its_passage_count_and_metadata(
        self, tmp_path: Path
    ) -> None:
        store = open_store(tmp_path)
        index(store, "b", [[1.0, 0.0]])
        index(store, "a", [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])

        listed = store.sources()

        assert [(item.id, item.passages) for item in listed] == [("a", 3), ("b", 1)]
        assert listed[0].metadata["title"] == "Title of a"
        assert listed[0].metadata["fingerprint"] == "f1"

    def test_a_source_is_marked_as_scanned_if_any_of_its_passages_is(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        store.replace_source(
            "scan",
            ids=["x:0", "x:1"],
            documents=["clean", "blurry"],
            vectors=[[1.0, 0.0], [0.0, 1.0]],
            metadatas=[{"ocr": False}, {"ocr": True}],
            fingerprint="f1",
        )
        index(store, "web", [[1.0, 0.0]])

        by_id = {item.id: item.metadata["ocr"] for item in store.sources()}

        assert by_id == {"scan": True, "web": False}

    def test_an_empty_index_lists_nothing(self, tmp_path: Path) -> None:
        assert open_store(tmp_path).sources() == []


class TestRefreshSource:
    def test_updates_fields_in_place_and_keeps_everything_else(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0], [0.0, 1.0]])

        store.refresh_source("a", {"verified_at": "2026-11-01T00:00:00"})

        for hit in store.search([1.0, 0.0], k=2):
            assert hit.metadata["verified_at"] == "2026-11-01T00:00:00"
            assert hit.metadata["title"] == "Title of a"
            assert hit.metadata["fingerprint"] == "f1"


WRITER = """
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings

from app.services.retrieval.store import VectorStore

directory, mode = Path(sys.argv[1]), sys.argv[2]
vectors = [[1.0, 0.1 * n] for n in range(40)]
if mode == "store":  # what `python -m app.cli ingest` does
    store = VectorStore(directory, embedding_model="model-a")
    store.replace_source(
        "a",
        ids=[f"a:v2:{n}" for n in range(40)],
        documents=[f"a version two passage {n}" for n in range(40)],
        vectors=vectors,
        metadatas=[{"title": "Title of a"} for _ in range(40)],
        fingerprint="f2",
    )
else:  # a writer that knows nothing about the stamp file: only Chroma itself is used
    client = chromadb.PersistentClient(path=str(directory), settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection("official_chunks", embedding_function=None)
    collection.delete(where={"source_id": "a"})
    collection.upsert(
        ids=[f"a:v2:{n}" for n in range(40)],
        documents=[f"a version two passage {n}" for n in range(40)],
        embeddings=vectors,
        metadatas=[{"title": "Title of a", "source_id": "a", "fingerprint": "f2"} for _ in range(40)],
    )
"""


def write_from_another_process(tmp_path: Path, mode: str) -> None:
    """Rewrite source "a" from a separate Python process, as the ingest command would."""
    subprocess.run(
        [sys.executable, "-c", WRITER, str(tmp_path / "chroma"), mode],
        check=True,
        capture_output=True,
        timeout=120,
        cwd=BACKEND_DIR,  # so that the writer can import the app
    )


class TestAnotherProcessWrites:
    """The API keeps the index open while `python -m app.cli ingest` replaces a source."""

    @pytest.mark.parametrize("mode", ["store", "chroma-only"])
    def test_a_reader_keeps_working_and_sees_the_new_version(
        self, tmp_path: Path, mode: str
    ) -> None:
        reader = open_store(tmp_path)
        index(reader, "a", [[1.0, 0.1 * n] for n in range(50)], fingerprint="f1")
        assert reader.search([1.0, 0.0], k=3)[0].text.startswith(
            "a passage"
        )  # warm: now it is open

        write_from_another_process(tmp_path, mode)

        hits = reader.search([1.0, 0.0], k=3)

        assert {hit.text.split(" passage")[0] for hit in hits} == {"a version two"}
        assert reader.counts() == {"a": 40}
        assert reader.size() == 40
        assert reader.fingerprint("a") == "f2"

    def test_the_listing_of_sources_follows_too(self, tmp_path: Path) -> None:
        reader = open_store(tmp_path)
        index(reader, "a", [[1.0, 0.1 * n] for n in range(50)], fingerprint="f1")
        assert reader.sources()[0].passages == 50

        write_from_another_process(tmp_path, "store")

        assert [(item.id, item.passages) for item in reader.sources()] == [("a", 40)]


class TestChangeStamp:
    def test_every_way_of_changing_the_index_leaves_a_stamp_for_other_readers(
        self, tmp_path: Path
    ) -> None:
        store = open_store(tmp_path)
        stamp = tmp_path / "chroma" / "last-update"
        stamps = []

        index(store, "a", [[1.0, 0.0]])
        stamps.append(stamp.read_text())
        store.refresh_source("a", {"verified_at": "2026-11-01T00:00:00"})
        stamps.append(stamp.read_text())
        open_store(tmp_path, rebuild=True)
        stamps.append(stamp.read_text())

        assert len(set(stamps)) == 3  # each change is a new stamp

    def test_reading_leaves_the_stamp_alone(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0]])
        stamp = tmp_path / "chroma" / "last-update"
        before = stamp.read_text()

        store.search([1.0, 0.0])
        store.counts()
        store.sources()
        store.size()
        store.fingerprint("a")

        assert stamp.read_text() == before

    def test_a_missing_stamp_is_not_an_error(self, tmp_path: Path) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0]])
        (tmp_path / "chroma" / "last-update").unlink()

        assert store.search([1.0, 0.0])[0].metadata["source_id"] == "a"

    def test_searches_from_many_threads_survive_the_index_changing_underneath(
        self, tmp_path: Path
    ) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.1 * n] for n in range(30)])
        failures: list[BaseException] = []

        def search_repeatedly() -> None:
            try:
                for _ in range(25):
                    assert store.search([1.0, 0.0], k=3)
            except BaseException as error:  # reported below, from the main thread
                failures.append(error)

        threads = [threading.Thread(target=search_repeatedly) for _ in range(6)]
        for thread in threads:
            thread.start()
        for _ in range(4):  # another process "changes" the index while the searches run
            (tmp_path / "chroma" / "last-update").write_text(str(time.time_ns()))
            time.sleep(0.05)
        for thread in threads:
            thread.join()

        assert failures == []


class TestModelGuard:
    def test_an_index_built_with_another_model_is_refused(self, tmp_path: Path) -> None:
        index(open_store(tmp_path, "model-a"), "a", [[1.0, 0.0]])

        with pytest.raises(IndexingError) as error:
            open_store(tmp_path, "model-b")

        assert error.value.code == "embedding_model_changed"
        assert "--rebuild" in error.value.message

    def test_rebuilding_discards_the_old_index_and_adopts_the_new_model(
        self, tmp_path: Path
    ) -> None:
        index(open_store(tmp_path, "model-a"), "a", [[1.0, 0.0]])

        rebuilt = open_store(tmp_path, "model-b", rebuild=True)

        assert rebuilt.counts() == {}
        index(rebuilt, "a", [[0.0, 1.0, 0.0]])  # a different dimension is fine in a fresh index
        assert open_store(tmp_path, "model-b").counts() == {"a": 1}

    def test_the_same_model_reopens_with_its_data(self, tmp_path: Path) -> None:
        index(open_store(tmp_path), "a", [[1.0, 0.0]])

        assert open_store(tmp_path).counts() == {"a": 1}

    @pytest.mark.filterwarnings("ignore:legacy embedding function config:DeprecationWarning")
    def test_a_query_by_text_fails_instead_of_silently_using_another_model(
        self, tmp_path: Path
    ) -> None:
        store = open_store(tmp_path)
        index(store, "a", [[1.0, 0.0]])

        with pytest.raises(ValueError, match="embedding function"):
            store._collection.query(query_texts=["income"], n_results=1)
