"""Answering a question from the official documents, from the question to a checked answer.

In order: the question is tidied and checked (not empty, not too long); requests to reprogram the
assistant or to fake documents are refused without a model call; personal numbers are removed;
the closest passages are retrieved; the model drafts claims with exact quotes; every claim is
checked against the passages it quotes; if some fail, the model is told what was wrong and asked
once more (SPEC section 8); and whatever still fails is removed with a notice. The user sees only
claims that survived, each tied to a quote they can open.

Nothing here logs a question, a passage or a draft: only counts.
"""

import logging
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.assistant import (
    Answer,
    AnswerWarning,
    Citation,
    Draft,
    Guidance,
    Highlight,
    Language,
    LanguageChoice,
    Passage,
)
from app.domain.errors import AssistantError
from app.services.assistant.citations import build_citations, source_warnings, warning
from app.services.assistant.freshness import assess
from app.services.assistant.guidance import build_guidance_prompt, check_guidance
from app.services.assistant.messages import say
from app.services.assistant.question import resolve_language, tidy
from app.services.assistant.search import DEFAULT_FEATURES, KnowledgeSearch
from app.services.assistant.smalltalk import classify_smalltalk
from app.services.assistant.stats import AssistantStats
from app.services.assistant.trace import Trace, TraceLog
from app.services.grounding.language import writes_in
from app.services.grounding.numbers import links
from app.services.grounding.verify import Rejection, Verification, clean_statement, verify
from app.services.llm.base import LanguageModel
from app.services.llm.prompts import Prompt, build_prompt
from app.services.retrieval.retriever import Retriever
from app.services.safety.abuse import is_forgery_request
from app.services.safety.injection import is_injection_attempt, neutralize
from app.services.safety.pii import redact_personal_data

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # the first draft, and one more with what was wrong with it
# A wrong or expired key (llm_auth, llm_rejected) is the operator's to fix and nothing a visitor
# can do about: they are shown the matching passages like in any other outage, and the code is kept
# for the admin report. A blocked prompt is not here: the provider declined that question, and so
# do we.
FALLBACK_CODES = frozenset(
    {"llm_busy", "llm_unavailable", "llm_bad_output", "llm_auth", "llm_rejected"}
)
FALLBACK_PASSAGES = 3  # shown when the model could not answer
FALLBACK_EXCERPT_CHARS = 600
MAX_HISTORY = 3  # earlier questions that may help to find the evidence for this one
MAX_HISTORY_CHARS = 300
MAX_NOT_STATED = 5
MAX_NOT_STATED_CHARS = 200


@dataclass(frozen=True)
class _Attempt:
    draft: Draft
    verification: Verification
    prompt: Prompt


