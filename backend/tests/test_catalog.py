from datetime import date, timedelta
from pathlib import Path

from app.services.assistant.catalog import SourceCatalog
from app.services.retrieval.store import VectorStore
from tests.factories import NOW, FakeEmbedder, index_texts, make_spec

TEXTS = ["The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum."]


def catalog_with(tmp_path: Path, *specs: object) -> tuple[SourceCatalog, VectorStore, FakeEmbedder]:
    embedder = FakeEmbedder()
    store = VectorStore(tmp_path / "chroma", embedding_model=embedder.name)
    return SourceCatalog(store, list(specs), clock=lambda: NOW), store, embedder  # type: ignore[arg-type]


def test_an_indexed_source_is_described_from_what_the_index_holds(tmp_path: Path) -> None:
    catalog, store, embedder = catalog_with(tmp_path, make_spec(id="guide", format="pdf"))
    index_texts(
        store, embedder, "guide", [*TEXTS, "Apply online."],
        level="state", state="West Bengal", doc_type="guidelines",
    )  # fmt: skip

    [summary] = catalog.sources()

    assert summary.id == "guide"
    assert summary.title == "Title of guide"
    assert (summary.scheme, summary.authority) == ("Demo Scholarship", "Department of Demos")
    assert (summary.level, summary.state, summary.doc_type) == (
        "state",
        "West Bengal",
        "guidelines",
    )
    assert summary.format == "pdf"
    assert summary.url == "https://example.gov.in/guide.pdf"
    assert summary.passages == 2
    assert summary.document_date == date(2026, 6, 1)
    assert summary.date_source == "pdf-metadata"
    assert summary.verification == "verified"
    assert summary.age_days == (NOW.date() - date(2026, 6, 1)).days
    assert not summary.stale
    assert not summary.verification_due
    assert not summary.ocr


def test_a_central_scheme_has_no_state(tmp_path: Path) -> None:
    catalog, store, embedder = catalog_with(tmp_path)
    index_texts(store, embedder, "guide", TEXTS, level="central", state="")

    assert catalog.sources()[0].state is None


def test_an_old_document_and_an_unchecked_source_are_marked(tmp_path: Path) -> None:
    catalog, store, embedder = catalog_with(tmp_path)
    old_check = (NOW - timedelta(days=45)).isoformat(timespec="seconds")
    index_texts(store, embedder, "guide", TEXTS, document_date="2024-01-01", verified_at=old_check)

    [summary] = catalog.sources()

    assert summary.stale
    assert summary.verification_due


def test_a_document_without_a_date_has_no_age_and_is_not_called_stale(tmp_path: Path) -> None:
    catalog, store, embedder = catalog_with(tmp_path)
    index_texts(store, embedder, "guide", TEXTS, document_date="", date_source="")

    [summary] = catalog.sources()

    assert summary.document_date is None
    assert summary.date_source is None
    assert summary.age_days is None
    assert not summary.stale


def test_a_scanned_source_is_marked(tmp_path: Path) -> None:
    catalog, store, embedder = catalog_with(tmp_path)
    index_texts(store, embedder, "guide", TEXTS, ocr=True)

    assert catalog.sources()[0].ocr


def test_the_format_is_guessed_for_a_source_missing_from_the_registry(tmp_path: Path) -> None:
    catalog, store, embedder = catalog_with(tmp_path)  # nothing registered
    index_texts(store, embedder, "paper", TEXTS)  # its url ends in .pdf
    index_texts(store, embedder, "page", TEXTS, url="https://example.gov.in/scheme")

    assert {item.id: item.format for item in catalog.sources()} == {"page": "html", "paper": "pdf"}


def test_registered_sources_that_are_not_indexed_are_not_listed(tmp_path: Path) -> None:
    catalog, store, embedder = catalog_with(tmp_path, make_spec(id="guide"), make_spec(id="later"))
    index_texts(store, embedder, "guide", TEXTS)

    assert [item.id for item in catalog.sources()] == ["guide"]


def test_an_empty_index_lists_nothing(tmp_path: Path) -> None:
    catalog, _, _ = catalog_with(tmp_path, make_spec())

    assert catalog.sources() == []
