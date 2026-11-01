"""Collect, verify, read, chunk, embed and index official sources (SPEC section 6, steps 1 and 2).

The pipeline is idempotent. A source whose download, registry entry, chunking rules and embedding
model are all unchanged is not re-processed (SPEC rule R9), though it is still re-verified so that
"last verified" stays honest (rule R4). A source that fails verification never touches the index:
what was indexed before stays exactly as it was.
"""

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from app.domain.documents import (
    Chunk,
    FetchedDocument,
    IngestRecord,
    ParsedDocument,
    PipelineInfo,
    VerificationCheck,
    VerificationReport,
)
from app.domain.sources import SourceSpec
from app.services.ingestion.storage import ArtifactStore
from app.services.ingestion.verification import build_report, failed, verify_content
from app.services.ingestion.verifier import SourceVerifier
from app.services.retrieval.embedder import Embedder
from app.services.retrieval.store import MetadataValue, VectorStore
from app.services.segmentation.chunker import CHUNKER_VERSION, ChunkerConfig, chunk_document

logger = logging.getLogger(__name__)

# Bump when extraction or the stored metadata layout changes, so existing indexes are rebuilt.
INGESTION_VERSION = "1"

Outcome = Literal["indexed", "unchanged", "rejected"]


@dataclass(frozen=True)
class IngestResult:
    source_id: str
    outcome: Outcome
    report: VerificationReport
    chunks: int
    seconds: float


class IngestionPipeline:
    def __init__(
        self,
        *,
        verifier: SourceVerifier,
        embedder: Embedder,
        store: VectorStore,
        artifacts: ArtifactStore,
        chunker: ChunkerConfig | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._verifier = verifier
        self._embedder = embedder
        self._store = store
        self._artifacts = artifacts
        self._chunker = chunker or ChunkerConfig()
        self._clock = clock or (lambda: datetime.now(UTC))

    def ingest(self, spec: SourceSpec, *, force: bool = False) -> IngestResult:
        """Bring the index up to date for one source."""
        started = time.perf_counter()
        now = self._clock()
        checks, fetched = self._verifier.download(spec, now)
        if fetched is None or failed(checks):
            return self._result(spec, "rejected", build_report(spec, checks, now), 0, started)

        fingerprint = self._fingerprint(spec, fetched)
        record = self._artifacts.load_record(spec.id)
        # "Unchanged" needs the audit record and the index to agree with the document. The index
        # alone is not enough: a run that died while replacing a changed document leaves old and new
        # passages together, and the new fingerprint may be on the first one read. The record is
        # saved last, so while it still holds the old fingerprint the source is not finished.
        if (
            not force
            and record
            and record.pipeline.fingerprint == fingerprint
            and self._store.fingerprint(spec.id) == fingerprint
        ):
            return self._refresh(spec, record, checks, now, started)

        more, document = self._verifier.read(spec, fetched, now)
        checks += more
        if document is None or failed(checks):
            return self._result(spec, "rejected", build_report(spec, checks, now), 0, started)

        chunks = chunk_document(
            document, title=spec.title, doc_hash=fetched.sha256, config=self._chunker
        )
        if not chunks:
            checks.append(
                VerificationCheck(
                    name="chunks", status="fail", detail="No passages could be built from the text."
                )
            )
            return self._result(spec, "rejected", build_report(spec, checks, now), 0, started)

        report = build_report(spec, checks, now)
        logger.info("%s: embedding %d passages", spec.id, len(chunks))
        vectors = self._embedder.embed_documents([chunk.embed_text for chunk in chunks])
        self._store.replace_source(
            spec.id,
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            vectors=vectors,
            metadatas=[
                _metadata(spec, report, fetched, document, chunk, self._embedder.name)
                for chunk in chunks
            ],
            fingerprint=fingerprint,
        )
        self._artifacts.save_raw(spec.id, fetched, spec.format)
        self._artifacts.save_record(
            IngestRecord(
                source=spec,
                fetched=fetched,
                verification=report,
                document=document,
                chunks=chunks,
                pipeline=PipelineInfo(
                    ingestion_version=INGESTION_VERSION,
                    chunker_version=CHUNKER_VERSION,
                    embedding_model=self._embedder.name,
                    fingerprint=fingerprint,
                    indexed_at=now,
                ),
            )
        )
        return self._result(spec, "indexed", report, len(chunks), started)

    def _refresh(
        self,
        spec: SourceSpec,
        record: IngestRecord,
        checks: list[VerificationCheck],
        now: datetime,
        started: float,
    ) -> IngestResult:
        """Nothing changed: re-run the checks on the stored text and refresh 'last verified'."""
        report = build_report(spec, [*checks, *verify_content(spec, record.document, now)], now)
        if report.status == "rejected":
            return self._result(spec, "rejected", report, 0, started)
        self._store.refresh_source(
            spec.id,
            {
                "verification": report.status,
                "verified_at": report.verified_at.isoformat(timespec="seconds"),
            },
        )
        self._artifacts.save_record(record.model_copy(update={"verification": report}))
        return self._result(spec, "unchanged", report, len(record.chunks), started)

    def _fingerprint(self, spec: SourceSpec, fetched: FetchedDocument) -> str:
        """Identifies everything that decides the indexed content, so any change re-indexes."""
        parts = [
            fetched.sha256,
            INGESTION_VERSION,
            CHUNKER_VERSION,
            repr(self._chunker),
            self._embedder.name,
            spec.model_dump_json(),
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def _result(
        spec: SourceSpec, outcome: Outcome, report: VerificationReport, chunks: int, started: float
    ) -> IngestResult:
        return IngestResult(spec.id, outcome, report, chunks, time.perf_counter() - started)


def _metadata(
    spec: SourceSpec,
    report: VerificationReport,
    fetched: FetchedDocument,
    document: ParsedDocument,
    chunk: Chunk,
    embedding_model: str,
) -> dict[str, MetadataValue]:
    """Flat metadata stored beside each passage: where it came from and how far to trust it."""
    return {
        "doc_hash": fetched.sha256,
        "title": spec.title,
        "scheme": spec.scheme,
        "authority": spec.authority,
        "level": spec.level,
        "state": spec.state or "",
        "doc_type": spec.doc_type,
        "url": spec.url,
        "domain": urlsplit(fetched.final_url).hostname or "",
        "verification": report.status,
        "verified_at": report.verified_at.isoformat(timespec="seconds"),
        "fetched_at": fetched.fetched_at.isoformat(timespec="seconds"),
        "document_date": document.document_date.isoformat() if document.document_date else "",
        "date_source": document.date_source or "",
        "page_start": chunk.page_start or 0,
        "page_end": chunk.page_end or 0,
        "section": chunk.section,
        "clause": chunk.clause,
        "chunk_index": chunk.index,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "script": chunk.script,
        "ocr": chunk.ocr,
        "embedding_model": embedding_model,
    }