def _excerpt(passage: Passage, number: int, now: datetime) -> Citation:
    """The first words of a passage as a citation, cut at a sentence end where there is one."""
    text = passage.text
    if len(text) > FALLBACK_EXCERPT_CHARS:
        cut = text.rfind(". ", 0, FALLBACK_EXCERPT_CHARS)
        text = (
            text[: cut + 1] if cut > FALLBACK_EXCERPT_CHARS // 3 else text[:FALLBACK_EXCERPT_CHARS]
        )
    freshness = assess(passage.document_date, passage.verified_at, now)
    return Citation(
        number=number,
        source_id=passage.source_id,
        title=passage.title,
        authority=passage.authority,
        url=passage.url,
        page_start=passage.page_start,
        page_end=passage.page_end,
        section=passage.section,
        clause=passage.clause,
        passage=passage.text,
        quote=text,
        language=passage.language,
        highlights=[Highlight(start=0, end=len(text))],
        document_date=passage.document_date,
        date_source=passage.date_source,
        verified_at=passage.verified_at,
        verification=passage.verification,
        age_days=freshness.age_days,
        stale=freshness.stale,
        ocr=passage.ocr,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_nonce() -> str:
    return secrets.token_hex(8)


class AssistantService:
    def __init__(
        self,
        *,
        retriever: Retriever,
        model: LanguageModel | None,
        max_question_chars: int = 500,
        search: KnowledgeSearch | None = None,
        features: frozenset[str] = DEFAULT_FEATURES,
        guidance: bool = True,
        clock: Callable[[], datetime] = _utc_now,
        nonce: Callable[[], str] = _new_nonce,
    ) -> None:
        """``model`` is None when no API key is configured; asking then fails with a clear error.

        With ``guidance`` on (the default), a question the documents do not cover gets general,
        clearly labelled help instead of a dead end; off, it gets the fixed "documents do not say".
        """
        self._retriever = retriever
        self._model = model
        self._max_question_chars = max_question_chars
        self._search = search
        self._features = features
        self._guidance = guidance
        self.stats = AssistantStats()
        self.traces = TraceLog()
        self._clock = clock
        self._nonce = nonce

    def ask(
        self,
        question: str,
        *,
        language: LanguageChoice = "auto",
        source_ids: Sequence[str] | None = None,
        history: Sequence[str] = (),
        sector: str | None = None,
    ) -> Answer:
        """Answer, and count how it went (never what was asked)."""
        started = time.perf_counter()
        try:
            answer = self._ask(question, language, source_ids, history, sector)
        except AssistantError as error:
            self.stats.record("error", (time.perf_counter() - started) * 1000, failure=error.code)
            raise
        outcome = (
            "fallback"
            if answer.fallback
            else "guidance"
            if answer.guidance
            else "conversation"
            if answer.conversational
            else "answered"
            if answer.answerable
            else "not_answered"
        )
        self.stats.record(outcome, (time.perf_counter() - started) * 1000)
        return answer

    def _ask(
        self,
        question: str,
        language: LanguageChoice,
        source_ids: Sequence[str] | None,
        history: Sequence[str],
        sector: str | None,
    ) -> Answer:
        text = tidy(question)
        if not text:
            raise AssistantError("Please type a question.", code="question_empty")
        if len(text) > self._max_question_chars:
            raise AssistantError(
                f"Please keep the question under {self._max_question_chars} characters.",
                code="question_too_long",
            )
        if self._model is None:
            raise AssistantError(
                "The assistant is not set up on this server.", code="assistant_not_configured"
            )
        if self._retriever.is_empty():
            raise AssistantError(
                "The library of official documents is empty. An administrator must run the "
                "ingest command first.",
                code="index_empty",
            )

        chosen, fell_back = resolve_language(text, language)
        notices: list[AnswerWarning] = []
        if fell_back:
            notices.append(warning(chosen, "language_fallback"))

        if is_injection_attempt(text):
            logger.info("refused a question that tried to reprogram the assistant")
            return self._finish(
                Trace(language=chosen, intent="out_of_scope"),
                self._reply(chosen, "refused_injection", notices),
                outcome="refused",
            )
        if is_forgery_request(text):
            logger.info("refused a request to fake documents")
            return self._finish(
                Trace(language=chosen, intent="out_of_scope"),
                self._reply(chosen, "refused_forgery", notices),
                outcome="refused",
            )

        talk = classify_smalltalk(text)
        if talk is not None:  # a greeting or thanks: answered like a person would, no lookup
            return self._finish(
                Trace(language=chosen, intent="smalltalk"),
                self._reply(chosen, talk, notices).model_copy(update={"conversational": True}),
                outcome="conversation",
            )

        clean, kinds = redact_personal_data(text)
        if kinds:
            logger.info("removed personal numbers from a question (%s)", ", ".join(sorted(kinds)))
            notices.append(warning(chosen, "personal_data"))

        trace = Trace(language=chosen)
        started = time.perf_counter()
        passages = self._find(clean, history, sector, source_ids, trace)
        trace.retrieval_ms = round((time.perf_counter() - started) * 1000, 1)
        trace.passages = len(passages)
        trace.sources = list(dict.fromkeys(p.source_id for p in passages))[:8]
        if trace.intent == "out_of_scope":  # weather, cricket, jokes: say what we can help with
            return self._finish(
                trace, self._reply(chosen, "off_topic", notices), outcome="off_topic"
            )
        earlier = self._earlier(history)
        if not passages:
            logger.info("no passages were relevant to a question")
            started = time.perf_counter()
            answer = self._uncovered(self._model, clean, earlier, chosen, notices)
            trace.model_ms = round((time.perf_counter() - started) * 1000, 1)
            return self._finish(trace, answer)
        started = time.perf_counter()
        try:
            answer = self._answer(self._model, clean, earlier, passages, chosen, notices)
        except AssistantError as error:
            if error.code not in FALLBACK_CODES:
                trace.outcome = "error:" + error.code
                self.traces.add(trace)
                raise
            logger.warning("the model failed (%s); showing the matching passages", error.code)
            self.stats.note_failure(error.code)
            answer = self._fallback(passages, chosen, notices)
        trace.model_ms = round((time.perf_counter() - started) * 1000, 1)
        return self._finish(trace, answer)

    def model_health(self) -> dict[str, object] | None:
        """The model's circuit breaker, if it has one: state and recent failure streak."""
        health = getattr(self._model, "health", None)
        return health() if callable(health) else None

    def _finish(self, trace: Trace, answer: Answer, *, outcome: str | None = None) -> Answer:
        """Note how the answer was reached, and tell the user what the question was judged to be."""
        trace.outcome = outcome or (
            "fallback"
            if answer.fallback
            else "guidance"
            if answer.guidance
            else "answered"
            if answer.answerable
            else "not_covered"
        )
        trace.claims_kept = len(answer.claims)
        trace.claims_removed = any(w.code == "claims_removed" for w in answer.warnings)
        self.traces.add(trace)
        return answer.model_copy(update={"intent": trace.intent})

    def _find(
        self,
        question: str,
        history: Sequence[str],
        sector: str | None,
        source_ids: Sequence[str] | None,
        trace: Trace,
    ) -> Sequence[Passage]:
        """The evidence: by the knowledge search when there is one, else by plain retrieval.

        Earlier questions are used only to find passages (they never reach the model), after the
        same tidying and removal of personal numbers as the question itself.
        """
        if self._search is None:
            return self._retriever.retrieve(question, source_ids=source_ids)  # no router
        found = self._search.search(
            question,
            history=self._earlier(history),
            sector=sector,
            source_ids=source_ids,
            features=self._features,
        )
        trace.intent = found.intent
        trace.needs_history = found.needs_history
        trace.routed = found.routed
        return found.passages

    @staticmethod
    def _earlier(history: Sequence[str]) -> list[str]:
        """Earlier questions, tidied and without personal numbers or attempts to reprogram us."""
        return [
            redact_personal_data(tidy(item))[0][:MAX_HISTORY_CHARS]
            for item in history[-MAX_HISTORY:]
            if tidy(item) and not is_injection_attempt(tidy(item))
        ]

    def _answer(
        self,
        model: LanguageModel,
        question: str,
        earlier: Sequence[str],
        passages: Sequence[Passage],
        language: Language,
        notices: list[AnswerWarning],
    ) -> Answer:
        best = self._draft_and_check(model, question, passages, language)
        if best is None:  # the provider declined the question
            return self._reply(language, "blocked", notices)

        verification = best.verification
        removed = len(verification.rejections)
        logger.info(
            "checked a draft: %d claims kept, %d removed, %d passages",
            len(verification.claims),
            removed,
            len(passages),
        )
        not_stated = self._not_stated(best.draft, language)
        if removed:
            notices = [*notices, warning(language, "claims_removed")]
        if not verification.claims:
            return self._uncovered(
                model, question, earlier, language, notices, not_stated=not_stated
            )

        now = self._clock()
        claims, citations = build_citations(verification.claims, now)
        sanitized_sources = {p.source_id for p in passages if p.ref in best.prompt.sanitized}
        return Answer(
            answerable=True,
            language=language,
            text="\n".join(claim.text for claim in claims),
            claims=claims,
            citations=citations,
            not_stated=not_stated,
            warnings=[
                *notices,
                *source_warnings(citations, language, now, sanitized_sources=sanitized_sources),
            ],
            disclaimer=say(language, "disclaimer"),
            model=model.name,
        )

    def _draft_and_check(
        self,
        model: LanguageModel,
        question: str,
        passages: Sequence[Passage],
        language: Language,
    ) -> _Attempt | None:
        """The best of at most two drafts, or None if the provider declined the question."""
        best: _Attempt | None = None
        rejections: Sequence[Rejection] = ()
        for number in range(1, MAX_ATTEMPTS + 1):
            prompt = build_prompt(
                question, passages, language=language, nonce=self._nonce(), rejections=rejections
            )
            try:
                draft = model.generate(system=prompt.system, prompt=prompt.user, schema=Draft)
            except AssistantError as error:
                if error.code == "llm_bad_output" and number < MAX_ATTEMPTS:
                    continue  # a reply that was cut off or malformed: try once more
                if best is None and error.code != "llm_blocked":
                    raise
                break  # keep what the first draft gave, or report the block
            attempt = _Attempt(draft, verify(draft, passages, language=language), prompt)
            if best is None or len(attempt.verification.claims) >= len(best.verification.claims):
                best = attempt
            if not draft.answerable or attempt.verification.clean:
                break
            rejections = attempt.verification.rejections
        return best

    def _not_stated(self, draft: Draft, language: Language) -> list[str]:
        """The parts of the question the model says the documents do not cover, if they are sane."""
        kept: list[str] = []
        for raw in draft.not_stated[:MAX_NOT_STATED]:
            item = clean_statement(raw)[:MAX_NOT_STATED_CHARS]
            if (
                item
                and writes_in(item, language)
                and not links(item)
                and neutralize(item)[1] == 0
                and item not in kept
            ):
                kept.append(item)
        return kept

    def _uncovered(
        self,
        model: LanguageModel,
        question: str,
        earlier: Sequence[str],
        language: Language,
        notices: Sequence[AnswerWarning],
        *,
        not_stated: Sequence[str] = (),
    ) -> Answer:
        """The documents have nothing to say: general, labelled help, or else the fixed text.

        Whatever goes wrong here (the model fails, declines, answers in the wrong language or
        with figures) ends in the fixed "the documents do not say", exactly as before.
        """
        fixed = self._reply(language, "not_covered", notices, not_stated=not_stated)
        if not self._guidance:
            return fixed
        system, prompt = build_guidance_prompt(
            question, earlier, language=language, nonce=self._nonce()
        )
        try:
            draft = model.generate(system=system, prompt=prompt, schema=Guidance)
        except AssistantError as error:
            logger.info("no general guidance was written (%s)", error.code)
            if error.code in FALLBACK_CODES:
                self.stats.note_failure(error.code)
            return fixed
        result = check_guidance(draft, language)
        if result.kind == "off_topic":
            return self._reply(language, "off_topic", notices)
        if result.kind == "unusable":
            logger.info("the general guidance was not usable")
            return fixed
        return Answer(
            answerable=False,
            guidance=True,
            language=language,
            text=result.reply,
            guidance_intro=say(language, "guidance_intro"),
            follow_up=result.follow_up,
            warnings=list(notices),
            disclaimer=say(language, "disclaimer"),
            model=model.name,
        )

    def _fallback(
        self, passages: Sequence[Passage], language: Language, notices: Sequence[AnswerWarning]
    ) -> Answer:
        """No explanation, but the passages that best match, exactly as the documents have them.

        Nothing is written by a model here, so nothing needs checking: each citation is the start
        of a real retrieved passage, with the facts needed to judge how fresh it is.
        """
        now = self._clock()
        citations = [
            _excerpt(passage, number, now)
            for number, passage in enumerate(passages[:FALLBACK_PASSAGES], start=1)
        ]
        return Answer(
            answerable=False,
            fallback=True,
            language=language,
            text=say(language, "llm_fallback"),
            citations=citations,
            warnings=[*notices, *source_warnings(citations, language, now)],
            disclaimer=say(language, "disclaimer"),
        )

    def _reply(
        self,
        language: Language,
        key: str,
        notices: Sequence[AnswerWarning],
        *,
        not_stated: Sequence[str] = (),
    ) -> Answer:
        """An answer made only of a fixed text: a refusal, or "the documents do not say"."""
        return Answer(
            answerable=False,
            language=language,
            text=say(language, key),
            not_stated=list(not_stated),
            warnings=list(notices),
            disclaimer=say(language, "disclaimer"),
        )
