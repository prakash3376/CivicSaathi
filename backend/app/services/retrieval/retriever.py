"""Finding the passages of the official documents that may answer a question.

Retrieval is dense only: the question is embedded with the same model as the passages and the
closest passages by meaning are returned. Two alternatives were measured on the gold questions
in tests/data/retrieval_gold.json and rejected. Adding keyword (BM25) matching made results
worse, because the questions are in Hindi and Bengali while the documents are in English, so
shared words are rare and common words dominate. Having the language model rewrite the question
first gave a small gain for a model call on every question.

The relevance floor is deliberately low. It exists to avoid sending the model passages that have
nothing to do with the question, not to decide whether the question is answerable: a question
about a passport scores as high as one about a scholarship because both are about "documents and
eligibility", and e5 scores are compressed into a narrow band. Whether the passages really answer
the question is for the model to say and for the grounding check to confirm.
"""

from collections.abc import Sequence

from app.domain.assistant import Passage
from app.services.retrieval.embedder import Embedder
from app.services.retrieval.metadata import parse_date, parse_datetime, parse_page
from app.services.retrieval.store import SearchHit, VectorStore
from app.services.segmentation.scripts import LANGUAGE_HINTS

DEFAULT_TOP_K = 10

# Below this cosine similarity a passage is not worth showing to the model. Measured on the gold
# questions: the lowest score of a passage that answered one was 0.783 and the highest score of
# an off-topic question was 0.844, so the floor only removes what is plainly unrelated. A model
# that has not been measured gets no floor.
RELEVANCE_FLOORS = {"intfloat/multilingual-e5-small": 0.77}


class Retriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        *,
        k: int = DEFAULT_TOP_K,
        floor: float | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._k = k
        self._floor = RELEVANCE_FLOORS.get(embedder.name, 0.0) if floor is None else floor

    def is_empty(self) -> bool:
        """True if nothing has been indexed yet (the ingest command has not been run)."""
        return self._store.size() == 0

    def retrieve(self, question: str, *, source_ids: Sequence[str] | None = None) -> list[Passage]:
        """The passages closest in meaning to ``question``, best first, numbered S1, S2, ..."""
        hits = self._store.search(
            self._embedder.embed_query(question), k=self._k, source_ids=source_ids
        )
        relevant = [hit for hit in hits if hit.score >= self._floor]
        return [passage_from_hit(hit, f"S{number}") for number, hit in enumerate(relevant, start=1)]


def passage_from_hit(hit: SearchHit, ref: str) -> Passage:
    """A search hit as a passage, with the facts needed to cite it and judge how fresh it is."""
    metadata = hit.metadata
    return Passage(
        ref=ref,
        chunk_id=hit.id,
        source_id=str(metadata.get("source_id", "")),
        title=str(metadata.get("title", "")),
        scheme=str(metadata.get("scheme", "")),
        authority=str(metadata.get("authority", "")),
        url=str(metadata.get("url", "")),
        text=hit.text,
        page_start=parse_page(metadata.get("page_start")),
        page_end=parse_page(metadata.get("page_end")),
        section=str(metadata.get("section", "")),
        clause=str(metadata.get("clause", "")),
        document_date=parse_date(metadata.get("document_date")),
        date_source=str(metadata.get("date_source") or "") or None,
        verified_at=parse_datetime(metadata.get("verified_at")),
        verification=str(metadata.get("verification", "")),
        ocr=bool(metadata.get("ocr", False)),
        language=LANGUAGE_HINTS.get(str(metadata.get("script", ""))),
        score=hit.score,
    )
