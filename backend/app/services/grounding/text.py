"""Finding a quote in the passage it claims to come from, in a way that survives re-typing.

A model asked to copy words exactly still joins broken lines, straightens quotation marks and
drops a full stop. None of that changes what the words say, so the comparison ignores white
space, punctuation, letter case and the script a digit is written in, and nothing else: a
different word, figure or vowel sign is a different quote. A match is mapped back to positions in
the passage's own text so the interface can highlight the words as the document writes them.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

# Fewer letters and digits than this are too little to show that a claim rests on the passage.
MIN_QUOTE_CHARS = 15

# An omission inside a quote: "At least 60% ... in the last qualifying examination".
_OMISSION = re.compile(
    r"\[\s*(?:\.{2,}|\N{HORIZONTAL ELLIPSIS})\s*\]|\.{3,}|\N{HORIZONTAL ELLIPSIS}"
)


@dataclass(frozen=True)
class Squashed:
    """Text reduced to what identifies it, with where each kept character came from."""

    chars: str
    origin: tuple[int, ...]  # origin[i] is the index in the original text of chars[i]


def squash(text: str) -> Squashed:
    """Keep letters, vowel signs and digits, lower-cased, with every digit written as 0-9."""
    chars: list[str] = []
    origin: list[int] = []
    for index, original in enumerate(text):
        for char in unicodedata.normalize("NFKC", original).casefold():
            category = unicodedata.category(char)
            if category == "Nd":
                chars.append(str(unicodedata.decimal(char)))
            elif category[0] in "LMN":  # letters, marks (the vowel signs of Indic scripts), numbers
                chars.append(char)
            else:
                continue
            origin.append(index)
    return Squashed("".join(chars), tuple(origin))


@dataclass(frozen=True)
class Located:
    """Where a quote sits in the passage text: ``(start, end)`` pairs, in reading order."""

    spans: tuple[tuple[int, int], ...]

    def words(self, passage_text: str) -> str:
        """The passage's own words for the quote; omissions are shown as an ellipsis."""
        return " \N{HORIZONTAL ELLIPSIS} ".join(
            passage_text[start:end] for start, end in self.spans
        )


def _merge(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return tuple(merged)


def _needles(quote: str) -> list[str]:
    needles = [squash(part).chars for part in _OMISSION.split(quote)]
    return [needle for needle in needles if needle]


def is_long_enough(quote: str) -> bool:
    """False for a quote with too few letters and digits to show that a claim rests on a passage."""
    return sum(len(needle) for needle in _needles(quote)) >= MIN_QUOTE_CHARS


def find_quote(quote: str, passage: Squashed) -> Located | None:
    """Locate ``quote`` in a passage, or None if it is not there or too short to mean anything."""
    if not is_long_enough(quote):
        return None
    needles = _needles(quote)

    spans: list[tuple[int, int]] = []
    after = 0
    for needle in needles:
        # The parts of a quote come in the order of the passage, so look past the previous part
        # first; a part that is out of order is still a real quote of the passage.
        position = passage.chars.find(needle, after)
        if position < 0:
            position = passage.chars.find(needle)
        if position < 0:
            return None
        last = position + len(needle) - 1
        spans.append((passage.origin[position], passage.origin[last] + 1))
        after = last + 1
    return Located(_merge(spans))


def find_in_any(quote: str, passages: Sequence[Squashed]) -> tuple[int, Located] | None:
    """The first passage, by position in ``passages``, that contains the quote."""
    for index, passage in enumerate(passages):
        located = find_quote(quote, passage)
        if located is not None:
            return index, located
    return None
