"""Finding the evidence for a question across every sector.

One search serves all twelve sectors; what differs is only what it is told about the question.
Each stage is a feature that can be switched off, so that ``python -m app.cli eval`` can show what
each is worth on the benchmark, and a feature stays only if it earns its place.

``history``   a question that leans on an earlier one ("What documents do I need for it?") is
              searched together with the question before it.
``router``    the question is matched, by meaning, to the catalogue entries and budget records
              (the structured data), and the documents behind the best matches are searched too.
              This is how "farmer money" finds PM-KISAN without the words being in a passage.
``keywords``  for a question in English, a keyword (BM25) ranking is fused with the dense one, to
              catch scheme names, figures and legal terms. It is not used for Hindi and Bengali:
              those share almost no words with the English documents, and measured on the first
              gold set it only added noise.
``sector``    the sector the person is looking at nudges its documents up. It never removes any,
              so a question about another sector still finds its answer.
``diverse``   at most a few passages of one document, so that one long manual cannot crowd out
              the others.

Passages are merged by reciprocal rank fusion. A passage must still be close to the question in
meaning (the relevance floor), a little less strictly when the router or the keywords also chose
it: it is not enough to be a popular document.
"""

import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.assistant import Passage
from app.domain.catalogue import BudgetRecord, Entry
from app.services.assistant.intent import Intent, classify
from app.services.retrieval.embedder import Embedder
from app.services.retrieval.retriever import (
    DEFAULT_TOP_K,
    RELEVANCE_FLOORS,
    passage_from_hit,
)
from app.services.retrieval.store import SearchHit, VectorStore
from app.services.segmentation.scripts import detect_script

ALL_FEATURES = frozenset({"history", "router", "keywords", "sector", "diverse"})

# What stays on, because the benchmark says it earns its place (docs/BENCHMARKS.md): the router
# and the earlier questions raise source recall@5 from 0.88 to 0.97 and fix follow-ups; the sector
# nudge adds a little when it is right and costs a little, never the answer, when it is wrong.
# Keywords added nothing once the router was on and lowered evidence-hit; the per-source cap lowered
# it too. Both stay available, off, for a corpus where they might help.
DEFAULT_FEATURES = frozenset({"history", "router", "sector"})

POOL = 30  # candidates taken from the dense ranking
ROUTE_POOL = 8  # candidates taken from the documents of the routed entries
KEYWORD_POOL = 20
RRF_K = 60
SECTOR_BONUS = 1 / (RRF_K + 4)
ROUTER_BEST = 3  # entries followed
ROUTER_MARGIN = 0.03  # of cosine, below the best match
ROUTER_MIN = 0.78
LOOSER_FLOOR_BY = (
    0.03  # a passage the router or the keywords also chose may be this much less close
)
MAX_PER_SOURCE = 4
HISTORY_QUESTIONS = 2

_WORD = re.compile(r"[a-z0-9][a-z0-9\-']+")
_STOP = frozenset(
    [
        "the",
        "and",
        "for",
        "are",
        "was",
        "were",
        "with",
        "that",
        "this",
        "from",
        "have",
        "has",
        "had",
        "not",
        "but",
        "you",
        "your",
        "can",
        "will",
        "would",
        "shall",
        "may",
        "who",
        "what",
        "which",
        "when",
        "where",
        "how",
        "does",
        "did",
        "get",
        "gets",
        "give",
        "gives",
        "provide",
        "provided",
        "any",
        "all",
        "one",
        "two",
        "its",
        "their",
        "they",
        "them",
        "than",
        "then",
        "also",
        "into",
        "out",
        "per",
        "under",
        "over",
        "each",
        "such",
        "upon",
        "about",
        "there",
        "here",
        "been",
        "being",
        "only",
        "more",
        "most",
        "other",
        "some",
        "very",
    ]
)


@dataclass(frozen=True)
class SearchResult:
    passages: list[Passage]
    intent: Intent
    needs_history: bool
    routed: list[str] = field(default_factory=list)  # the entries or records the router chose


@dataclass
class _Candidate:
    hit: SearchHit
    dense: float | None = None
    score: float = 0.0
    chosen_elsewhere: bool = False  # by the router or the keywords, not only by meaning


