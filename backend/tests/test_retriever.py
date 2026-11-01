from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.services.retrieval.retriever import RELEVANCE_FLOORS, Retriever, passage_from_hit
from app.services.retrieval.store import SearchHit, VectorStore
from tests.factories import FakeEmbedder, index_texts

INCOME = "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum."
MARKS = "Students must secure at least 60% marks in the last qualifying examination."
CAT = "The cat sat on the mat and watched the birds in the garden."


def store_with(tmp_path: Path, embedder: FakeEmbedder, **by_source: list[str]) -> VectorStore:
    store = VectorStore(tmp_path / "chroma", embedding_model=embedder.name)
    for source_id, texts in by_source.items():
        index_texts(store, embedder, source_id, texts)
    return store


class TestRetrieve:
    def test_returns_the_closest_passages_first_numbered_from_s1(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        store = store_with(tmp_path, embedder, guide=[CAT, INCOME, MARKS])

        passages = Retriever(store, embedder, floor=0.1).retrieve(
            "What is the family income ceiling?"
        )

        assert [p.ref for p in passages][:2] == ["S1", "S2"]
        assert passages[0].text == INCOME
        assert passages[0].score >= passages[1].score

    def test_a_passage_carries_what_is_needed_to_cite_it(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        store = store_with(tmp_path, embedder, guide=[INCOME])

        [passage] = Retriever(store, embedder, floor=0.1).retrieve("family income ceiling")

        assert passage.source_id == "guide"
        assert passage.title == "Title of guide"
        assert passage.scheme == "Demo Scholarship"
        assert passage.url == "https://example.gov.in/guide.pdf"
        assert (passage.page_start, passage.page_end) == (1, 1)
        assert passage.section == "ELIGIBILITY"
        assert passage.document_date == date(2026, 6, 1)
        assert passage.date_source == "pdf-metadata"
        assert passage.verified_at == datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
        assert passage.verification == "verified"
        assert passage.ocr is False

    def test_passages_unrelated_to_the_question_are_left_out_by_the_floor(
        self, tmp_path: Path
    ) -> None:
        embedder = FakeEmbedder()
        store = store_with(tmp_path, embedder, guide=[INCOME, CAT])

        passages = Retriever(store, embedder, floor=0.3).retrieve("family income ceiling")

        assert [p.text for p in passages] == [INCOME]

    def test_nothing_relevant_gives_no_passages(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        store = store_with(tmp_path, embedder, guide=[CAT])

        assert Retriever(store, embedder, floor=0.3).retrieve("family income ceiling") == []

    def test_at_most_k_passages_are_returned(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        store = store_with(tmp_path, embedder, guide=[INCOME, MARKS, CAT])

        assert len(Retriever(store, embedder, k=2, floor=0.0).retrieve("income marks")) == 2

    def test_can_be_limited_to_some_sources(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        store = store_with(tmp_path, embedder, one=[INCOME], two=[INCOME], three=[INCOME])

        passages = Retriever(store, embedder, floor=0.1).retrieve(
            "family income", source_ids=["one", "three"]
        )

        assert {p.source_id for p in passages} == {"one", "three"}

    def test_an_empty_index_gives_no_passages(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()
        store = store_with(tmp_path, embedder)

        assert Retriever(store, embedder).retrieve("anything") == []

    def test_it_knows_whether_anything_has_been_indexed(self, tmp_path: Path) -> None:
        embedder = FakeEmbedder()

        assert Retriever(store_with(tmp_path, embedder), embedder).is_empty()
        assert not Retriever(store_with(tmp_path, embedder, guide=[INCOME]), embedder).is_empty()


class TestRelevanceFloor:
    class Fixed:
        """Always asks about the same direction, so scores are exactly what the vectors give."""

        name = "intfloat/multilingual-e5-small"

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise AssertionError("not used")

        def embed_query(self, _text: str) -> list[float]:
            return [1.0, 0.0]

    def test_the_measured_model_has_its_floor_and_others_have_none(self) -> None:
        assert RELEVANCE_FLOORS == {"intfloat/multilingual-e5-small": 0.77}

    def test_a_passage_below_the_floor_of_the_model_is_dropped(self, tmp_path: Path) -> None:
        embedder = self.Fixed()
        store = VectorStore(tmp_path / "chroma", embedding_model=embedder.name)
        store.replace_source(
            "guide",
            ids=["close", "far"],
            documents=["close passage", "far passage"],
            vectors=[[0.8, 0.6], [0.75, 0.6614378]],  # cosine similarity 0.80 and 0.75
            metadatas=[{}, {}],
            fingerprint="f1",
        )

        passages = Retriever(store, embedder).retrieve("question")

        assert [p.text for p in passages] == ["close passage"]


class TestPassageFromHit:
    def hit(self, **metadata: Any) -> SearchHit:
        return SearchHit(id="c1", text="text", score=0.9, metadata=metadata)

    def test_a_web_page_has_no_page_numbers(self) -> None:
        passage = passage_from_hit(self.hit(page_start=0, page_end=0), "S1")

        assert (passage.page_start, passage.page_end) == (None, None)

    def test_missing_or_unreadable_dates_become_none(self) -> None:
        passage = passage_from_hit(
            self.hit(document_date="", verified_at="not a time", date_source=""), "S1"
        )

        assert passage.document_date is None
        assert passage.verified_at is None
        assert passage.date_source is None

    @pytest.mark.parametrize(
        ("script", "language"),
        [("Latin", "en"), ("Bengali", "bn"), ("Devanagari", "hi"), ("mixed", None), ("", None)],
    )
    def test_the_language_of_a_passage_is_judged_from_its_script(
        self, script: str, language: str | None
    ) -> None:
        assert passage_from_hit(self.hit(script=script), "S1").language == language

    def test_a_passage_with_no_metadata_at_all_is_still_usable(self) -> None:
        passage = passage_from_hit(self.hit(), "S4")

        assert (passage.ref, passage.text, passage.score) == ("S4", "text", 0.9)
        assert passage.title == passage.url == ""
