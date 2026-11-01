import itertools
import random
from typing import ClassVar

import pytest

from app.domain.eligibility import Condition, Criterion, Evidence, LocalText, Operator, Scalar
from app.services.eligibility.engine import all_hold, evaluate, holds, judge

TEXT = LocalText(en="rule", bn="নিয়ম", hi="नियम")
QUOTE = [Evidence(source_id="s", quote="a quote that is long enough")]


def rule(
    field: str,
    op: Operator,
    value: Scalar | list[str],
    *,
    waived_when: list[Condition] | None = None,
    id: str | None = None,
) -> Criterion:
    return Criterion(
        id=id or f"{field}-{op}",
        label=TEXT,
        condition=Condition(field=field, op=op, value=value),
        waived_when=waived_when or [],
        evidence=QUOTE,
    )


# The rule of the spec's scenarios T2 to T4: age 18-25, income < 2,50,000, resident, enrolled.
SPEC_RULES = [
    rule("age", "gte", 18),
    rule("age", "lte", 25, id="age-max"),
    rule("income", "lt", 250000),
    rule("resident", "eq", True),
    rule("enrolled", "eq", True),
]


class TestTheSpecScenarios:
    def test_t2_every_criterion_met_is_eligible(self) -> None:
        answers = {"age": 21, "income": 180000, "resident": True, "enrolled": True}

        result = evaluate(SPEC_RULES, answers)

        assert result.outcome == "eligible"
        assert [j.status for j in result.judgements] == ["met"] * 5
        assert result.unanswered == []

    def test_t3_income_exactly_at_a_strict_limit_is_not_eligible(self) -> None:
        answers = {"age": 21, "income": 250000, "resident": True, "enrolled": True}

        result = evaluate(SPEC_RULES, answers)

        assert result.outcome == "not_eligible"
        failed = [j.criterion.id for j in result.judgements if j.status == "not_met"]
        assert failed == ["income-lt"]

    def test_t4_a_skipped_question_needs_more_info_and_says_which(self) -> None:
        answers = {"age": 21, "resident": True, "enrolled": True}

        result = evaluate(SPEC_RULES, answers)

        assert result.outcome == "need_more_info"
        assert result.unanswered == ["income"]


class TestBoundaries:
    """Whether the edge counts is written in the rule, as the document words it."""

    @pytest.mark.parametrize(
        ("op", "value", "answer", "expected"),
        [
            ("lt", 800000, 799999, True),
            ("lt", 800000, 800000, False),  # "less than Rs. 8 Lakh"
            ("lte", 250000, 250000, True),  # "not more than Rs. 2,50,000"
            ("lte", 250000, 250001, False),
            ("gte", 60, 60, True),  # "at least 60%"
            ("gte", 60, 59.99, False),
            ("gt", 60, 60, False),
            ("gt", 60, 60.01, True),
            ("eq", 2, 2.0, True),
            ("ne", 2, 3, True),
        ],
    )
    def test_numbers(self, op: Operator, value: int, answer: float, expected: bool) -> None:
        assert holds(Condition(field="x", op=op, value=value), {"x": answer}) is expected

    def test_a_fraction_is_not_rounded_into_range(self) -> None:
        assert holds(Condition(field="marks", op="gte", value=60), {"marks": 59.999999}) is False

    def test_choices(self) -> None:
        in_ = Condition(field="how", op="in", value=["first_year", "lateral_entry"])
        not_in = Condition(field="how", op="not_in", value=["other"])

        assert holds(in_, {"how": "lateral_entry"}) is True
        assert holds(in_, {"how": "other"}) is False
        assert holds(not_in, {"how": "first_year"}) is True
        assert holds(not_in, {"how": "other"}) is False

    def test_yes_and_no_are_not_confused_with_numbers(self) -> None:
        yes = Condition(field="x", op="eq", value=True)

        assert holds(yes, {"x": True}) is True
        assert holds(yes, {"x": False}) is False
        assert holds(yes, {"x": 1}) is False  # a number is not a yes

    def test_a_missing_answer_is_unknown_not_false(self) -> None:
        assert holds(Condition(field="x", op="eq", value=True), {}) is None


class TestUnknownIsNeverDecided:
    def test_a_missing_answer_makes_the_criterion_unknown(self) -> None:
        assert judge(rule("income", "lt", 10), {}).status == "unknown"

    def test_a_definite_failure_is_final_even_with_other_questions_unanswered(self) -> None:
        # Nothing the person answers next can make them eligible, so "not eligible" is certain.
        result = evaluate(SPEC_RULES, {"age": 30})

        assert result.outcome == "not_eligible"
        assert result.unanswered == ["income", "resident", "enrolled"]

    def test_no_criteria_answered_is_need_more_info(self) -> None:
        assert evaluate(SPEC_RULES, {}).outcome == "need_more_info"

    def test_unanswered_questions_are_listed_once_in_the_order_of_the_rules(self) -> None:
        rules = [rule("a", "eq", True), rule("b", "eq", True), rule("a", "ne", False, id="again")]

        assert evaluate(rules, {}).unanswered == ["a", "b"]


