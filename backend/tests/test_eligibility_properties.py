"""Properties that must hold for *every* input, searched for by Hypothesis rather than picked by hand.

A wrong "eligible" sends a citizen to an office with the wrong papers; a wrong "not eligible" tells
someone entitled to a benefit that they are not. These are the rules the product promises (SPEC AC5
and AC6), stated as invariants and attacked with generated rules, generated answers and hostile
input. A failure prints the smallest case that breaks the promise.
"""

import json
import string
from datetime import date
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.domain.eligibility import Condition, Criterion, Evidence, LocalText, Scalar
from app.services.eligibility.engine import evaluate
from app.services.eligibility.loader import load_schemes
from app.services.eligibility.service import EligibilityInputError, SchemeService
from app.services.ingestion.registry import load_registry

PROFILE = settings(
    max_examples=200,
    deadline=None,
    database=None,  # no .hypothesis folder left in the repository
    suppress_health_check=[HealthCheck.too_slow],
)

TEXT = LocalText(en="rule", bn="নিয়ম", hi="नियम")
QUOTE = [Evidence(source_id="s", quote="a quote that is long enough")]
NUMBERS = ("n1", "n2", "n3")
FLAGS = ("b1", "b2")
CHOICES = ("red", "green", "blue")

numbers = st.integers(min_value=-1_000_000, max_value=10_000_000)


@st.composite
def conditions(draw: st.DrawFn) -> Condition:
    kind = draw(st.sampled_from(["number", "flag", "choice"]))
    if kind == "number":
        return Condition(
            field=draw(st.sampled_from(NUMBERS)),
            op=draw(st.sampled_from(["lt", "lte", "gt", "gte", "eq", "ne"])),
            value=draw(numbers),
        )
    if kind == "flag":
        return Condition(
            field=draw(st.sampled_from(FLAGS)),
            op=draw(st.sampled_from(["eq", "ne"])),
            value=draw(st.booleans()),
        )
    return Condition(
        field="c1",
        op=draw(st.sampled_from(["in", "not_in"])),
        value=draw(st.lists(st.sampled_from(CHOICES), min_size=1, max_size=2, unique=True)),
    )


@st.composite
def rules(draw: st.DrawFn) -> list[Criterion]:
    count = draw(st.integers(min_value=1, max_value=6))
    return [
        Criterion(
            id=f"rule-{index}",
            label=TEXT,
            condition=draw(conditions()),
            waived_when=draw(st.lists(conditions(), max_size=2)),
            evidence=QUOTE,
        )
        for index in range(count)
    ]


@st.composite
def answers(draw: st.DrawFn) -> dict[str, Scalar]:
    given_: dict[str, Scalar] = {}
    for field in NUMBERS:
        if draw(st.booleans()):
            given_[field] = draw(numbers)
    for field in FLAGS:
        if draw(st.booleans()):
            given_[field] = draw(st.booleans())
    if draw(st.booleans()):
        given_["c1"] = draw(st.sampled_from(CHOICES))
    return given_


def statuses(criteria: list[Criterion], given_: dict[str, Scalar]) -> dict[str, str]:
    return {j.criterion.id: j.status for j in evaluate(criteria, given_).judgements}


