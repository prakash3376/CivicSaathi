"""Running the benchmark: did retrieval find the evidence, and did the answer rest on it?

Retrieval is measured without the language model, so it is free, fast and repeatable:

* **Source recall@k**: a passage of a document that holds the answer is among the first k.
* **Evidence hit@k**: a passage among the first k contains one of the verified quotes that
  support the answer. This is the stricter test: the right document with the wrong page fails it.
* **MRR**: how high the first right document ranks.

Answers are measured only on request (``--answer``), because each costs a model call: an
answerable question must be answered with a citation from a right document, and a question the
documents cannot answer must not be answered.
"""

import json
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.assistant import Answer, Passage
from app.domain.errors import AssistantError
from app.services.assistant.intent import classify
from app.services.evaluation.cases import Case
from app.services.grounding.language import writes_in
from app.services.grounding.text import Squashed, find_quote, squash

Searcher = Callable[[Case], Sequence[Passage]]
Asker = Callable[[Case], Answer]


@dataclass
class RetrievalResult:
    id: str
    group: str
    language: str
    sector: str | None
    origin: str
    answerable: bool
    expected_intent: str | None
    got_intent: str | None
    source_rank: int | None  # 1-based rank of the first passage from a right document
    evidence_rank: int | None  # 1-based rank of the first passage holding a verified quote
    passages: int
    milliseconds: float
    top: list[str] = field(default_factory=list)


@dataclass
class AnswerResult:
    id: str
    group: str
    language: str
    sector: str | None
    answerable: bool
    got_answerable: bool | None
    cited_right_source: bool
    correct: bool
    language_ok: bool
    citations: int
    milliseconds: float
    error: str | None = None
    cited_sources: list[str] = field(default_factory=list)  # which documents the answer rests on


def evaluate_retrieval(cases: Sequence[Case], search: Searcher) -> list[RetrievalResult]:
    results: list[RetrievalResult] = []
    for case in cases:
        started = time.perf_counter()
        passages = list(search(case))
        elapsed = (time.perf_counter() - started) * 1000
        squashed: dict[str, Squashed] = {}

        def holds(
            passage: Passage, case: Case = case, cache: dict[str, Squashed] = squashed
        ) -> bool:
            if passage.chunk_id not in cache:
                cache[passage.chunk_id] = squash(passage.text)
            return any(
                cite.source_id == passage.source_id
                and find_quote(cite.quote, cache[passage.chunk_id])
                for cite in case.quotes
            )

        source_rank = next(
            (n for n, p in enumerate(passages, 1) if p.source_id in case.sources), None
        )
        evidence_rank = next((n for n, p in enumerate(passages, 1) if holds(p)), None)
        intent = classify(case.question, has_history=bool(case.history)).intent
        results.append(
            RetrievalResult(
                id=case.id,
                group=case.group,
                language=case.language,
                sector=case.sector,
                origin=case.origin,
                answerable=case.answerable,
                expected_intent=case.intent,
                got_intent=intent,
                source_rank=source_rank,
                evidence_rank=evidence_rank,
                passages=len(passages),
                milliseconds=elapsed,
                top=[p.source_id for p in passages[:5]],
            )
        )
    return results


def evaluate_answers(
    cases: Sequence[Case], ask: Asker, *, pause: float = 0.0
) -> list[AnswerResult]:
    results: list[AnswerResult] = []
    for case in cases:
        started = time.perf_counter()
        error: str | None = None
        answer: Answer | None = None
        try:
            answer = ask(case)
        except AssistantError as failure:
            error = failure.code
        elapsed = (time.perf_counter() - started) * 1000
        cited = answer is not None and any(c.source_id in case.sources for c in answer.citations)
        got = answer.answerable if answer is not None else None
        correct = (
            got is False if not case.answerable else (got is True and cited)
        ) and error is None
        results.append(
            AnswerResult(
                id=case.id,
                group=case.group,
                language=case.language,
                sector=case.sector,
                answerable=case.answerable,
                got_answerable=got,
                cited_right_source=cited,
                correct=correct,
                language_ok=answer is not None and writes_in(answer.text, case.language),
                citations=len(answer.citations) if answer else 0,
                milliseconds=elapsed,
                error=error,
                cited_sources=list(dict.fromkeys(c.source_id for c in answer.citations))
                if answer
                else [],
            )
        )
        if pause:
            time.sleep(pause)
    return results


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 3) if total else None


