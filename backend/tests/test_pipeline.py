from datetime import timedelta
from pathlib import Path

import httpx2
import pytest

from app.domain.documents import VerificationReport
from app.domain.errors import IndexingError
from app.services.ingestion.fetcher import Fetcher
from app.services.ingestion.pipeline import IngestionPipeline, IngestResult
from app.services.ingestion.storage import ArtifactStore
from app.services.ingestion.verifier import SourceVerifier
from app.services.retrieval.store import VectorStore
from tests.factories import NOW, FakeEmbedder, make_spec
from tests.pdf_factory import make_pdf

HOST = "https://scholarships.example.gov.in"
MAX_BYTES = 25 * 1024 * 1024


def guidelines_pdf(income: str = "2,50,000") -> bytes:
    return make_pdf(
        [
            [
                "SCHOLARSHIP GUIDELINES",
                f"The upper ceiling for family income has been fixed at Rs.{income}/- per annum.",
                "Applicants must be residents of the State and must apply online before the last date.",
                "The scholarship is paid every month to students who are enrolled in a recognised",
                "institution and who secure the minimum marks in the last qualifying examination.",
            ],
            [
                "RENEWAL OF SCHOLARSHIP",
                "For renewal, the application must be submitted online within one month of admission",
                "to the next higher class, with the marksheet of the previous examination attached.",
                "Renewal is sanctioned only for students who obtain the minimum marks in the examination",
                "and who continue to meet every other condition of the scheme that applies to new",
                "applicants, as stated in the guidelines above.",
            ],
        ],
        creation_date="D:20260301093000",
    )


ABOUT_PAGE = b"""<html><body><nav>Menu</nav><div class="about_main">
<h3>Eligibility</h3>
<p>The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum. Students must be
residents of the State and must have passed the last qualifying examination with at least 60% marks.
The scholarship is paid every month to students who are enrolled in a recognised institution.</p>
</div></body></html>"""


class Network:
    """A fake website whose pages can change between pipeline runs."""

    def __init__(self) -> None:
        self.pages: dict[str, tuple[int, bytes, str]] = {
            "/guidelines.pdf": (200, guidelines_pdf(), "application/pdf"),
            "/about.html": (200, ABOUT_PAGE, "text/html"),
        }
        self.requested: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requested.append(str(request.url))
        status, body, content_type = self.pages.get(request.url.path, (404, b"", "text/plain"))
        return httpx2.Response(status, content=body, headers={"content-type": content_type})


class Setup:
    def __init__(self, tmp_path: Path) -> None:
        self.network = Network()
        self.embedder = FakeEmbedder()
        self.artifacts = ArtifactStore(tmp_path)
        self.store = VectorStore(self.artifacts.chroma_dir, embedding_model=self.embedder.name)
        self.now = NOW
        fetcher = Fetcher(transport=httpx2.MockTransport(self.network), max_bytes=MAX_BYTES)
        self.pipeline = IngestionPipeline(
            verifier=SourceVerifier(fetcher=fetcher, max_bytes=MAX_BYTES),
            embedder=self.embedder,
            store=self.store,
            artifacts=self.artifacts,
            clock=lambda: self.now,
        )

    def ingest(self, spec=None, **kwargs: bool) -> IngestResult:
        return self.pipeline.ingest(spec or make_spec(), **kwargs)

    def failing_checks(self, report: VerificationReport) -> set[str]:
        return {check.name for check in report.failures}


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


