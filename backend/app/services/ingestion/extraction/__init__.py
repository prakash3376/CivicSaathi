"""Turns a downloaded file into structured text, whatever its format."""

from app.domain.documents import FetchedDocument, ParsedDocument
from app.domain.sources import SourceSpec
from app.services.ingestion.extraction.html import extract_html
from app.services.ingestion.extraction.pdf import extract_pdf

__all__ = ["extract_document", "extract_html", "extract_pdf"]


def extract_document(spec: SourceSpec, fetched: FetchedDocument) -> ParsedDocument:
    """Extract ``fetched`` according to the format the registry declares for ``spec``.

    The document's date comes from, in order of trust: the registry (a person read it off the
    document), the file's own metadata, then the server's ``Last-Modified`` header.
    """
    if spec.format == "pdf":
        parsed = extract_pdf(fetched.content, source_id=spec.id)
    else:
        parsed = extract_html(
            fetched.content,
            source_id=spec.id,
            selector=spec.content_selector,
            last_modified=fetched.last_modified,
        )

    if spec.published_on:
        return parsed.model_copy(
            update={"document_date": spec.published_on, "date_source": "registry"}
        )
    return parsed