def summarise_retrieval(results: Sequence[RetrievalResult], k: int) -> dict[str, Any]:
    """Recall, evidence hit and MRR, overall and by group, sector, language and origin."""

    def block(items: Sequence[RetrievalResult]) -> dict[str, Any]:
        scored = [r for r in items if r.answerable]
        ranks = [r.source_rank for r in scored]
        return {
            "cases": len(scored),
            f"source_recall@{k}": _rate(sum(1 for r in ranks if r and r <= k), len(scored)),
            f"evidence_hit@{k}": _rate(
                sum(1 for r in scored if r.evidence_rank and r.evidence_rank <= k), len(scored)
            ),
            "mrr": round(sum(1 / r for r in ranks if r) / len(scored), 3) if scored else None,
        }

    def by(key: str) -> dict[str, Any]:
        groups: dict[str, list[RetrievalResult]] = defaultdict(list)
        for result in results:
            groups[str(getattr(result, key))].append(result)
        return {name: block(items) for name, items in sorted(groups.items())}

    labelled = [r for r in results if r.expected_intent]
    times = sorted(r.milliseconds for r in results)
    return {
        "k": k,
        "overall": block(results),
        "by_group": by("group"),
        "by_sector": by("sector"),
        "by_language": by("language"),
        "by_origin": by("origin"),
        "intent_accuracy": _rate(
            sum(1 for r in labelled if r.expected_intent == r.got_intent), len(labelled)
        ),
        "intent_cases": len(labelled),
        "latency_ms": {
            "mean": round(statistics.fmean(times), 1) if times else None,
            "p95": round(times[int(0.95 * (len(times) - 1))], 1) if times else None,
        },
    }


def summarise_answers(results: Sequence[AnswerResult]) -> dict[str, Any]:
    answerable = [r for r in results if r.answerable]
    refused = [r for r in results if not r.answerable]
    times = sorted(r.milliseconds for r in results)
    return {
        "cases": len(results),
        "errors": sum(1 for r in results if r.error),
        "answerable_correct": _rate(sum(r.correct for r in answerable), len(answerable)),
        "answerable_cases": len(answerable),
        "abstained_correctly": _rate(sum(r.correct for r in refused), len(refused)),
        "abstain_cases": len(refused),
        "language_ok": _rate(
            sum(r.language_ok for r in results if r.error is None),
            sum(1 for r in results if r.error is None),
        ),
        "latency_ms": {
            "mean": round(statistics.fmean(times), 1) if times else None,
            "p95": round(times[int(0.95 * (len(times) - 1))], 1) if times else None,
        },
    }


def write_report(
    directory: Path,
    *,
    strategy: str,
    retrieval: dict[str, Any],
    answers: dict[str, Any] | None,
    details: dict[str, Any],
) -> Path:
    """Keep the run on disk: a dated file, and ``latest-<strategy>.json`` for the dashboard."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC)
    body = {
        "strategy": strategy,
        "at": stamp.isoformat(timespec="seconds"),
        "retrieval": retrieval,
        "answers": answers,
        "details": details,
    }
    text = json.dumps(body, indent=2, ensure_ascii=False)
    path = directory / f"{stamp:%Y%m%d-%H%M%S}-{strategy}.json"
    path.write_text(text, encoding="utf-8")
    (directory / f"latest-{strategy}.json").write_text(text, encoding="utf-8")
    return path


def details_of(
    retrieval: Sequence[RetrievalResult], answers: Sequence[AnswerResult]
) -> dict[str, Any]:
    return {
        "retrieval": [asdict(r) for r in retrieval],
        "answers": [asdict(r) for r in answers],
    }
