"""Removes personal numbers from a question before it is sent anywhere or written anywhere.

SPEC section 9: no Aadhaar, PAN or bank numbers are requested or stored, and any that turn up are
redacted before processing and logging. A question goes to a third-party model, so this runs first.
It errs on the side of removing too much: a question rarely needs a 12-digit number to be answered.
Passages are never redacted: the official helpline numbers and e-mail addresses in them are
exactly what a citizen may need.
"""

import re

PLACEHOLDER = "[removed]"

# Bengali and Devanagari digits are matched as if they were ASCII digits. Each is one character,
# so a position in the translated text is the same position in the original.
_ASCII_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯०१२३४५६७८९", "01234567890123456789")

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Card numbers first: their first three groups would otherwise be taken for an Aadhaar number
    # and the last group left behind.
    ("card", re.compile(r"(?<!\d)\d{4}(?:[\s-]\d{4}){3,4}(?!\d)")),
    # Twelve digits in groups of four: an Aadhaar number, or a typo of one.
    ("aadhaar", re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("pan", re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b")),
    ("ifsc", re.compile(r"\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("phone", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("account", re.compile(r"(?<!\d)\d{9,18}(?!\d)")),
)


def redact_personal_data(text: str) -> tuple[str, set[str]]:
    """Replace personal numbers with a placeholder; returns the text and the kinds found."""
    kinds: set[str] = set()
    for kind, pattern in _PATTERNS:
        matches = list(pattern.finditer(text.translate(_ASCII_DIGITS)))
        if not matches:
            continue
        kinds.add(kind)
        for match in reversed(matches):  # from the end, so earlier positions stay valid
            text = text[: match.start()] + PLACEHOLDER + text[match.end() :]
    return text, kinds
