"""Turns the lines of an extracted PDF page into blocks: headings, numbered clauses, paragraphs.

A PDF gives us lines, not paragraphs, so structure is inferred from how the lines look. The rules
are heuristics tuned on real Indian government documents. They are deliberately conservative:
when in doubt, text stays together, because a wrongly split sentence hurts more than a merged
paragraph does.
"""

import re
from collections.abc import Sequence

from app.domain.documents import Block, BlockKind
from app.services.segmentation.normalize import collapse_spaces

_SENTENCE_END = (".", "?", "!", ";", "।", "॥")
_PAGE_NOISE = re.compile(r"^(?:page\s+\d+\s*(?:of|/)\s*\d+|-\s*\d+\s*-)$", re.IGNORECASE)
# An ALL-CAPS line that ends on one of these continues on the next line, so it is not a heading.
_DANGLING_WORDS = frozenset({"AND", "OR", "OF", "FOR", "THE", "TO", "IN", "ON", "BY", "WITH", "&"})
_MAX_HEADING_CHARS = 200

_QUESTION = re.compile(r"^Q(?:uestion)?\.?\s*(?P<num>\d+)\s*[.:)]?\s+\S", re.IGNORECASE)
_ANSWER = re.compile(r"^Ans(?:wer)?\b\s*[.:]?", re.IGNORECASE)
_KEYWORD_HEADING = re.compile(
    r"^(?:annexure|appendix|chapter|schedule|अनुलग्नक|परिशिष्ट|अध्याय|अनुसूची|পরিশিষ্ট|অধ্যায়|তফসিল)"
    r"(?=$|[\s:.\-\N{EN DASH}\N{EM DASH}0-9IVXivx])",
    re.IGNORECASE,
)
# "2.1 Scope", "2.1.3 Amount", "2.1. Scope". A decimal such as "2.5 lakh" is not a clause number,
# so the word after the number must start with a capital letter (or an Indic letter).
_LEVELED = re.compile(
    r"^(?P<label>\d{1,2}(?:\.\d{1,2})+)\s*[.)]?\s+(?=[A-Z(\U00000900-\U00000DFF])"
)
# "1. Text", "2) Text". A bare "8 Lakh" at the start of a wrapped line is not a clause.
_SINGLE = re.compile(r"^(?P<label>\d{1,2})[.)]\s+(?=\S)")
_LETTERED = re.compile(r"^\((?P<label>[A-Za-z]|[ivxlcIVXLC]{1,5}|\d{1,2})\)\s+(?=\S)")
_BULLET = re.compile(r"^[•●▪■◦‣∙·*\N{EN DASH}\N{EM DASH}-]\s+(?=\S)")


def clause_label(text: str) -> str:
    """The clause number a passage starts with (``2.1``, ``(a)``, ``Q.3``), or ``""``."""
    line = text.lstrip()
    if match := _QUESTION.match(line):
        return f"Q.{match.group('num')}"
    if match := (_LEVELED.match(line) or _SINGLE.match(line)):
        return match.group("label")
    if match := _LETTERED.match(line):
        return f"({match.group('label')})"
    return ""


def list_marker(line: str) -> str | None:
    """The label if the line opens a numbered, lettered or bulleted item (``""`` for a bullet)."""
    label = clause_label(line)
    if label:
        return label
    return "" if _BULLET.match(line) else None


def heading_depth(line: str) -> int | None:
    """Depth of a heading (1 is the top) if the line looks like one, else ``None``."""
    if len(line) > 300:
        return None
    if _QUESTION.match(line):
        return 2

    if len(line) <= 90:
        if _KEYWORD_HEADING.match(line):
            return 1
        if _is_caps_heading(line):
            return 1

    # "2. Eligibility", "3.1 Scope of the scheme". A longer numbered line that merely lacks a
    # final full stop is the first line of a wrapped list item, not a heading.
    leveled = _LEVELED.match(line) or _SINGLE.match(line)
    if (
        leveled
        and len(line) <= 60
        and not line.endswith((*_SENTENCE_END, ":"))
        and len(line[leveled.end() :].split()) <= 4
    ):
        return leveled.group("label").count(".") + 1
    return None