class TestWaivers:
    """ "Not applicable for Board toppers": a waiver is itself something that may be unanswered."""

    INCOME = rule(
        "income",
        "lte",
        250000,
        waived_when=[Condition(field="topper", op="eq", value=True)],
    )

    def test_a_waived_criterion_is_met_whatever_the_income(self) -> None:
        judgement = judge(self.INCOME, {"income": 900000, "topper": True})

        assert (judgement.status, judgement.waived) == ("met", True)

    def test_a_waiver_applies_even_before_the_income_is_given(self) -> None:
        assert judge(self.INCOME, {"topper": True}).status == "met"

    def test_income_over_the_limit_is_not_met_once_the_waiver_is_ruled_out(self) -> None:
        assert judge(self.INCOME, {"income": 900000, "topper": False}).status == "not_met"

    def test_income_over_the_limit_is_unknown_while_the_waiver_is_unanswered(self) -> None:
        # The person may be exempt, so "no" would be a guess.
        judgement = judge(self.INCOME, {"income": 900000})

        assert (judgement.status, judgement.missing) == ("unknown", ("topper",))

    def test_income_within_the_limit_needs_no_waiver(self) -> None:
        judgement = judge(self.INCOME, {"income": 200000})

        assert (judgement.status, judgement.waived) == ("met", False)

    def test_with_nothing_answered_both_questions_are_wanted(self) -> None:
        assert judge(self.INCOME, {}).missing == ("income", "topper")

    def test_several_waiver_conditions_must_all_hold(self) -> None:
        both = rule(
            "income",
            "lte",
            10,
            waived_when=[
                Condition(field="a", op="eq", value=True),
                Condition(field="b", op="eq", value=True),
            ],
        )

        assert judge(both, {"income": 99, "a": True, "b": False}).status == "not_met"
        assert judge(both, {"income": 99, "a": True}).status == "unknown"
        assert judge(both, {"income": 99, "a": True, "b": True}).status == "met"

    def test_no_waiver_conditions_waive_nothing(self) -> None:
        assert all_hold([], {}) is False


class TestEveryCombinationOfAnswers:
    """Three yes/no questions, each yes, no or skipped: all 27 cases, against the invariants."""

    RULES: ClassVar[list[Criterion]] = [
        rule("a", "eq", True),
        rule("b", "eq", True),
        rule("c", "eq", False),
    ]
    FIELDS = ("a", "b", "c")

    def cases(self) -> list[dict[str, Scalar]]:
        options = [(None, True, False)] * 3
        return [
            {
                field: value
                for field, value in zip(self.FIELDS, combo, strict=True)
                if value is not None
            }
            for combo in itertools.product(*options)
        ]

    def test_eligible_only_when_everything_is_answered_and_met(self) -> None:
        for answers in self.cases():
            outcome = evaluate(self.RULES, answers).outcome
            fully_met = answers == {"a": True, "b": True, "c": False}
            assert (outcome == "eligible") == fully_met, answers

    def test_a_skipped_question_can_never_give_eligible(self) -> None:
        # SPEC AC6.
        for answers in self.cases():
            if len(answers) < 3:
                assert evaluate(self.RULES, answers).outcome != "eligible", answers

    def test_a_definite_failure_always_gives_not_eligible(self) -> None:
        for answers in self.cases():
            failed = (
                answers.get("a") is False or answers.get("b") is False or answers.get("c") is True
            )
            if failed:
                assert evaluate(self.RULES, answers).outcome == "not_eligible", answers

    def test_otherwise_it_is_need_more_info(self) -> None:
        for answers in self.cases():
            failed = (
                answers.get("a") is False or answers.get("b") is False or answers.get("c") is True
            )
            if not failed and len(answers) < 3:
                assert evaluate(self.RULES, answers).outcome == "need_more_info", answers

    def test_answering_a_skipped_question_never_undoes_a_not_eligible(self) -> None:
        for answers in self.cases():
            if evaluate(self.RULES, answers).outcome != "not_eligible":
                continue
            for field in self.FIELDS:
                if field not in answers:
                    for value in (True, False):
                        more = {**answers, field: value}
                        assert evaluate(self.RULES, more).outcome == "not_eligible", (answers, more)


class TestDeterminism:
    """SPEC AC5: the same answers always give the same result."""

    def test_the_order_in_which_answers_arrive_changes_nothing(self) -> None:
        answers: dict[str, Scalar] = {
            "age": 21,
            "income": 180000,
            "resident": True,
            "enrolled": True,
        }
        expected = evaluate(SPEC_RULES, answers)

        for _ in range(20):
            shuffled = list(answers.items())
            random.shuffle(shuffled)
            assert evaluate(SPEC_RULES, dict(shuffled)) == expected

    def test_repeating_the_check_gives_an_identical_result(self) -> None:
        answers = {"age": 21, "income": 250000}

        assert evaluate(SPEC_RULES, answers) == evaluate(SPEC_RULES, answers)

    def test_the_answers_are_not_changed(self) -> None:
        answers: dict[str, Scalar] = {"age": 21}

        evaluate(SPEC_RULES, answers)

        assert answers == {"age": 21}