class TestTheEngine:
    @PROFILE
    @given(rules(), answers())
    def test_eligible_means_every_rule_was_met_and_nothing_is_missing(
        self, criteria: list[Criterion], given_: dict[str, Scalar]
    ) -> None:
        result = evaluate(criteria, given_)

        if result.outcome == "eligible":
            assert result.unanswered == []
            assert {j.status for j in result.judgements} == {"met"}

    @PROFILE
    @given(rules(), answers(), st.data())
    def test_a_skipped_question_can_never_turn_into_a_no(
        self, criteria: list[Criterion], given_: dict[str, Scalar], data: st.DataObject
    ) -> None:
        # AC6: "not met" is only ever said because of an answer. Take answers away, and every
        # criterion that is now "not met" was "not met" before too.
        kept = {
            field: value for field, value in given_.items() if data.draw(st.booleans(), label=field)
        }

        before = statuses(criteria, given_)
        after = statuses(criteria, kept)

        for rule_id, status in after.items():
            if status == "not_met":
                assert before[rule_id] == "not_met"

    @PROFILE
    @given(rules(), answers(), st.data())
    def test_removing_answers_can_never_make_a_person_more_eligible_or_less(
        self, criteria: list[Criterion], given_: dict[str, Scalar], data: st.DataObject
    ) -> None:
        kept = {
            field: value for field, value in given_.items() if data.draw(st.booleans(), label=field)
        }

        full = evaluate(criteria, given_).outcome
        partial = evaluate(criteria, kept).outcome

        if full == "eligible":
            assert partial in {"eligible", "need_more_info"}  # never a "no" invented from silence
        if partial == "not_eligible":
            assert full == "not_eligible"  # a definite no does not depend on what was left out

    @PROFILE
    @given(rules())
    def test_answering_nothing_is_never_eligible_and_never_a_no(
        self, criteria: list[Criterion]
    ) -> None:
        result = evaluate(criteria, {})

        assert result.outcome == "need_more_info"
        assert {j.status for j in result.judgements} == {"unknown"}

    @PROFILE
    @given(rules(), answers())
    def test_the_same_answers_always_give_the_same_result_and_are_never_changed(
        self, criteria: list[Criterion], given_: dict[str, Scalar]
    ) -> None:
        snapshot = dict(given_)

        first = evaluate(criteria, given_)
        second = evaluate(criteria, given_)

        assert (first.outcome, first.unanswered) == (second.outcome, second.unanswered)
        assert given_ == snapshot

    @PROFILE
    @given(rules(), answers(), st.randoms(use_true_random=False))
    def test_the_order_of_the_rules_does_not_change_the_outcome(
        self, criteria: list[Criterion], given_: dict[str, Scalar], rng: Any
    ) -> None:
        shuffled = list(criteria)
        rng.shuffle(shuffled)

        assert evaluate(shuffled, given_).outcome == evaluate(criteria, given_).outcome

    @PROFILE
    @given(
        age=st.integers(min_value=-50, max_value=150),
        others=st.fixed_dictionaries({}, optional={"income": numbers, "resident": st.booleans()}),
    )
    def test_an_age_outside_the_rule_is_never_eligible_whatever_else_is_answered(
        self, age: int, others: dict[str, Scalar]
    ) -> None:
        # The product's scenario: 18 to 25 inclusive. 17 and 26 must fail; 18 and 25 must not.
        criteria = [
            Criterion(
                id="age-min",
                label=TEXT,
                condition=Condition(field="age", op="gte", value=18),
                evidence=QUOTE,
            ),
            Criterion(
                id="age-max",
                label=TEXT,
                condition=Condition(field="age", op="lte", value=25),
                evidence=QUOTE,
            ),
        ]

        outcome = evaluate(criteria, {"age": age, **others}).outcome

        if age < 18 or age > 25:
            assert outcome == "not_eligible"
        else:
            assert outcome == "eligible"

    @PROFILE
    @given(
        threshold=st.integers(min_value=1, max_value=10_000_000),
        offset=st.integers(min_value=-2, max_value=2),
    )
    def test_the_boundary_follows_the_words_of_the_document(
        self, threshold: int, offset: int
    ) -> None:
        # "less than" (lt) excludes the figure itself; "not more than" (lte) includes it.
        income = threshold + offset

        def outcome(op: str) -> str:
            rule = Criterion(
                id="income",
                label=TEXT,
                condition=Condition(field="income", op=op, value=threshold),  # type: ignore[arg-type]
                evidence=QUOTE,
            )
            return evaluate([rule], {"income": income}).outcome

        assert (outcome("lt") == "eligible") == (income < threshold)
        assert (outcome("lte") == "eligible") == (income <= threshold)


@pytest.fixture(scope="module")
def service() -> SchemeService:
    book = load_schemes(sources={spec.id: spec.url for spec in load_registry()})
    return SchemeService(book, clock=lambda: date(2026, 10, 20))


