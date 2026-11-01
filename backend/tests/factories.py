"""Small builders for the domain objects that many tests need."""

import hashlib
import math
import re
import zlib
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.domain.assistant import Draft, DraftClaim, Evidence
from app.domain.documents import Block, FetchedDocument, ParsedDocument, TlsInfo
from app.domain.errors import AssistantError
from app.domain.sources import SourceSpec
from app.services.assistant.catalog import SourceCatalog
from app.services.assistant.factory import AssistantRuntime
from app.services.assistant.service import AssistantService
from app.services.llm.base import T
from app.services.retrieval.retriever import Retriever
from app.services.retrieval.store import VectorStore

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def make_spec(**overrides: Any) -> SourceSpec:
    fields: dict[str, Any] = {
        "id": "demo-guidelines",
        "title": "Demo Scholarship: Guidelines",
        "scheme": "Demo Scholarship",
        "authority": "Department of Demos, Government of India",
        "level": "central",
        "doc_type": "guidelines",
        "format": "pdf",
        "url": "https://scholarships.example.gov.in/guidelines.pdf",
        "expected_phrases": ("scholarship guidelines",),
        "expected_facts": ("2,50,000",),
        "curated_on": date(2026, 10, 31),
    }
    fields.update(overrides)
    return SourceSpec(**fields)


def make_fetched(content: bytes = b"%PDF-1.4 body", **overrides: Any) -> FetchedDocument:
    fields: dict[str, Any] = {
        "url": "https://scholarships.example.gov.in/guidelines.pdf",
        "final_url": "https://scholarships.example.gov.in/guidelines.pdf",
        "status_code": 200,
        "content_type": "application/pdf",
        "last_modified": None,
        "robots": "absent",
        "tls": None,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "fetched_at": NOW,
        "elapsed_ms": 5,
        "content": content,
    }
    fields.update(overrides)
    return FetchedDocument(**fields)


def make_tls(**overrides: Any) -> TlsInfo:
    fields: dict[str, Any] = {
        "version": "TLSv1.3",
        "cipher": "TLS_AES_256_GCM_SHA384",
        "issuer": "Example CA",
        "not_after": datetime(2027, 6, 1, tzinfo=UTC),
        "hostnames": ["scholarships.example.gov.in"],
    }
    fields.update(overrides)
    return TlsInfo(**fields)


def make_document(text: str | Sequence[str] | None = None, **overrides: Any) -> ParsedDocument:
    """A parsed document with enough text to pass the verification checks."""
    if text is None:
        text = [
            "SCHOLARSHIP GUIDELINES",
            "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum. "
            "Applicants must be residents of the State and must apply online before the last date.",
            "The scholarship is paid every month to students who are enrolled in a recognised "
            "institution and who secure the minimum marks in the last qualifying examination.",
        ]
    paragraphs = [text] if isinstance(text, str) else list(text)
    fields: dict[str, Any] = {
        "source_id": "demo-guidelines",
        "format": "pdf",
        "blocks": [Block(kind="paragraph", text=paragraph, page=1) for paragraph in paragraphs],
        "document_date": date(2026, 6, 1),
        "date_source": "pdf-metadata",
        "extractor": "test",
    }
    fields.update(overrides)
    return ParsedDocument(**fields)


INCOME_QUOTE = "family income has been fixed at Rs.2,50,000/- per annum"


def make_claim(statement: str, quote: str = INCOME_QUOTE, source: str = "S1") -> DraftClaim:
    return DraftClaim(statement=statement, evidence=[Evidence(source=source, quote=quote)])


def make_draft(
    *claims: DraftClaim, answerable: bool = True, not_stated: list[str] | None = None
) -> Draft:
    return Draft(answerable=answerable, claims=list(claims), not_stated=not_stated or [])


class FakeModel:
    """Answers with scripted drafts (or raises scripted errors); the last reply repeats.

    A reply of the wrong shape for what was asked (a ``Draft`` where general guidance was wanted)
    is what a real model's malformed output is: ``llm_bad_output``.
    """

    name = "fake-model"

    def __init__(self, *replies: BaseModel | AssistantError) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []  # (system, user) of each call

    def generate(self, *, system: str, prompt: str, schema: type[T]) -> T:
        self.calls.append((system, prompt))
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, AssistantError):
            raise reply
        if not isinstance(reply, schema):
            raise AssistantError("wrong shape", code="llm_bad_output")
        return reply


def make_runtime(
    directory: Path,
    model: "FakeModel | None",
    *,
    texts: Sequence[str] = (
        "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum.",
    ),
    max_chars: int = 500,
    **metadata: Any,
) -> AssistantRuntime:
    """An assistant over a real vector store of ``texts`` (source "guide") and a scripted model."""
    embedder = FakeEmbedder()
    store = VectorStore(directory / "chroma", embedding_model=embedder.name)
    index_texts(store, embedder, "guide", texts, **metadata)
    service = AssistantService(
        retriever=Retriever(store, embedder, floor=-1.0),
        model=model,
        max_question_chars=max_chars,
        clock=lambda: NOW,
    )
    return AssistantRuntime(
        service, SourceCatalog(store, [make_spec(id="guide")], clock=lambda: NOW)
    )


def index_texts(
    store: VectorStore,
    embedder: "FakeEmbedder",
    source_id: str,
    texts: Sequence[str],
    **metadata: Any,
) -> None:
    """Put passages into a real vector store, with the metadata the pipeline would have stored.

    Keyword arguments override that metadata for every passage (``document_date="2024-01-01"``).
    """
    fields: dict[str, Any] = {
        "title": f"Title of {source_id}",
        "scheme": "Demo Scholarship",
        "authority": "Department of Demos",
        "url": f"https://example.gov.in/{source_id}.pdf",
        "section": "ELIGIBILITY",
        "clause": "",
        "document_date": "2026-06-01",
        "date_source": "pdf-metadata",
        "verified_at": "2026-10-30T09:00:00+00:00",
        "verification": "verified",
        "ocr": False,
        "script": "Latin",
    }
    fields.update(metadata)
    store.replace_source(
        source_id,
        ids=[f"{source_id}:{n}" for n in range(len(texts))],
        documents=list(texts),
        vectors=embedder.embed_documents(texts),
        metadatas=[{**fields, "page_start": n + 1, "page_end": n + 1} for n in range(len(texts))],
        fingerprint="f1",
    )


class FakeEmbedder:
    """Bag-of-words vectors: deterministic, offline, and similar for passages sharing words."""

    name = "fake-embedder"
    dimensions = 64

    def __init__(self) -> None:
        self.documents_embedded = 0

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in re.findall(r"\w+", text.lower()):
            vector[zlib.crc32(word.encode()) % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.documents_embedded += len(texts)
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