class TestFirstIngest:
    def test_indexes_the_source_with_provenance_metadata(self, setup: Setup) -> None:
        result = setup.ingest()

        assert result.outcome == "indexed"
        assert result.report.status == "verified_with_warnings"  # no TLS details on a fake network
        assert result.chunks >= 2
        assert setup.store.counts() == {"demo-guidelines": result.chunks}

        [hit] = setup.store.search(setup.embedder.embed_query("family income ceiling"), k=1)
        assert "2,50,000" in hit.text
        assert hit.metadata["title"] == "Demo Scholarship: Guidelines"
        assert hit.metadata["authority"] == "Department of Demos, Government of India"
        assert hit.metadata["level"] == "central"
        assert hit.metadata["doc_type"] == "guidelines"
        assert hit.metadata["url"] == f"{HOST}/guidelines.pdf"
        assert hit.metadata["domain"] == "scholarships.example.gov.in"
        assert hit.metadata["document_date"] == "2026-03-01"
        assert hit.metadata["date_source"] == "pdf-metadata"
        assert hit.metadata["page_start"] == 1
        assert hit.metadata["verification"] == "verified_with_warnings"
        assert hit.metadata["verified_at"] == "2026-10-31T12:00:00+00:00"
        assert hit.metadata["embedding_model"] == "fake-embedder"
        assert hit.metadata["script"] == "Latin"
        assert hit.metadata["ocr"] is False

    def test_passages_know_their_page_and_section(self, setup: Setup) -> None:
        setup.ingest()

        [hit] = setup.store.search(
            setup.embedder.embed_query("renewal application marksheet next higher class"), k=1
        )

        assert hit.metadata["page_start"] == 2
        assert hit.metadata["section"] == "RENEWAL OF SCHOLARSHIP"

    def test_keeps_the_original_download_and_an_audit_record(
        self, setup: Setup, tmp_path: Path
    ) -> None:
        result = setup.ingest()

        [raw] = list((tmp_path / "raw" / "demo-guidelines").glob("*.pdf"))
        assert raw.read_bytes() == guidelines_pdf()
        record = setup.artifacts.load_record("demo-guidelines")
        assert record is not None
        assert record.source.id == "demo-guidelines"
        assert len(record.chunks) == result.chunks
        assert record.fetched.sha256 in raw.name or raw.name.startswith(record.fetched.sha256[:16])
        assert record.pipeline.embedding_model == "fake-embedder"
        assert "Rs.2,50,000" in record.document.text

    def test_indexes_a_web_page_source(self, setup: Setup) -> None:
        spec = make_spec(
            id="demo-page",
            format="html",
            doc_type="scheme_page",
            url=f"{HOST}/about.html",
            content_selector="div.about_main",
            expected_phrases=("family income",),
        )

        result = setup.ingest(spec)

        assert result.outcome == "indexed"
        [hit] = setup.store.search(setup.embedder.embed_query("family income"), k=1)
        assert hit.metadata["page_start"] == 0  # web pages have no pages
        assert hit.metadata["section"] == "Eligibility"


class TestIdempotency:
    def test_a_second_run_does_no_work_but_refreshes_last_verified(self, setup: Setup) -> None:
        first = setup.ingest()
        embedded = setup.embedder.documents_embedded
        setup.now = NOW + timedelta(days=1)

        second = setup.ingest()

        assert second.outcome == "unchanged"
        assert second.chunks == first.chunks
        assert setup.embedder.documents_embedded == embedded  # nothing was re-embedded
        [hit] = setup.store.search(setup.embedder.embed_query("family income ceiling"), k=1)
        assert hit.metadata["verified_at"] == "2026-11-01T12:00:00+00:00"
        assert second.report.verified_at == setup.now

    def test_force_re_processes_an_unchanged_source(self, setup: Setup) -> None:
        setup.ingest()
        embedded = setup.embedder.documents_embedded

        result = setup.ingest(force=True)

        assert result.outcome == "indexed"
        assert setup.embedder.documents_embedded == 2 * embedded
        assert setup.store.counts() == {"demo-guidelines": result.chunks}

    def test_a_changed_document_replaces_the_old_passages(self, setup: Setup) -> None:
        first = setup.ingest()
        setup.network.pages["/guidelines.pdf"] = (
            200,
            guidelines_pdf(income="3,00,000"),
            "application/pdf",
        )

        result = setup.ingest()

        assert result.outcome == "indexed"
        assert setup.store.counts() == {"demo-guidelines": result.chunks}
        assert result.chunks == first.chunks
        [hit] = setup.store.search(setup.embedder.embed_query("family income ceiling"), k=1)
        assert "3,00,000" in hit.text
        assert "2,50,000" not in hit.text

    def test_a_change_to_the_registry_entry_re_indexes(self, setup: Setup) -> None:
        setup.ingest()

        result = setup.ingest(make_spec(title="A better title for the same document"))

        assert result.outcome == "indexed"
        [hit] = setup.store.search(setup.embedder.embed_query("family income"), k=1)
        assert hit.metadata["title"] == "A better title for the same document"

    def test_a_lost_audit_record_triggers_a_full_re_ingest(
        self, setup: Setup, tmp_path: Path
    ) -> None:
        setup.ingest()
        (tmp_path / "parsed" / "demo-guidelines.json").unlink()

        assert setup.ingest().outcome == "indexed"


