"""Splits a parsed document into passages small enough to embed and precise enough to cite.

Chunks follow the document's own structure: a heading starts a new chunk once the current one has
some substance, a chunk never ends on an orphaned heading, and a block that is too long is cut at
sentence (or table-row) boundaries. Each chunk's text is an exact slice of ``ParsedDocument.text``
and records its offsets, so a later "show original" view can highlight precisely what was cited.
"""

import re
from dataclasses import dataclass

from app.domain.documents import Chunk, ParsedDocument
from app.services.segmentation.scripts import detect_script
from app.services.segmentation.structure import clause_label

# Bump when chunking or extraction behaviour changes, so existing indexes are rebuilt.
CHUNKER_VERSION = "2"

_BLOCK_GAP = 2  # ParsedDocument.text joins blocks with a blank line
_MAX_SECTION_CHARS = 300
_SENTENCE_BREAK = re.compile(r"(?<=[.!?।॥])\s+(?=[\"'(\[A-Z0-9\U00000900-\U00000DFF])")
_LINE_BREAK = re.compile(r"\n+")


@dataclass(frozen=True)
class ChunkerConfig:
    """Sizes are in characters, not tokens, which differ widely between Latin and Indic text."""

    target_chars: int = 900
    max_chars: int = 1400
    min_chars: int = 250  # a heading starts a new chunk only once the current one is this long
    overlap_chars: int = 150  # repeated at the start of a chunk that continues a long block
    # A table is cut into chunks of whole rows about this long, each standing alone. A chunk of
    # many rows has a blurred meaning, so a question about one row would not find it.
    table_chars: int = 450


@dataclass
class _Unit:
    """A run of document text that goes into exactly one chunk."""

    start: int  # offsets into ParsedDocument.text
    end: int
    block_start: int  # where the block this unit was cut from begins; bounds the overlap
    heading: bool
    page: int | None
    ocr: bool
    label: str
    section: str
    continuation: bool  # cut from the middle of a long block
    atomic: bool = False  # a table piece: never merged with neighbouring text

    @property
    def length(self) -> int:
        return self.end - self.start


def chunk_document(
    doc: ParsedDocument,
    *,
    title: str,
    doc_hash: str,
    config: ChunkerConfig | None = None,
) -> list[Chunk]:
    """Chunk ``doc``. ``title`` and the section path are added to each chunk's embedding text."""
    config = config or ChunkerConfig()
    text = doc.text
    groups = _pack(_units(doc, config), config)
    return [
        _build(index, group, text=text, doc=doc, title=title, doc_hash=doc_hash, config=config)
        for index, group in enumerate(groups)
    ]


def _units(doc: ParsedDocument, config: ChunkerConfig) -> list[_Unit]:
    units: list[_Unit] = []
    headings: list[tuple[int, str]] = []  # (depth, text) of the headings in force
    position = 0
    for block in doc.blocks:
        start = position
        position = start + len(block.text) + _BLOCK_GAP

        if block.kind == "heading":
            depth = block.level or 1
            while headings and headings[-1][0] >= depth:
                headings.pop()
            headings.append((depth, block.text))
            units.append(
                _Unit(
                    start=start,
                    end=start + len(block.text),
                    block_start=start,
                    heading=True,
                    page=block.page,
                    ocr=block.ocr,
                    label=clause_label(block.text),
                    section=_section_path(headings),
                    continuation=False,
                )
            )
            continue

        section = _section_path(headings)
        label = clause_label(block.text)
        is_table = block.kind == "table"
        limit = config.table_chars if is_table else config.max_chars
        target = config.table_chars if is_table else config.target_chars
        for number, (low, high) in enumerate(_pieces(block.text, config, limit, target)):
            units.append(
                _Unit(
                    start=start + low,
                    end=start + high,
                    block_start=start,
                    heading=False,
                    page=block.page,
                    ocr=block.ocr,
                    label=label if number == 0 else "",
                    section=section,
                    continuation=number > 0 and not is_table,  # table rows are never repeated
                    atomic=is_table,
                )
            )
    return units


def _section_path(headings: list[tuple[int, str]]) -> str:
    path = " > ".join(text for _, text in headings)
    return path if len(path) <= _MAX_SECTION_CHARS else path[: _MAX_SECTION_CHARS - 1] + "…"


