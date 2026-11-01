from pathlib import Path

import pytest

from app.domain.catalogue import Entry
from app.services.assistant import search as search_module
from app.services.assistant.search import (
    ALL_FEATURES,
    MAX_PER_SOURCE,
    KnowledgeSearch,
    _Keywords,
    is_english,
)
from app.services.retrieval.store import VectorStore
from tests.factories import FakeEmbedder, index_texts

KISAN = "PM-KISAN pays Rs 6000 a year to landholding farmer families. Documents: Aadhaar and bank account."
HEALTH = "Swasthya Sathi gives a health cover of Rs 5 lakh a year to every family of the State."
DOCS = "Documents you need to bring are a photo identity card and an address proof."
MUTATION = "Land mutation changes the name of the owner in the records after a sale."
CAT = "The cat sat on the mat and watched the birds in the garden."


def entry(ident: str, name: str, summary: str, sector: str, source: str) -> Entry:
    quote = {"source_id": source, "quote": "x" * 40}
    return Entry.model_validate(
        {
            "id": ident,
            "name": name,
            "sectors": [sector],
            "level": "central",
            "department": "Department of Demos",
            "source_ids": [source],
            "last_verified": "2026-10-31",
            "summary": {"en": summary, "bn": "x", "hi": "x"},
            "target": {"en": summary, "bn": "x", "hi": "x"},
            "benefits": [{"text": summary, "evidence": [quote]}],
            "apply": {"label": "Portal", "url": "https://demo.gov.in"},
        }
    )


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def store(tmp_path: Path, embedder: FakeEmbedder) -> VectorStore:
    store = VectorStore(tmp_path / "chroma", embedding_model=embedder.name)
    index_texts(store, embedder, "kisan", [KISAN])
    index_texts(store, embedder, "health", [HEALTH])
    index_texts(store, embedder, "forms", [DOCS])
    index_texts(store, embedder, "land", [MUTATION])
    index_texts(store, embedder, "other", [CAT])
    return store


def engine(store: VectorStore, embedder: FakeEmbedder, **kwargs: object) -> KnowledgeSearch:
    kwargs.setdefault("floor", -1.0)
    return KnowledgeSearch(store, embedder, **kwargs)  # type: ignore[arg-type]


def sources(result: search_module.SearchResult) -> list[str]:
    return [p.source_id for p in result.passages]