def tracks(service: SchemeService) -> list[tuple[str, str]]:
    found = []
    for summary in service.catalogue():
        if summary.layout == "check":
            details = service.details(summary.id)
            found.extend((summary.id, track.id) for track in details.tracks)  # type: ignore[union-attr]
    return found


JSON = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-(10**500), max_value=10**500)
    | st.floats(allow_nan=True, allow_infinity=True)
    | st.text(alphabet=string.printable + "কहअ", max_size=20),
    lambda inner: (
        st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=8), inner, max_size=3)
    ),
    max_leaves=6,
)


class TestTheRealSchemesAgainstHostileInput:
    @PROFILE
    @given(st.data())
    def test_whatever_is_sent_the_answer_is_a_result_or_a_clean_refusal_never_a_crash(
        self, service: SchemeService, data: st.DataObject
    ) -> None:
        scheme_id, track_id = data.draw(st.sampled_from(tracks(service)))
        questions = service.details(scheme_id).tracks  # type: ignore[union-attr]
        fields = [q.field for t in questions if t.id == track_id for q in t.questions] + [
            "not_a_question"
        ]
        raw = data.draw(st.dictionaries(st.sampled_from(fields), JSON, max_size=len(fields)))

        refusal: EligibilityInputError | None = None
        try:
            result = service.check(scheme_id, track_id, raw)
        except EligibilityInputError as error:
            refusal = error
        if refusal is not None:
            assert refusal.code in {"invalid_answer", "unknown_question"}
            assert "not_a_question" not in refusal.message  # nothing submitted is echoed back
            return
        assert result.outcome in {"eligible", "not_eligible", "need_more_info"}
        if result.outcome == "eligible":
            assert result.unanswered == []
            assert {criterion.status for criterion in result.criteria} == {"met"}

    @PROFILE
    @given(st.data())
    def test_a_value_outside_a_questions_limits_is_refused_never_accepted(
        self, service: SchemeService, data: st.DataObject
    ) -> None:
        scheme_id, track_id = data.draw(st.sampled_from(tracks(service)))
        track = next(t for t in service.details(scheme_id).tracks if t.id == track_id)  # type: ignore[union-attr]
        bounded = [q for q in track.questions if q.type == "number" and q.maximum is not None]
        if not bounded:
            return
        question = data.draw(st.sampled_from(bounded))
        assert question.minimum is not None
        assert question.maximum is not None
        low, high = question.minimum, question.maximum
        if question.integer:  # whole numbers for a whole-number question, so none rounds into range
            outside: float = data.draw(
                st.one_of(
                    st.integers(min_value=-(10**9), max_value=int(low) - 1),
                    st.integers(min_value=int(high) + 1, max_value=10**12),
                )
            )
        else:
            outside = data.draw(
                st.one_of(
                    st.floats(min_value=-1e9, max_value=low - 0.5),
                    st.floats(min_value=high + 0.5, max_value=1e12),
                )
            )
        value = outside

        with pytest.raises(EligibilityInputError) as refusal:
            service.check(scheme_id, track_id, {question.field: value})

        assert refusal.value.code == "invalid_answer"
        assert refusal.value.message == f"The answer to '{question.field}' is not valid."

    def test_skipping_every_question_of_every_scheme_is_never_eligible(
        self, service: SchemeService
    ) -> None:
        for scheme_id, track_id in tracks(service):
            result = service.check(scheme_id, track_id, {})

            assert result.outcome == "need_more_info", (scheme_id, track_id)

    def test_a_huge_integer_is_a_refusal_not_a_server_error(self, service: SchemeService) -> None:
        # Found by the probe that led to these tests: it was a 500 (OverflowError).
        with pytest.raises(EligibilityInputError) as refusal:
            service.check("aicte-pragati", "degree", {"family_income": 10**400})

        assert refusal.value.code == "invalid_answer"

    def test_the_result_never_repeats_what_was_submitted(self, service: SchemeService) -> None:
        marker = "ZZ-SECRET-9"
        with pytest.raises(EligibilityInputError) as refusal:
            service.check("aicte-pragati", "degree", {"gender": marker})

        assert marker not in refusal.value.message
        assert marker not in json.dumps(refusal.value.__dict__, default=str)
