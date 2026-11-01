"""Text clean-up shared by every extractor, so the chunker always sees the same kind of text."""

import re
import unicodedata

_LIGATURES = {
    "\U0000fb00": "ff",
    "\U0000fb01": "fi",
    "\U0000fb02": "fl",
    "\U0000fb03": "ffi",
    "\U0000fb04": "ffl",
    "\U0000fb05": "st",
    "\U0000fb06": "st",
}
# Characters that carry no meaning in running text. ZWJ and ZWNJ (zero-width joiner and
# non-joiner) are kept on purpose: Indian scripts need them to form conjuncts, so removing them
# would change words.
_INVISIBLE = "\N{ZERO WIDTH SPACE}\N{WORD JOINER}\N{ZERO WIDTH NO-BREAK SPACE}\N{SOFT HYPHEN}"
_ODD_SPACES = (
    "\N{NO-BREAK SPACE}\N{EN SPACE}\N{EM SPACE}\N{THREE-PER-EM SPACE}\N{FOUR-PER-EM SPACE}"
    "\N{SIX-PER-EM SPACE}\N{FIGURE SPACE}\N{PUNCTUATION SPACE}\N{THIN SPACE}\N{HAIR SPACE}"
    "\N{NARROW NO-BREAK SPACE}\N{MEDIUM MATHEMATICAL SPACE}\N{IDEOGRAPHIC SPACE}\t\x0b\x0c"
)

_TRANSLATION = {
    **{ord(char): replacement for char, replacement in _LIGATURES.items()},
    **dict.fromkeys(map(ord, _INVISIBLE)),
    **{ord(char): " " for char in _ODD_SPACES},
}
_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")
_MULTIPLE_SPACES = re.compile(r" {2,}")


def normalize_text(text: str) -> str:
    """Canonical form of extracted text: NFC, ligatures expanded, odd spaces and controls removed.

    Numbers, currency signs and punctuation are left exactly as extracted: figures in the source
    must survive unchanged (SPEC rule R2).
    """
    text = unicodedata.normalize("NFC", text).translate(_TRANSLATION)
    return _CONTROL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))


def collapse_spaces(line: str) -> str:
    """Trim a line and squeeze runs of spaces."""
    return _MULTIPLE_SPACES.sub(" ", line).strip()