def is_english(text: str) -> bool:
    return detect_script(text) in ("Latin", "unknown")


class _Keywords:
    """A BM25 ranking over every passage, rebuilt when the index changes."""

    def __init__(self, store: VectorStore) -> None:
        self._store = store
        self._version: str | None = None
        self._docs: list[tuple[str, dict[str, object]]] = []
        self._hits: dict[str, SearchHit] = {}
        self._postings: dict[str, list[tuple[int, int]]] = {}
        self._lengths: list[int] = []
        self._average = 1.0

    @staticmethod
    def tokens(text: str) -> list[str]:
        return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2]

    def _build(self) -> None:
        version = self._store.version()
        if version == self._version and self._docs:
            return
        self._docs, self._hits, self._lengths = [], {}, []
        self._postings = defaultdict(list)
        for ident, text, metadata in self._store.corpus():
            words = self.tokens(text)
            index = len(self._docs)
            self._docs.append((ident, metadata))
            self._hits[ident] = SearchHit(ident, text, 0.0, metadata)
            self._lengths.append(len(words))
            for word, count in Counter(words).items():
                self._postings[word].append((index, count))
        self._average = (sum(self._lengths) / len(self._lengths)) if self._lengths else 1.0
        self._version = version

    def top(self, text: str, k: int, source_ids: Sequence[str] | None) -> list[SearchHit]:
        self._build()
        scores: dict[int, float] = defaultdict(float)
        total = len(self._docs)
        allowed = set(source_ids) if source_ids else None
        for word in set(self.tokens(text)):
            postings = self._postings.get(word, [])
            if not postings:
                continue
            idf = math.log(1 + (total - len(postings) + 0.5) / (len(postings) + 0.5))
            for index, count in postings:
                length = self._lengths[index]
                scores[index] += (
                    idf * count * 2.5 / (count + 1.5 * (0.25 + 0.75 * length / self._average))
                )
        ranked = sorted(scores, key=scores.__getitem__, reverse=True)
        found: list[SearchHit] = []
        for index in ranked:
            ident, metadata = self._docs[index]
            if allowed is not None and metadata.get("source_id") not in allowed:
                continue
            found.append(self._hits[ident])
            if len(found) == k:
                break
        return found