class TestRejection:
    def test_a_non_official_url_is_never_requested(self, setup: Setup) -> None:
        spec = make_spec(url="https://blog.example.com/scholarship.pdf")

        result = setup.ingest(spec)

        assert result.outcome == "rejected"
        assert setup.failing_checks(result.report) == {"official_domain"}
        assert setup.network.requested == []
        assert setup.store.counts() == {}

    def test_a_server_error_is_rejected(self, setup: Setup) -> None:
        setup.network.pages["/guidelines.pdf"] = (500, b"oops", "text/plain")

        result = setup.ingest()

        assert result.outcome == "rejected"
        assert "http_status" in setup.failing_checks(result.report)
        assert setup.store.counts() == {}

    def test_an_unreadable_pdf_is_rejected_without_crashing(self, setup: Setup) -> None:
        setup.network.pages["/guidelines.pdf"] = (
            200,
            b"%PDF-1.4 this is not really a pdf",
            "application/pdf",
        )

        result = setup.ingest()

        assert result.outcome == "rejected"
        assert "extraction" in setup.failing_checks(result.report)

    def test_a_different_document_at_the_same_address_is_rejected(self, setup: Setup) -> None:
        setup.network.pages["/guidelines.pdf"] = (
            200,
            make_pdf([["An entirely different notice about something else. " * 8]]),
            "application/pdf",
        )

        result = setup.ingest()

        assert result.outcome == "rejected"
        assert "identity" in setup.failing_checks(result.report)

    def test_a_failed_re_verification_leaves_the_index_exactly_as_it_was(
        self, setup: Setup
    ) -> None:
        first = setup.ingest()
        setup.network.pages["/guidelines.pdf"] = (
            200,
            make_pdf([["An entirely different notice about something else. " * 8]]),
            "application/pdf",
        )

        result = setup.ingest()

        assert result.outcome == "rejected"
        assert setup.store.counts() == {"demo-guidelines": first.chunks}
        [hit] = setup.store.search(setup.embedder.embed_query("family income ceiling"), k=1)
        assert "2,50,000" in hit.text

    def test_a_scan_is_indexed_but_its_passages_are_flagged(self, setup: Setup) -> None:
        setup.network.pages["/guidelines.pdf"] = (
            200,
            make_pdf(
                [
                    [
                        "SCHOLARSHIP GUIDELINES",
                        "The last date for submitting applications is 31.10.2026 for all students.",
                        "Institutions must verify applications before the date given in this notice.",
                        "Students are advised to apply well in time so that verification is complete.",
                    ]
                ],
                invisible_text=True,
                creation_date="D:20260301093000",
            ),
            "application/pdf",
        )

        result = setup.ingest(make_spec(expected_facts=()))

        assert result.outcome == "indexed"
        assert any("OCR" in check.detail for check in result.report.warnings)
        [hit] = setup.store.search(setup.embedder.embed_query("last date applications"), k=1)
        assert hit.metadata["ocr"] is True


class TestEmbeddingModelGuard:
    def test_ingesting_with_a_different_model_than_the_index_is_refused(
        self, setup: Setup, tmp_path: Path
    ) -> None:
        setup.ingest()

        with pytest.raises(IndexingError) as error:
            VectorStore(setup.artifacts.chroma_dir, embedding_model="another-model")

        assert error.value.code == "embedding_model_changed"


def test_verify_checks_a_source_without_touching_the_index(setup: Setup) -> None:
    verifier = setup.pipeline._verifier

    result = verifier.verify(make_spec())

    assert result.report.status == "verified_with_warnings"
    assert result.fetched is not None
    assert result.document is not None
    assert setup.store.counts() == {}
    assert setup.embedder.documents_embedded == 0