def _uppercase_share(line: str) -> float:
    letters = [char for char in line if char.isalpha()]
    return sum(char.isupper() for char in letters) / len(letters) if letters else 0.0


def _is_caps_heading(line: str) -> bool:
    """An ALL-CAPS line of words. Table cells such as 'UG (SCIENCE)' must not pass for one."""
    words = line.split()
    return (
        len(words) >= 2
        and sum(char.isalpha() for char in line) >= 8
        and not line.endswith((*_SENTENCE_END, ":", ","))
        and not any(char in line for char in "(),")
        and not any(char.isdigit() for char in line)
        and words[-1] not in _DANGLING_WORDS
        and _uppercase_share(line) >= 0.85
    )


def lines_to_blocks(text: str, *, page: int | None, ocr: bool = False) -> list[Block]:
    """Group the lines of one page into blocks, in reading order."""
    lines = [collapse_spaces(line) for line in text.split("\n")]
    lines = [line for line in lines if not _PAGE_NOISE.match(line)]
    width = _typical_width(lines)

    blocks: list[Block] = []
    paragraph: list[str] = []
    kind: BlockKind = "paragraph"
    previous_was_caps_heading = False  # the previous line was an ALL-CAPS heading (same block)
    open_question = False  # a question heading that has not reached its question mark yet

    def flush() -> None:
        if paragraph:
            blocks.append(Block(kind=kind, text=_join(paragraph), page=page, ocr=ocr))
            paragraph.clear()

    for line in lines:
        if not line:
            flush()
            previous_was_caps_heading = open_question = False
            continue
        if open_question and (
            _ANSWER.match(line) or list_marker(line) is not None or heading_depth(line) is not None
        ):
            open_question = False  # the question had no question mark; this line starts the answer
        if open_question:
            # A long FAQ question wrapped: the rest of it runs up to the first question mark.
            head, mark, rest = line.partition("?")
            question = f"{blocks[-1].text} {head}{mark}".rstrip()
            blocks[-1] = blocks[-1].model_copy(update={"text": question})
            open_question = not mark and len(question) < _MAX_HEADING_CHARS
            line = rest.strip()
            if not line:
                continue
        if (
            previous_was_caps_heading
            and _uppercase_share(line) >= 0.85
            and len(blocks[-1].text) >= 0.6 * width  # the first line is nearly full, so it wrapped
            and len(blocks[-1].text) + len(line) < _MAX_HEADING_CHARS
        ):
            # A long ALL-CAPS heading wrapped onto a second line.
            blocks[-1] = blocks[-1].model_copy(update={"text": f"{blocks[-1].text} {line}"})
            continue
        depth = heading_depth(line)
        previous_was_caps_heading = depth == 1 and _is_caps_heading(line)
        if depth is not None:
            flush()
            blocks.append(Block(kind="heading", text=line, level=depth, page=page, ocr=ocr))
            open_question = (
                bool(_QUESTION.match(line)) and not line.endswith("?") and len(line) >= 0.6 * width
            )
        elif list_marker(line) is not None:
            flush()
            kind = "list_item"
            paragraph.append(line)
        else:
            if paragraph and _ends_paragraph(paragraph[-1], width):
                flush()
            if not paragraph:
                kind = "paragraph"
            paragraph.append(line)
    flush()
    return blocks


def _typical_width(lines: Sequence[str]) -> int:
    """How long a 'full' line is on this page: the 90th percentile of line lengths."""
    lengths = sorted(len(line) for line in lines if line)
    if not lengths:
        return 0
    return max(lengths[int(0.9 * (len(lengths) - 1))], 40)


def _ends_paragraph(line: str, width: int) -> bool:
    """A colon introduces a list; a short line that ends a sentence closes its paragraph."""
    if line.endswith(":"):
        return True
    return line.endswith(_SENTENCE_END) and len(line) < 0.6 * width


def _join(lines: Sequence[str]) -> str:
    """Join wrapped lines. A trailing hyphen is kept (``2021-`` + ``22``): it may be a real one."""
    joined = lines[0]
    for line in lines[1:]:
        joined += line if joined.endswith("-") and line[:1].isalnum() else f" {line}"
    return joined