class TestTheBaseline:
    def test_dense_is_what_the_assistant_did_before(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        passages = engine(store, embedder).dense("health cover for a family")

        assert passages[0].source_id == "health"
        assert [p.ref for p in passages][:2] == ["S1", "S2"]


class TestFollowUps:
    QUESTION = "What documents do I need for it?"

    def test_without_history_the_question_finds_the_wrong_thing(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        result = engine(store, embedder).search(self.QUESTION, features=frozenset())

        assert sources(result)[0] == "forms"

    def test_the_earlier_question_is_searched_with_it(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        result = engine(store, embedder).search(
            self.QUESTION, history=["Tell me about PM-KISAN"], features=frozenset({"history"})
        )

        assert sources(result)[0] == "kisan"
        assert result.intent == "follow_up"
        assert result.needs_history is True

    def test_a_question_that_stands_alone_ignores_the_history(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        result = engine(store, embedder).search(
            "How much health cover does Swasthya Sathi give a family?",
            history=["Tell me about PM-KISAN"],
            features=frozenset({"history"}),
        )

        assert sources(result)[0] == "health"
        assert result.needs_history is False


class TestTheRouter:
    def test_a_question_is_matched_to_the_entry_it_is_about_and_its_documents_are_added(
        self, store: VectorStore, embedder: FakeEmbedder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(search_module, "ROUTER_MIN", 0.2)
        entries = [
            entry(
                "pm-kisan", "PM-KISAN", "farmer families landholding income", "agriculture", "kisan"
            ),
            entry("swasthya", "Swasthya Sathi", "health cover family State", "health", "health"),
        ]
        result = engine(store, embedder, entries=entries).search(
            "money for farmer families", features=frozenset({"router"})
        )

        assert result.routed == ["pm-kisan"]
        assert sources(result)[0] == "kisan"

    def test_nothing_is_routed_when_nothing_is_close(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        entries = [entry("pm-kisan", "PM-KISAN", "farmer families", "agriculture", "kisan")]

        result = engine(store, embedder, entries=entries).search(
            "completely unrelated words here", features=frozenset({"router"})
        )

        assert result.routed == []

    def test_a_chosen_scheme_is_a_hard_limit_and_the_router_stays_out_of_it(
        self, store: VectorStore, embedder: FakeEmbedder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(search_module, "ROUTER_MIN", 0.0)
        entries = [entry("pm-kisan", "PM-KISAN", "farmer families", "agriculture", "kisan")]

        result = engine(store, embedder, entries=entries).search(
            "farmer families", source_ids=["health"], features=ALL_FEATURES
        )

        assert set(sources(result)) <= {"health"}
        assert result.routed == []


class TestKeywords:
    def test_a_rare_word_ranks_its_passage_first_and_the_source_filter_applies(
        self, store: VectorStore
    ) -> None:
        index = _Keywords(store)

        top = index.top("mutation of the owner", 3, None)
        limited = index.top("mutation of the owner", 3, ["kisan"])

        assert top[0].metadata["source_id"] == "land"
        assert all(h.metadata["source_id"] == "kisan" for h in limited)

    def test_the_index_follows_the_store_when_it_changes(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        index = _Keywords(store)
        assert index.top("hydrogen", 3, None) == []

        index_texts(store, embedder, "green", ["The hydrogen mission aims at green hydrogen."])

        assert index.top("hydrogen", 3, None)[0].metadata["source_id"] == "green"

    def test_keywords_are_used_for_english_and_not_for_hindi_or_bengali(self) -> None:
        assert is_english("Who can apply for PMAY?")
        assert not is_english("पीएम आवास योजना")
        assert not is_english("পিম কিষাণ")

    def test_keywords_bring_in_a_passage_the_dense_pool_cut(
        self, store: VectorStore, embedder: FakeEmbedder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(search_module, "POOL", 1)

        plain = engine(store, embedder).search("mutation owner", features=frozenset())
        fused = engine(store, embedder).search("mutation owner", features=frozenset({"keywords"}))

        assert len(plain.passages) == 1
        assert "land" in sources(fused)


class TestTheSector:
    def test_the_sector_nudges_its_documents_up_but_removes_nothing(
        self, tmp_path: Path, embedder: FakeEmbedder
    ) -> None:
        store = VectorStore(tmp_path / "c", embedding_model=embedder.name)
        index_texts(store, embedder, "a", ["scheme benefits for families"])
        index_texts(store, embedder, "b", ["scheme benefits for families"])
        entries = [entry("e-b", "B scheme", "scheme b entry", "health", "b")]
        engine_ = engine(store, embedder, entries=entries)

        neutral = engine_.search("scheme benefits for families", features=frozenset({"sector"}))
        health = engine_.search(
            "scheme benefits for families", sector="health", features=frozenset({"sector"})
        )
        wrong = engine_.search(
            "scheme benefits for families", sector="housing", features=frozenset({"sector"})
        )

        assert sources(health)[0] == "b"
        assert set(sources(neutral)) == set(sources(health)) == set(sources(wrong)) == {"a", "b"}


class TestDiversityAndTheFloor:
    def test_one_long_document_cannot_crowd_out_the_others(
        self, tmp_path: Path, embedder: FakeEmbedder
    ) -> None:
        store = VectorStore(tmp_path / "c", embedding_model=embedder.name)
        index_texts(store, embedder, "manual", [f"farmer scheme rule number {n}" for n in range(8)])
        index_texts(store, embedder, "small", ["farmer scheme rule summary"])

        crowded = engine(store, embedder).search("farmer scheme rule", features=frozenset())
        spread = engine(store, embedder).search(
            "farmer scheme rule", features=frozenset({"diverse"})
        )

        assert sources(crowded).count("manual") > MAX_PER_SOURCE
        assert sources(spread).count("manual") == MAX_PER_SOURCE
        assert "small" in sources(spread)

    def test_what_is_not_close_to_the_question_is_left_out(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        result = engine(store, embedder, floor=0.3).search(
            "health cover for a family", features=frozenset()
        )

        assert "other" not in sources(result)
        assert sources(result)[0] == "health"


class TestWhatIsNotAboutGovernment:
    def test_nothing_is_searched_for_a_question_that_is_out_of_scope(
        self, store: VectorStore, embedder: FakeEmbedder
    ) -> None:
        result = engine(store, embedder).search("What is the weather in Kolkata today?")

        assert result.passages == []
        assert result.intent == "out_of_scope"
