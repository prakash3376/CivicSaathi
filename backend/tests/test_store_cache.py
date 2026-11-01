"""The copy of the passages' metadata that makes listing the sources cheap: it must be reused when
nothing changed and thrown away the moment the index does, whoever changed it."""

from pathlib import Path

from app.services.retrieval.store import VectorStore
from tests.factories import FakeEmbedder, index_texts


def store(tmp_path: Path, embedder: FakeEmbedder, **options: bool) -> VectorStore:
    opened = VectorStore(tmp_path / "chroma", embedding_model=embedder.name, **options)
    index_texts(opened, embedder, "guide", ["The income ceiling is Rs 2,50,000.", "Apply online."])
    return opened


class TestTheScanCache:
    def test_listing_twice_reads_the_passages_once(self, tmp_path: Path) -> None:
        opened = store(tmp_path, FakeEmbedder())

        first = opened.sources()
        second = opened.sources()
        counts = opened.counts()

        assert first == second
        assert counts == {"guide": 2}
        assert opened.scan_stats() == {"hits": 2, "misses": 1}

    def test_a_change_made_through_the_store_is_seen_at_once(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        opened = store(tmp_path, embedder)
        assert opened.counts() == {"guide": 2}

        index_texts(opened, embedder, "other", ["Another document."])

        assert opened.counts() == {"guide": 2, "other": 1}

    def test_a_change_made_by_another_process_is_seen_at_once(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        reader = store(tmp_path, embedder)
        assert reader.counts() == {"guide": 2}
        writer = VectorStore(tmp_path / "chroma", embedding_model=embedder.name)  # the ingest

        index_texts(writer, embedder, "other", ["Written while the reader had its copy."])

        assert reader.counts() == {"guide": 2, "other": 1}

    def test_a_replaced_source_shows_its_new_count(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        opened = store(tmp_path, embedder)
        assert opened.counts()["guide"] == 2

        # A changed document has a new fingerprint, which is what lets the old passages go.
        opened.replace_source(
            "guide",
            ids=["guide:0"],
            documents=["Only one passage now."],
            vectors=embedder.embed_documents(["Only one passage now."]),
            metadatas=[{"title": "t", "page_start": 1, "page_end": 1}],
            fingerprint="f2",
        )

        assert opened.counts()["guide"] == 1

    def test_the_copy_can_be_switched_off(self, tmp_path: Path) -> None:
        opened = store(tmp_path, FakeEmbedder(), cache_scans=False)

        opened.sources()
        opened.sources()

        assert opened.scan_stats() == {"hits": 0, "misses": 2}

    def test_what_the_caller_gets_cannot_corrupt_the_copy(self, tmp_path: Path) -> None:
        opened = store(tmp_path, FakeEmbedder())

        opened.counts()["guide"] = 999
        opened.sources().clear()

        assert opened.counts() == {"guide": 2}
        assert [s.id for s in opened.sources()] == ["guide"]
