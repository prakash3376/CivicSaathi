"""Deciding eligibility: a pure function of a scheme's rules and a person's answers.

No model, no clock, no randomness: the same answers always give the same result (SPEC AC5).
Every comparison has three possible answers, true, false or *unknown* (the question was skipped),
and unknown is never turned into either of the others (AC6, rule R3):

* a criterion whose answer is missing is ``unknown``;
* a criterion that fails but could still be exempted (the exemption's own question is unanswered)
  is ``unknown`` too, because the person may be exempt;
* the outcome is **not eligible** if any required criterion is definitely not met, since nothing
  the person answers later can change that; otherwise **need more info** if any is unknown;
  otherwise **eligible**.

Whether a boundary counts depends on the words of the document and is written in the rule:
"less than Rs. 8 Lakh" is ``lt``, "not more than Rs. 2,50,000" is ``lte``.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.eligibility import Condition, Criterion, Outcome, Scalar, Status


def _number(value: Scalar | list[str]) -> Decimal:
    return Decimal(str(value))


def holds(condition: Condition, answers: Mapping[str, Scalar]) -> bool | None:
    """True or False if the answer settles the condition, None if it was not answered."""
    answer = answers.get(condition.field)
    if answer is None:
        return None
    expected = condition.value
    match condition.op:
        case "eq":
            return _same(answer, expected)
        case "ne":
            return not _same(answer, expected)
        case "in":
            return isinstance(expected, list) and answer in expected
        case "not_in":
            return isinstance(expected, list) and answer not in expected
        case "lt":
            return _number(answer) < _number(expected)
        case "lte":
            return _number(answer) <= _number(expected)
        case "gt":
            return _number(answer) > _number(expected)
        case "gte":
            return _number(answer) >= _number(expected)


def _same(answer: Scalar, expected: Scalar | list[str]) -> bool:
    if isinstance(answer, bool) or isinstance(expected, bool):
        return answer is expected
    if isinstance(answer, str) or isinstance(expected, str):
        return answer == expected
    return _number(answer) == _number(expected)


def all_hold(conditions: Sequence[Condition], answers: Mapping[str, Scalar]) -> bool | None:
    """Three-valued AND: false if any is false, else unknown if any is unknown, else true.
    No conditions at all is false: nothing is exempted."""
    if not conditions:
        return False
    results = [holds(condition, answers) for condition in conditions]
    if any(result is False for result in results):
        return False
    if any(result is None for result in results):
        return None
    return True


@dataclass(frozen=True)
class Judgement:
    criterion: Criterion
    status: Status
    waived: bool
    missing: tuple[str, ...]  # fields whose answers would settle this criterion


def judge(criterion: Criterion, answers: Mapping[str, Scalar]) -> Judgement:
    waiver = all_hold(criterion.waived_when, answers)
    if waiver is True:
        return Judgement(criterion, "met", True, ())

    base = holds(criterion.condition, answers)
    if base is True:
        return Judgement(criterion, "met", False, ())

    missing_waiver = tuple(
        condition.field for condition in criterion.waived_when if holds(condition, answers) is None
    )
    if base is False:
        if waiver is None:  # failed, but the person may be exempt: ask before saying no
            return Judgement(criterion, "unknown", False, missing_waiver)
        return Judgement(criterion, "not_met", False, ())
    return Judgement(
        criterion,
        "unknown",
        False,
        (criterion.condition.field, *(missing_waiver if waiver is None else ())),
    )


@dataclass(frozen=True)
class Evaluation:
    outcome: Outcome
    judgements: list[Judgement]
    unanswered: list[str]  # in the order the criteria are listed, without repeats


def evaluate(criteria: Sequence[Criterion], answers: Mapping[str, Scalar]) -> Evaluation:
    judgements = [judge(criterion, answers) for criterion in criteria]
    statuses = {judgement.status for judgement in judgements}
    outcome: Outcome
    if "not_met" in statuses:
        outcome = "not_eligible"
    elif "unknown" in statuses:
        outcome = "need_more_info"
    else:
        outcome = "eligible"
    unanswered = list(
        dict.fromkeys(field for judgement in judgements for field in judgement.missing)
    )
    return Evaluation(outcome, judgements, unanswered)