class KnowledgeSearch:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        *,
        entries: Sequence[Entry] = (),
        records: Sequence[BudgetRecord] = (),
        k: int = DEFAULT_TOP_K,
        floor: float | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._k = k
        self._floor = RELEVANCE_FLOORS.get(embedder.name, 0.0) if floor is None else floor
        self._keywords = _Keywords(store)
        self._entries = list(entries)
        self._records = list(records)
        self._router_vectors: list[list[float]] | None = None
        self.sector_sources: dict[str, set[str]] = defaultdict(set)
        for entry in entries:
            for sector in entry.sectors:
                self.sector_sources[sector].update(entry.source_ids)
        for record in records:
            for tag in (record.sector, "budget"):
                if tag:
                    self.sector_sources[tag].update(record.source_ids)

    def is_empty(self) -> bool:
        return self._store.size() == 0

    # --- the baseline: what the assistant did before ------------------------------------------

    def dense(self, question: str, *, source_ids: Sequence[str] | None = None) -> list[Passage]:
        hits = self._store.search(
            self._embedder.embed_query(question), k=self._k, source_ids=source_ids
        )
        relevant = [hit for hit in hits if hit.score >= self._floor]
        return [passage_from_hit(hit, f"S{n}") for n, hit in enumerate(relevant, start=1)]

    # --- the search ---------------------------------------------------------------------------

    def search(
        self,
        question: str,
        *,
        history: Sequence[str] = (),
        sector: str | None = None,
        source_ids: Sequence[str] | None = None,
        features: frozenset[str] = DEFAULT_FEATURES,
    ) -> SearchResult:
        """Passages for ``question``, best first and numbered S1, S2, ...

        ``source_ids`` is a hard limit (the person chose one scheme's documents); ``sector`` is
        only a nudge.
        """
        decision = classify(question, has_history=bool(history))
        if decision.intent == "out_of_scope":
            return SearchResult([], decision.intent, False)
        text = question
        if "history" in features and history and decision.needs_history:
            text = " ".join([*history[-HISTORY_QUESTIONS:], question])
        vector = self._embedder.embed_query(text)

        candidates: dict[str, _Candidate] = {}
        rankings: list[tuple[float, list[str]]] = []

        dense = self._store.search(vector, k=POOL, source_ids=source_ids)
        for hit in dense:
            candidates[hit.id] = _Candidate(hit, dense=hit.score)
        rankings.append((1.0, [hit.id for hit in dense]))

        routed: list[str] = []
        if "router" in features and not source_ids:
            routed, boosted = self._route(vector)
            if boosted:
                near = self._store.search(vector, k=ROUTE_POOL, source_ids=sorted(boosted))
                for hit in near:
                    candidate = candidates.setdefault(hit.id, _Candidate(hit, dense=hit.score))
                    candidate.chosen_elsewhere = True
                rankings.append((1.0, [hit.id for hit in near]))

        if "keywords" in features and is_english(text):
            words = self._keywords.top(text, KEYWORD_POOL, source_ids)
            new = [hit.id for hit in words if hit.id not in candidates]
            known = self._store.similarities(vector, new)
            for hit in words:
                if hit.id not in candidates:
                    candidates[hit.id] = _Candidate(
                        SearchHit(hit.id, hit.text, known.get(hit.id, 0.0), hit.metadata),
                        dense=known.get(hit.id),
                    )
                candidates[hit.id].chosen_elsewhere = True
            rankings.append((1.0, [hit.id for hit in words]))

        for weight, order in rankings:
            for rank, ident in enumerate(order, start=1):
                candidates[ident].score += weight / (RRF_K + rank)
        if "sector" in features and sector:
            favoured = self.sector_sources.get(sector, set())
            for candidate in candidates.values():
                if candidate.hit.metadata.get("source_id") in favoured:
                    candidate.score += SECTOR_BONUS

        passages = self._choose(candidates, diverse="diverse" in features)
        return SearchResult(passages, decision.intent, decision.needs_history, routed)

    def _choose(self, candidates: Mapping[str, _Candidate], *, diverse: bool) -> list[Passage]:
        kept: list[_Candidate] = []
        per_source: Counter[str] = Counter()
        for candidate in sorted(candidates.values(), key=lambda c: c.score, reverse=True):
            floor = self._floor - (LOOSER_FLOOR_BY if candidate.chosen_elsewhere else 0.0)
            if candidate.dense is None or candidate.dense < floor:
                continue
            source = str(candidate.hit.metadata.get("source_id", ""))
            if diverse and per_source[source] >= MAX_PER_SOURCE:
                continue
            per_source[source] += 1
            kept.append(candidate)
            if len(kept) == self._k:
                break
        return [passage_from_hit(c.hit, f"S{n}") for n, c in enumerate(kept, start=1)]

    # --- the router ---------------------------------------------------------------------------

    def _route(self, vector: Sequence[float]) -> tuple[list[str], set[str]]:
        """The entries and budget records closest in meaning to the question, and their sources."""
        if self._router_vectors is None:
            texts = [
                f"{e.name}. {e.summary.en} {e.target.en} {e.benefits[0].text}"
                for e in self._entries
            ] + [f"{r.title}. {r.summary.en}" for r in self._records]
            self._router_vectors = self._embedder.embed_documents(texts) if texts else []
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        scored: list[tuple[float, str, Sequence[str]]] = []
        items: list[tuple[str, Sequence[str]]] = [
            *((e.id, e.source_ids) for e in self._entries),
            *((r.id, r.source_ids) for r in self._records),
        ]
        for (ident, sources), other in zip(items, self._router_vectors, strict=True):
            size = math.sqrt(sum(x * x for x in other)) or 1.0
            cosine = sum(a * b for a, b in zip(vector, other, strict=True)) / (norm * size)
            scored.append((cosine, ident, sources))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored or scored[0][0] < ROUTER_MIN:
            return [], set()
        best = scored[0][0]
        chosen = [s for s in scored[:ROUTER_BEST] if s[0] >= best - ROUTER_MARGIN]
        return [s[1] for s in chosen], {src for s in chosen for src in s[2]}