def _pieces(text: str, config: ChunkerConfig, limit: int, target: int) -> list[tuple[int, int]]:
    """Cut a block longer than ``limit`` into runs of about ``target`` characters."""
    if len(text) <= limit:
        return [(0, len(text))]
    spans = _spans(text, config.max_chars)
    pieces: list[tuple[int, int]] = []
    start, end = spans[0]
    for low, high in spans[1:]:
        if high - start <= target:
            end = high
        else:
            pieces.append((start, end))
            start, end = low, high
    pieces.append((start, end))
    return pieces


def _spans(text: str, max_chars: int) -> list[tuple[int, int]]:
    """Sentence spans (table rows for multi-line text); a span that is still too long is cut."""
    separator = _LINE_BREAK if "\n" in text else _SENTENCE_BREAK
    raw: list[tuple[int, int]] = []
    last = 0
    for match in separator.finditer(text):
        raw.append((last, match.start()))
        last = match.end()
    raw.append((last, len(text)))

    spans: list[tuple[int, int]] = []
    for low, high in raw:
        while high - low > max_chars:
            cut = text.rfind(" ", low + max_chars // 2, low + max_chars)
            cut = cut if cut != -1 else low + max_chars
            spans.append((low, cut))
            low = cut + 1 if text[cut : cut + 1] == " " else cut
        spans.append((low, high))
    return [(low, high) for low, high in spans if high > low]


def _pack(units: list[_Unit], config: ChunkerConfig) -> list[list[_Unit]]:
    groups: list[list[_Unit]] = []
    current: list[_Unit] = []

    def size(group: list[_Unit]) -> int:
        return sum(unit.length for unit in group) + _BLOCK_GAP * max(len(group) - 1, 0)

    def has_content(group: list[_Unit]) -> bool:
        return any(not unit.heading for unit in group)

    def flush() -> None:
        nonlocal current
        carry: list[_Unit] = []
        while current and current[-1].heading:  # never end a chunk on an orphaned heading
            carry.insert(0, current.pop())
        groups.append(current)
        current = carry

    for unit in units:
        if has_content(current):
            new_section_is_due = unit.heading and size(current) >= config.min_chars
            chunk_is_full = size(current) + _BLOCK_GAP + unit.length > config.target_chars
            stands_alone = unit.atomic or current[-1].atomic  # a table chunk is never merged
            if stands_alone or new_section_is_due or (not unit.heading and chunk_is_full):
                flush()
        current.append(unit)
    if has_content(current):
        flush()

    if (
        len(groups) > 1
        and size(groups[-1]) < config.min_chars
        and size(groups[-2]) + _BLOCK_GAP + size(groups[-1]) <= config.max_chars
        and not any(unit.atomic for unit in [*groups[-1], *groups[-2]])
    ):
        groups[-2].extend(groups.pop())
    return groups


def _build(
    index: int,
    group: list[_Unit],
    *,
    text: str,
    doc: ParsedDocument,
    title: str,
    doc_hash: str,
    config: ChunkerConfig,
) -> Chunk:
    first = group[0]
    start = _overlap_start(text, first, config.overlap_chars) if first.continuation else first.start
    end = group[-1].end
    body = text[start:end]  # units are contiguous in the document, so this is exactly their text

    section = next((unit.section for unit in group if not unit.heading), first.section)
    pages = [unit.page for unit in group if unit.page is not None]
    return Chunk(
        id=f"{doc.source_id}:{doc_hash[:12]}:{index:04d}",
        index=index,
        text=body,
        embed_text="\n".join(part for part in (title, section, body) if part),
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
        section=section,
        clause=next((unit.label for unit in group if unit.label), ""),
        char_start=start,
        char_end=end,
        script=detect_script(body),
        ocr=any(unit.ocr for unit in group),
    )


def _overlap_start(text: str, unit: _Unit, overlap_chars: int) -> int:
    """Where to start a continuation chunk so it repeats a little of the previous one."""
    candidate = max(unit.block_start, unit.start - overlap_chars)
    if candidate == unit.block_start:
        return candidate
    window = text[candidate : unit.start]
    row_end = window.find("\n")  # a table: begin at a row boundary, never inside a row
    if row_end != -1:
        return candidate + row_end + 1
    boundary = _SENTENCE_BREAK.search(window)
    if boundary:
        return candidate + boundary.end()
    space = window.find(" ")
    return candidate + space + 1 if space != -1 else unit.start
