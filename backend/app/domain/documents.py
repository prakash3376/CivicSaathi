from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.sources import SourceFormat, SourceSpec

BlockKind = Literal["heading", "paragraph", "list_item", "table"]
CheckStatus = Literal["pass", "warn", "fail"]
VerificationStatus = Literal["verified", "verified_with_warnings", "rejected"]


class TlsInfo(BaseModel):
    """What the TLS handshake with the server established."""

    version: str
    cipher: str
    issuer: str | None = None
    subject_org: str | None = None
    not_after: datetime | None = None
    hostnames: list[str] = Field(default_factory=list)
    legacy_renegotiation: bool = Field(
        default=False,
        description="Connected with legacy server connect enabled (RFC 5746 missing).",
    )


class FetchedDocument(BaseModel):
    """What came back from an official URL, plus how it got here."""

    url: str
    final_url: str
    redirect_chain: list[str] = Field(default_factory=list)
    status_code: int
    content_type: str | None
    last_modified: str | None
    robots: Literal["allowed", "absent"] = "absent"
    tls: TlsInfo | None = None
    size_bytes: int
    sha256: str
    fetched_at: datetime
    elapsed_ms: int
    # The bytes are kept as a file under raw/, not inside the JSON record, so a record loaded
    # from disk has none.
    content: bytes = Field(default=b"", exclude=True, repr=False)


class Block(BaseModel):
    """A paragraph, list item, heading or table of a document, in reading order."""

    kind: BlockKind
    text: str
    page: int | None = Field(default=None, description="1-based page of a PDF; None for web pages.")
    level: int | None = Field(default=None, description="Depth of a heading (1 is the top).")
    ocr: bool = Field(default=False, description="Text comes from a scan's OCR layer.")


class PageInfo(BaseModel):
    """Per-page extraction diagnostics for PDFs."""

    number: int
    chars: int
    ocr_layer: bool = False


class ParsedDocument(BaseModel):
    """A document reduced to structured text, ready to be chunked."""

    source_id: str
    format: SourceFormat
    blocks: list[Block]
    pages: list[PageInfo] = Field(default_factory=list)
    document_date: date | None = None
    date_source: str | None = None
    warnings: list[str] = Field(default_factory=list)
    extractor: str

    @property
    def text(self) -> str:
        """The whole document as one string; chunk offsets refer to this exact text."""
        return "\n\n".join(block.text for block in self.blocks)

    @property
    def has_ocr_layer(self) -> bool:
        return any(page.ocr_layer for page in self.pages)


class Chunk(BaseModel):
    """A passage small enough to embed and cite, with where it came from."""

    id: str
    index: int
    text: str
    embed_text: str = Field(description="What is embedded: the passage with its title and section.")
    page_start: int | None = None
    page_end: int | None = None
    section: str = ""
    clause: str = ""
    char_start: int = Field(description="Offset into ParsedDocument.text.")
    char_end: int
    script: str
    ocr: bool = False


class VerificationCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class VerificationReport(BaseModel):
    """The outcome of checking a source: why we trust it, or why we do not."""

    source_id: str
    url: str
    status: VerificationStatus
    checks: list[VerificationCheck]
    verified_at: datetime

    @property
    def failures(self) -> list[VerificationCheck]:
        return [check for check in self.checks if check.status == "fail"]

    @property
    def warnings(self) -> list[VerificationCheck]:
        return [check for check in self.checks if check.status == "warn"]


class PipelineInfo(BaseModel):
    """Everything besides the document that decides what the index holds for a source."""

    ingestion_version: str
    chunker_version: str
    embedding_model: str
    fingerprint: str
    indexed_at: datetime


class IngestRecord(BaseModel):
    """The audit trail of one ingested source, stored as JSON beside the vector index."""

    source: SourceSpec
    fetched: FetchedDocument
    verification: VerificationReport
    document: ParsedDocument
    chunks: list[Chunk]
    pipeline: PipelineInfo
