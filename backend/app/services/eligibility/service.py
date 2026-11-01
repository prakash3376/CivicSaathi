"""The catalogue of schemes and the eligibility check, the two things the API offers.

Everything here is deterministic. The only input besides the rules and the answers is today's date,
and it is used for one thing: telling whether a deadline has passed.

Answers are checked before they are used, and a bad one is reported by *which question* it was
about, never by its value: an answer can be private (an income, a category).
"""

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

from app.domain.catalogue import BudgetRecord, BudgetView, Entry, ProgrammeDetails, SourceRef
from app.domain.eligibility import (
    Applicability,
    Checklist,
    ChecklistDocument,
    CriterionResult,
    CriterionView,
    Deadline,
    DeadlineView,
    DocumentItem,
    EligibilityResult,
    FieldDef,
    LocalText,
    Question,
    Scalar,
    Scheme,
    SchemeDetails,
    SchemeSummary,
    Track,
    TrackStub,
    TrackView,
)
from app.services.catalogue.budget import budget_views
from app.services.eligibility.engine import all_hold, evaluate
from app.services.eligibility.formatting import describe_answer
from app.services.eligibility.loader import SchemeBook

# SPEC rule R6, in every language.
DISCLAIMER = LocalText(
    en="Informational summary, not legal advice. Check the official document before acting.",
    bn="এটি শুধুমাত্র তথ্যমূলক সারসংক্ষেপ, আইনি পরামর্শ নয়। কোনো পদক্ষেপ নেওয়ার আগে সরকারি নথিটি মিলিয়ে দেখুন।",
    hi=(
        "यह केवल जानकारी के लिए सारांश है, कानूनी सलाह नहीं। "
        "कोई भी कदम उठाने से पहले सरकारी दस्तावेज़ से मिलान कर लें।"
    ),
)


