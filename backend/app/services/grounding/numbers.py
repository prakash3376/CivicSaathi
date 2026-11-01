"""What a statement says in figures: amounts, dates, months and web addresses.

SPEC rule R2: numbers are sacred. A claim may only state a figure that is in the words it quotes.
Figures are compared by value, not by spelling, so "Rs.2,50,000/-", "2.5 lakh" and the same
amount in Bengali or Devanagari digits are one figure, while 250000 and 25000 are two. That is
also what lets the check run on a Bengali answer drawn from an English document (rule R2:
"post-translation").

The check is deliberately one-sided. It finds a figure that the quotes do not contain; it cannot
find a sentence whose figures are right and whose meaning is wrong.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.grounding.text import squash

Problem = Literal["number", "month", "link"]

# How much a word multiplies the figure before it. English, Bengali and Hindi.
_MULTIPLIERS = {
    "thousand": 1_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "lac": 100_000,
    "lacs": 100_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
    "million": 1_000_000,
    "হাজার": 1_000,
    "লক্ষ": 100_000,
    "লাখ": 100_000,
    "কোটি": 10_000_000,
    "हज़ार": 1_000,
    "हजार": 1_000,
    "लाख": 100_000,
    "करोड़": 10_000_000,
    "करोड": 10_000_000,
}

# Months. Full names count wherever they appear; the others (an abbreviation, or a word that is
# also an ordinary word such as "may") count only beside a day or a year.
_MONTHS_ANYWHERE = {
    **dict.fromkeys(("january", "জানুয়ারি", "জানুয়ারী", "जनवरी"), 1),
    **dict.fromkeys(("february", "ফেব্রুয়ারি", "ফেব্রুয়ারী", "फ़रवरी", "फरवरी"), 2),
    **dict.fromkeys(("march", "মার্চ", "मार्च"), 3),
    **dict.fromkeys(("april", "এপ্রিল", "अप्रैल"), 4),
    **dict.fromkeys(("june", "জুন", "जून"), 6),
    **dict.fromkeys(("july", "জুলাই", "जुलाई"), 7),
    **dict.fromkeys(("august", "আগস্ট", "আগষ্ট", "अगस्त"), 8),
    **dict.fromkeys(("september", "সেপ্টেম্বর", "सितंबर", "सितम्बर"), 9),
    **dict.fromkeys(("october", "অক্টোবর", "अक्टूबर"), 10),
    **dict.fromkeys(("november", "নভেম্বর", "नवंबर", "नवम्बर"), 11),
    **dict.fromkeys(("december", "ডিসেম্বর", "दिसंबर", "दिसम्बर"), 12),
}
_MONTHS_BESIDE_A_DATE = {
    **dict.fromkeys(("may", "মে", "मई"), 5),
    **dict.fromkeys(("jan",), 1),
    **dict.fromkeys(("feb",), 2),
    **dict.fromkeys(("mar",), 3),
    **dict.fromkeys(("apr",), 4),
    **dict.fromkeys(("jun",), 6),
    **dict.fromkeys(("jul",), 7),
    **dict.fromkeys(("aug",), 8),
    **dict.fromkeys(("sep", "sept"), 9),
    **dict.fromkeys(("oct",), 10),
    **dict.fromkeys(("nov",), 11),
    **dict.fromkeys(("dec",), 12),
}


def _nfc(word: str) -> str:
    return unicodedata.normalize("NFC", word).casefold()


_ANYWHERE = {_nfc(name): number for name, number in _MONTHS_ANYWHERE.items()}
_BESIDE_A_DATE = {_nfc(name): number for name, number in _MONTHS_BESIDE_A_DATE.items()}

_MULTIPLIER = "|".join(
    sorted((_nfc(word) for word in _MULTIPLIERS), key=len, reverse=True),
)
_MULTIPLIER_VALUE = {_nfc(word): value for word, value in _MULTIPLIERS.items()}

_NUMBER = re.compile(
    # 1,000,000 / 2,50,000 / 250000, then an optional fraction, then an optional "lakh".
    r"(\d{1,3}(?:,\d{3})+(?!\d)|\d{1,3}(?:,\d{2})+,\d{3}(?!\d)|\d+)(\.\d+)?"
    rf"(?:\s*({_MULTIPLIER})(?![^\W\d_]))?",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")  # 2026-06-01
_NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)")  # 1.6.2026
_SESSION = re.compile(  # 2025-26
    r"(?<!\d)(\d{4})\s*[-\N{EN DASH}\N{EM DASH}/]\s*(\d{4}|\d{2})(?!\d)"
)
_DAY = re.compile(r"\d{1,4}(?:st|nd|rd|th)?")

_LINK = re.compile(
    r"(?:https?://|www\.)[^\s<>()\[\]'\"]+"
    r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
    r"|(?<![\w.@/-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:gov\.in|nic\.in|org\.in|co\.in|in|org|com|net|edu)"
    r"(?![\w-])(?:/[^\s<>()\[\]'\"]*)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Figures:
    numbers: frozenset[str]
    months: frozenset[int]


def _ascii_digits(text: str) -> str:
    return "".join(
        str(unicodedata.decimal(char)) if unicodedata.category(char) == "Nd" else char
        for char in text
    )


def _canonical(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _words(text: str) -> list[str]:
    """Runs of letters, vowel signs and digits. (``\\w`` would cut Bengali words at every sign.)"""
    words: list[str] = []
    current: list[str] = []
    for char in text:
        if unicodedata.category(char)[0] in "LMN":
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def _months_named(text: str) -> set[int]:
    spelled = _words(text)
    words = [_nfc(word) for word in spelled]
    found: set[int] = set()
    for index, word in enumerate(words):
        if word in _ANYWHERE:
            found.add(_ANYWHERE[word])
        elif word in _BESIDE_A_DATE:
            # "may" is nearly always the verb ("students of class 12 may apply"): only "May"
            # and "MAY" can be the month.
            if word == "may" and spelled[index] not in ("May", "MAY"):
                continue
            before = words[index - 1] if index else ""
            before_that = words[index - 2] if index > 1 else ""
            after = words[index + 1] if index + 1 < len(words) else ""
            if (
                _DAY.fullmatch(before)
                or _DAY.fullmatch(after)
                or (before == "of" and _DAY.fullmatch(before_that))
            ):
                found.add(_BESIDE_A_DATE[word])
    return found


def figures(text: str) -> Figures:
    """The numbers (by value) and the months a text states."""
    text = _ascii_digits(unicodedata.normalize("NFC", text))
    numbers: set[str] = set()
    months = _months_named(text)

    def take_session(match: re.Match[str]) -> str:
        first, second = match.group(1), match.group(2)
        numbers.add(first)
        numbers.add(second if len(second) == 4 else first[:2] + second)
        return " "

    def take_date(match: re.Match[str], *, year_first: bool = False) -> str:
        first, month, last = match.groups()
        day, year = (last, first) if year_first else (first, last)
        if not 1 <= int(month) <= 12:
            return match.group()  # not a date after all: leave it for the number scan
        months.add(int(month))
        numbers.add(_canonical(Decimal(day)))
        numbers.add(_canonical(Decimal(year if len(year) == 4 else "20" + year)))
        return " "

    text = _ISO_DATE.sub(lambda match: take_date(match, year_first=True), text)
    text = _SESSION.sub(take_session, text)
    text = _NUMERIC_DATE.sub(take_date, text)

    for match in _NUMBER.finditer(text):
        value = Decimal(match.group(1).replace(",", "") + (match.group(2) or ""))
        if match.group(3):
            value *= _MULTIPLIER_VALUE[_nfc(match.group(3))]
        numbers.add(_canonical(value))
    return Figures(frozenset(numbers), frozenset(months))


def _link_key(link: str) -> str:
    link = re.sub(r"^(?:https?://)?(?:www\.)?", "", link.strip().rstrip(".,;:!?)"), flags=re.I)
    return squash(link.rstrip("/")).chars


def links(text: str) -> frozenset[str]:
    """The web and e-mail addresses in a text, reduced to what identifies them."""
    return frozenset(_link_key(match.group()) for match in _LINK.finditer(text))


def unsupported(statement: str, quotes: Sequence[str]) -> list[Problem]:
    """What a statement states that its quotes do not."""
    claimed = figures(statement)
    available_numbers: set[str] = set()
    available_months: set[int] = set()
    for quote in quotes:
        stated = figures(quote)
        available_numbers |= stated.numbers
        available_months |= stated.months

    problems: list[Problem] = []
    if not claimed.numbers <= available_numbers:
        problems.append("number")
    if not claimed.months <= available_months:
        problems.append("month")
    quoted_text = squash(" ".join(quotes)).chars
    if any(link not in quoted_text for link in links(statement)):
        problems.append("link")
    return problems
