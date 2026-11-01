from datetime import date

import pypdfium2 as pdfium
import pytest

from app.domain.errors import ExtractionError
from app.services.ingestion.extraction import pdf as pdf_module
from app.services.ingestion.extraction.pdf import extract_pdf, strip_running_lines
from tests.pdf_factory import make_pdf

LONG_LINE = "The scholarship is paid every month to students who qualify under the scheme."


class TestExtractPdf:
    def test_reads_text_page_by_page(self) -> None:
        pdf = make_pdf([["Page one starts here.", LONG_LINE], ["Page two has its own text."]])

        doc = extract_pdf(pdf, source_id="demo")

        assert doc.source_id == "demo"
        assert doc.format == "pdf"
        assert [page.number for page in doc.pages] == [1, 2]
        assert {block.page for block in doc.blocks} == {1, 2}
        assert "Page two has its own text." in doc.text
        assert doc.warnings == []

    def test_decodes_bullets_and_dashes(self) -> None:
        pdf = make_pdf([["• First condition applies.", "• Second condition applies."]])

        doc = extract_pdf(pdf, source_id="demo")

        assert [block.text for block in doc.blocks] == [
            "• First condition applies.",
            "• Second condition applies.",
        ]
        assert all(block.kind == "list_item" for block in doc.blocks)

    def test_reads_the_document_date_from_the_pdf_metadata(self) -> None:
        pdf = make_pdf([[LONG_LINE]], creation_date="D:20260301093000")

        doc = extract_pdf(pdf, source_id="demo")

        assert doc.document_date == date(2026, 3, 1)
        assert doc.date_source == "pdf-metadata"

    def test_has_no_date_when_the_metadata_has_none(self) -> None:
        doc = extract_pdf(make_pdf([[LONG_LINE]]), source_id="demo")

        assert doc.document_date is None
        assert doc.date_source is None

    def test_flags_a_scan_whose_text_is_an_invisible_ocr_layer(self) -> None:
        pdf = make_pdf([["Notice about the last date of application."]], invisible_text=True)

        doc = extract_pdf(pdf, source_id="demo")

        assert doc.pages[0].ocr_layer is True
        assert doc.has_ocr_layer
        assert all(block.ocr for block in doc.blocks)
        assert any("OCR" in warning for warning in doc.warnings)

    def test_does_not_flag_ordinary_text(self) -> None:
        doc = extract_pdf(make_pdf([[LONG_LINE]]), source_id="demo")

        assert not doc.has_ocr_layer
        assert not any(block.ocr for block in doc.blocks)

    def test_removes_a_header_repeated_on_every_page_but_keeps_the_first(self) -> None:
        pages = [
            ["SCHEME GUIDELINES", f"Unique body text for page {number}, long enough to matter."]
            for number in range(1, 5)
        ]

        doc = extract_pdf(make_pdf(pages), source_id="demo")

        assert sum("SCHEME GUIDELINES" in block.text for block in doc.blocks) == 1
        assert doc.blocks[0].page == 1

    def test_garbage_is_not_a_pdf(self) -> None:
        with pytest.raises(ExtractionError) as error:
            extract_pdf(b"this is plainly not a pdf file", source_id="demo")

        assert error.value.code == "corrupted_document"

    def test_a_password_protected_pdf_is_reported_as_such(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(_content: bytes) -> None:
            raise pdfium.PdfiumError("Failed to load document (PDFium: Incorrect password error).")

        monkeypatch.setattr(pdf_module.pdfium, "PdfDocument", refuse)

        with pytest.raises(ExtractionError) as error:
            extract_pdf(b"%PDF-1.4", source_id="demo")

        assert error.value.code == "password_protected"

    def test_refuses_documents_with_too_many_pages(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pdf_module, "MAX_PAGES", 2)

        with pytest.raises(ExtractionError) as error:
            extract_pdf(make_pdf([[LONG_LINE]] * 3), source_id="demo")

        assert error.value.code == "too_many_pages"


class TestStripRunningLines:
    def test_leaves_short_documents_alone(self) -> None:
        pages = ["HEADER\nbody one", "HEADER\nbody two"]

        assert strip_running_lines(pages) == pages

    def test_drops_repeated_edge_lines_after_the_first_page(self) -> None:
        pages = [f"REPORT TITLE\nbody of page {n}\nfooter text" for n in range(1, 5)]

        cleaned = strip_running_lines(pages)

        assert cleaned[0].splitlines() == ["REPORT TITLE", "body of page 1"]
        assert all("REPORT TITLE" not in page for page in cleaned[1:])
        assert all("footer text" not in page for page in cleaned[1:])

    def test_drops_page_numbers_at_the_edge_of_a_page(self) -> None:
        pages = [f"body of page {n}\n{n}" for n in range(1, 4)]

        cleaned = strip_running_lines(pages)

        assert cleaned == ["body of page 1", "body of page 2", "body of page 3"]

    def test_keeps_a_repeated_line_that_is_not_at_the_edge(self) -> None:
        pages = [f"intro {n}\nNOTE: see annexure\nclosing {n}" for n in range(1, 5)]

        cleaned = strip_running_lines(pages)

        assert all("NOTE: see annexure" in page for page in cleaned)