class EligibilityInputError(Exception):
    """The request cannot be answered as sent. ``code`` is stable; the message is safe to show and
    never contains anything the person submitted."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _today() -> date:
    return datetime.now(UTC).date()


class SchemeService:
    """The catalogue: the schemes with a questionnaire, and the programmes and services that are
    read, in one list. Only the first kind can be checked for eligibility."""

    def __init__(
        self,
        book: SchemeBook,
        *,
        entries: Sequence[Entry] = (),
        budget: Sequence[BudgetRecord] = (),
        sources: Mapping[str, SourceRef] | None = None,
        clock: Callable[[], date] = _today,
    ) -> None:
        clashes = {scheme.id for scheme in book.schemes} & {entry.id for entry in entries}
        if clashes:
            raise ValueError(f"ids used by both a scheme and a catalogue entry: {sorted(clashes)}")
        self._book = book
        self._entries = {entry.id: entry for entry in entries}
        self._sources = dict(sources or {})
        self._budget = list(budget)
        self._clock = clock

    # --- the catalogue ------------------------------------------------------------------------

    def catalogue(self) -> list[SchemeSummary]:
        return [
            *(self._summary(scheme) for scheme in self._book.schemes),
            *(self._entry_summary(entry) for entry in self._entries.values()),
        ]

    def knowledge(self) -> tuple[list[Scheme], list[Entry], list[BudgetRecord]]:
        """The loaded data, for counting what each sector has."""
        return list(self._book.schemes), list(self._entries.values()), list(self._budget)

    def budget(self) -> list[BudgetView]:
        return budget_views(self._budget, self._sources)

    def details(self, scheme_id: str) -> SchemeDetails | ProgrammeDetails | None:
        entry = self._entries.get(scheme_id)
        if entry is not None:
            return self._entry_details(entry)
        scheme = self._book.scheme(scheme_id)
        if scheme is None:
            return None
        return SchemeDetails(
            id=scheme.id,
            name=scheme.name,
            authority=scheme.authority,
            level=scheme.level,
            state=scheme.state,
            sectors=scheme.sectors,
            summary=scheme.summary,
            source_ids=scheme.source_ids,
            tracks=[self._track_view(scheme, track) for track in scheme.tracks],
            steps=scheme.steps,
            contacts=scheme.contacts,
            deadlines=[self._deadline(deadline) for deadline in scheme.deadlines],
            apply=scheme.apply,
            not_stated=scheme.not_stated,
        )

    def _entry_summary(self, entry: Entry) -> SchemeSummary:
        return SchemeSummary(
            id=entry.id,
            name=entry.name,
            authority=entry.department,
            level=entry.level,
            state=entry.state,
            sectors=entry.sectors,
            summary=entry.summary,
            source_ids=entry.source_ids,
            tracks=[],
            deadline=None,
            layout="info",
            kind=entry.kind,
            status=entry.status,
            target=entry.target,
            benefit=entry.benefits[0].text,
            last_verified=entry.last_verified,
        )

    def _entry_details(self, entry: Entry) -> ProgrammeDetails:
        return ProgrammeDetails(
            id=entry.id,
            name=entry.name,
            kind=entry.kind,
            sectors=entry.sectors,
            authority=entry.department,
            level=entry.level,
            state=entry.state,
            applicable_states=entry.applicable_states,
            status=entry.status,
            status_note=entry.status_note,
            summary=entry.summary,
            target=entry.target,
            source_ids=entry.source_ids,
            last_verified=entry.last_verified,
            published_on=entry.published_on,
            effective_on=entry.effective_on,
            benefits=entry.benefits,
            eligibility=entry.eligibility,
            exclusions=entry.exclusions,
            documents=entry.documents,
            steps=entry.steps,
            apply=entry.apply,
            not_stated=entry.not_stated,
            sources=[self._sources[i] for i in entry.source_ids if i in self._sources],
        )

    def _summary(self, scheme: Scheme) -> SchemeSummary:
        return SchemeSummary(
            id=scheme.id,
            name=scheme.name,
            authority=scheme.authority,
            level=scheme.level,
            state=scheme.state,
            sectors=scheme.sectors,
            summary=scheme.summary,
            source_ids=scheme.source_ids,
            tracks=[TrackStub(id=track.id, label=track.label) for track in scheme.tracks],
            deadline=self._deadline(scheme.deadlines[0]) if scheme.deadlines else None,
        )

    def _track_view(self, scheme: Scheme, track: Track) -> TrackView:
        return TrackView(
            id=track.id,
            label=track.label,
            description=track.description,
            benefit=track.benefit,
            criteria=[
                CriterionView(id=c.id, label=c.label, note=c.note, evidence=c.evidence)
                for c in self._book.criteria(scheme, track)
            ],
            questions=self._book.questions(scheme, track),
            documents=self._checklist_documents(scheme, track, {}),
            caveats=self._book.caveats(scheme, track),
        )

    def _deadline(self, deadline: Deadline) -> DeadlineView:
        days = (deadline.on - self._clock()).days
        return DeadlineView(
            id=deadline.id,
            label=deadline.label,
            on=deadline.on,
            status="closed" if days < 0 else "closes_today" if days == 0 else "open",
            days_left=days if days >= 0 else None,
            scanned=deadline.scanned,
            evidence=deadline.evidence,
        )

    # --- the check ----------------------------------------------------------------------------

    def check(
        self, scheme_id: str, track_id: str, raw_answers: Mapping[str, Any]
    ) -> EligibilityResult:
        scheme = self._book.scheme(scheme_id)
        if scheme is None:
            raise EligibilityInputError("There is no such scheme.", code="unknown_scheme")
        track = next((t for t in scheme.tracks if t.id == track_id), None)
        if track is None:
            raise EligibilityInputError(
                "This scheme has no such course or group.", code="unknown_track"
            )
        questions = self._book.questions(scheme, track)
        answers = self._clean(questions, raw_answers)

        criteria = self._book.criteria(scheme, track)
        evaluation = evaluate(criteria, answers)
        order = {question.field: position for position, question in enumerate(questions)}
        return EligibilityResult(
            scheme_id=scheme.id,
            track_id=track.id,
            outcome=evaluation.outcome,
            criteria=[
                CriterionResult(
                    id=j.criterion.id,
                    label=j.criterion.label,
                    status=j.status,
                    waived=j.waived,
                    field=j.criterion.condition.field,
                    answer_text=(
                        describe_answer(
                            self._book.fields[j.criterion.condition.field],
                            answers[j.criterion.condition.field],
                        )
                        if j.criterion.condition.field in answers
                        else None
                    ),
                    note=j.criterion.note,
                    evidence=j.criterion.evidence,
                )
                for j in evaluation.judgements
            ],
            unanswered=sorted(evaluation.unanswered, key=order.__getitem__),
            caveats=self._book.caveats(scheme, track),
            checklist=Checklist(
                documents=self._checklist_documents(scheme, track, answers),
                steps=scheme.steps,
                contacts=scheme.contacts,
                deadlines=[self._deadline(deadline) for deadline in scheme.deadlines],
                apply=scheme.apply,
                not_stated=scheme.not_stated,
            ),
            disclaimer=DISCLAIMER,
        )

    def _clean(self, questions: list[Question], raw: Mapping[str, Any]) -> dict[str, Scalar]:
        """Keep the answers that were given, after checking each against its question."""
        asked = {question.field: question for question in questions}
        answers: dict[str, Scalar] = {}
        for field, value in raw.items():
            question = asked.get(field)
            if question is None:
                # Not echoed: the key is part of what was submitted.
                raise EligibilityInputError(
                    "One of the answers is not a question of this scheme.", code="unknown_question"
                )
            if value is None:
                continue  # skipped: an unknown
            answers[field] = _checked(self._book.fields[field], value)
        return answers

    def _checklist_documents(
        self, scheme: Scheme, track: Track, answers: Mapping[str, Scalar]
    ) -> list[ChecklistDocument]:
        documents: list[ChecklistDocument] = []
        for document in self._book.documents(scheme, track):
            applicability = _applicability(document, answers)
            if applicability is not None:
                documents.append(
                    ChecklistDocument(
                        id=document.id,
                        label=document.label,
                        detail=document.detail,
                        applicability=applicability,
                        evidence=document.evidence,
                    )
                )
        return documents


def _applicability(document: DocumentItem, answers: Mapping[str, Scalar]) -> Applicability | None:
    """'needed'; 'maybe' (it depends on something not yet answered, or the document itself says
    "if applicable"); or None when the answers show that it is not needed."""
    if not document.needed_when:
        return "maybe" if document.if_applicable else "needed"
    needed = all_hold(document.needed_when, answers)
    if needed is False:
        return None
    return "needed" if needed is True and not document.if_applicable else "maybe"


MAX_ANSWER_MAGNITUDE = 10**15


def _checked(field: FieldDef, value: Any) -> Scalar:
    """The value if it suits the question, else an error naming only the question."""

    def refuse() -> EligibilityInputError:
        return EligibilityInputError(
            f"The answer to '{field.id}' is not valid.", code="invalid_answer"
        )

    if field.type == "yes_no":
        if not isinstance(value, bool):
            raise refuse()
        return value
    if field.type == "choice":
        if not isinstance(value, str) or value not in {choice.id for choice in field.choices}:
            raise refuse()
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise refuse()
    # An integer is never converted to a float here: a 400-digit one overflows it. And no household
    # figure (an income, an age, a count) comes near the bound, so a larger number is a mistake.
    if isinstance(value, float) and not math.isfinite(value):
        raise refuse()
    if abs(value) > MAX_ANSWER_MAGNITUDE:
        raise refuse()
    if field.integer and isinstance(value, float) and not value.is_integer():
        raise refuse()
    if (field.minimum is not None and value < field.minimum) or (
        field.maximum is not None and value > field.maximum
    ):
        raise refuse()
    return int(value) if field.integer else value
