"""Showing an answer back to the person in words, in every language."""

from decimal import Decimal

from app.domain.eligibility import FieldDef, LocalText, Scalar

_YES = LocalText(en="Yes", bn="হ্যাঁ", hi="हाँ")
_NO = LocalText(en="No", bn="না", hi="नहीं")


def format_number(value: int | float) -> str:
    """With the Indian grouping (12,34,567) and without a needless ".0"; digits are 0-9."""
    number = Decimal(str(value)).normalize()
    whole, _, fraction = f"{number:f}".partition(".")
    negative = whole.startswith("-")
    digits = whole.lstrip("-")
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join([head, *groups, tail]) if head else ",".join([*groups, tail])
    return f"{'-' if negative else ''}{digits}{'.' + fraction if fraction else ''}"


def describe_answer(field: FieldDef, value: Scalar) -> LocalText:
    if isinstance(value, bool):
        return _YES if value else _NO
    if isinstance(value, str):
        choice = next((c for c in field.choices if c.id == value), None)
        return choice.label if choice else LocalText(en=value, bn=value, hi=value)
    shown = format_number(value)
    if field.display is None:
        return LocalText(en=shown, bn=shown, hi=shown)
    return LocalText(
        en=field.display.en.replace("{value}", shown),
        bn=field.display.bn.replace("{value}", shown),
        hi=field.display.hi.replace("{value}", shown),
    )
