"""Web page text extraction: the page's main content, with headings, lists and tables as structure.

Government sites are old and inconsistent: tables nested in tables, ``<h2>`` used to style a whole
paragraph, menus repeated around the content. The extractor is therefore tolerant, and it reports
a warning whenever it had to guess where the content is.
"""

import re
from datetime import date
from email.utils import parsedate_to_datetime
from importlib.metadata import version

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PreformattedString

from app.domain.documents import Block, BlockKind, ParsedDocument
from app.domain.errors import ExtractionError
from app.services.segmentation.normalize import collapse_spaces, normalize_text

# Page furniture that is never content.
_DROP_TAGS = (
    "script", "style", "noscript", "svg", "iframe", "form", "button", "template",
    "nav", "aside", "footer",
)  # fmt: skip
_MAIN_SELECTORS = ("main", "article", "[role=main]", "#content", ".content")
_HEADINGS = {f"h{number}": number for number in range(1, 7)}
# Elements that flow inside a line of text; anything else starts a new block.
_INLINE = frozenset(
    {
        "a", "abbr", "b", "bdi", "bdo", "big", "cite", "code", "data", "dfn", "em", "font", "i",
        "kbd", "label", "mark", "q", "s", "samp", "small", "span", "strong", "sub", "sup", "time",
        "u", "var",
    }
)  # fmt: skip
_LEAF_BLOCKS = frozenset({"p", "dt", "dd", "blockquote", "figcaption", "caption", "pre", "address"})

_BREAK = "\U00002029"  # marks a real line break; newlines in HTML source are only formatting
_source_whitespace = re.compile(r"[\r\n\t\f\v]+")
_MAX_HEADING_CHARS = 150
_MIN_DEDUPE_CHARS = 40
_SENTENCE_END = (".", "?", "!", ";", "।", "॥")
_MAX_SPAN = 20


def extract_html(
    content: bytes,
    *,
    source_id: str,
    selector: str | None = None,
    last_modified: str | None = None,
) -> ParsedDocument:
    """Read a web page into blocks. ``selector`` pins the main content when guessing is unsafe."""
    soup = BeautifulSoup(content, "lxml")
    warnings: list[str] = []
    if _unwrap_page_forms(soup):
        warnings.append("The page's content sits inside a <form> (ASP.NET style); it was read.")
    for tag in soup(_DROP_TAGS):
        tag.decompose()

    root = _find_root(soup, selector, warnings)
    collector = _Collector()
    _walk(root, collector)
    collector.flush()

    document_date = _header_date(last_modified)
    return ParsedDocument(
        source_id=source_id,
        format="html",
        blocks=_drop_repeats(collector.blocks),
        document_date=document_date,
        date_source="http-last-modified" if document_date else None,
        warnings=warnings,
        extractor=f"beautifulsoup4 {version('beautifulsoup4')} + lxml {version('lxml')}",
    )


_PAGE_FORM_SHARE = 0.6  # a form holding this much of the page's text is the page, not a widget


def _unwrap_page_forms(soup: BeautifulSoup) -> bool:
    """Keep the content of a form that wraps the whole page.

    A form is normally a search box or a login: furniture, and dropped. ASP.NET sites, which
    several state portals use, put the entire page inside one ``<form>``; dropping it leaves
    nothing. A form that holds most of the page's text is therefore unwrapped instead (its small
    forms inside are still dropped afterwards).
    """
    body = soup.body
    total = len(body.get_text(strip=True)) if body else 0
    if total == 0:
        return False
    unwrapped = False
    for form in soup.find_all("form"):
        if len(form.get_text(strip=True)) >= _PAGE_FORM_SHARE * total:
            form.unwrap()
            unwrapped = True
    return unwrapped


def _find_root(soup: BeautifulSoup, selector: str | None, warnings: list[str]) -> Tag:
    if selector:
        root = soup.select_one(selector)
        if root is None:
            raise ExtractionError(
                f"The page has no element matching '{selector}'; the site may have changed.",
                code="selector_not_found",
            )
        return root
    for candidate in _MAIN_SELECTORS:
        root = soup.select_one(candidate)
        if root is not None:
            return root
    warnings.append(
        "No main-content container found; menus and footers may be mixed into the text."
    )
    return soup.body or soup


class _Collector:
    """Collects blocks, and gathers loose inline text until a block boundary closes it."""

    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self._pending: list[str] = []

    def inline(self, raw: str) -> None:
        self._pending.append(raw)

    def flush(self) -> None:
        raw = "".join(self._pending)
        self._pending.clear()
        for line in _split_lines(raw):
            self.add("paragraph", line)

    def add(self, kind: BlockKind, text: str, *, level: int | None = None) -> None:
        if text:
            self.blocks.append(Block(kind=kind, text=text, level=level))


def _raw(node: Tag, *, skip: tuple[str, ...] = ()) -> str:
    """Text of ``node`` with a break marker wherever the page really breaks the line."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, PreformattedString):  # comments, CDATA, doctype
            continue
        if isinstance(child, NavigableString):
            parts.append(_source_whitespace.sub(" ", str(child)))
        elif isinstance(child, Tag) and child.name not in skip:
            if child.name == "br":
                parts.append(_BREAK)
            elif child.name in _INLINE:
                parts.append(_raw(child, skip=skip))
            else:
                parts.append(f"{_BREAK}{_raw(child, skip=skip)}{_BREAK}")
    return "".join(parts)


def _split_lines(raw: str) -> list[str]:
    lines = (collapse_spaces(line) for line in normalize_text(raw).split(_BREAK))
    return [line for line in lines if line]


def _lines(node: Tag, *, skip: tuple[str, ...] = ()) -> list[str]:
    return _split_lines(_raw(node, skip=skip))


def _walk(node: Tag, out: _Collector) -> None:
    for child in node.children:
        if isinstance(child, PreformattedString):
            continue
        if isinstance(child, NavigableString):
            out.inline(_source_whitespace.sub(" ", str(child)))
            continue
        if not isinstance(child, Tag):
            continue

        name = child.name
        if name in _HEADINGS:
            out.flush()
            _heading(child, out)
        elif name == "table":
            out.flush()
            _table(child, out)
        elif name in ("ul", "ol"):
            out.flush()
            _list(child, out)
        elif name in _LEAF_BLOCKS:
            out.flush()
            for line in _lines(child):
                out.add("paragraph", line)
        elif name == "br":
            out.inline(_BREAK)
        elif name in _INLINE:
            out.inline(_raw(child))
        else:  # div, section, ...: a container
            out.flush()
            _walk(child, out)
            out.flush()


def _heading(tag: Tag, out: _Collector) -> None:
    text = " ".join(_lines(tag))
    if not text:
        return
    introduces_list = text.endswith(":") and len(text.split()) > 5  # "The rates are as under:"
    if len(text) > _MAX_HEADING_CHARS or text.endswith(_SENTENCE_END) or introduces_list:
        out.add("paragraph", text)  # a heading tag used to style body text
    else:
        out.add("heading", text, level=_HEADINGS[tag.name])


def _list(tag: Tag, out: _Collector) -> None:
    for item in tag.find_all("li", recursive=False):
        for number, line in enumerate(_lines(item, skip=("ul", "ol"))):
            out.add("list_item" if number == 0 else "paragraph", line)
        for nested in item.find_all(["ul", "ol"], recursive=False):
            _list(nested, out)


def _table(table: Tag, out: _Collector) -> None:
    # Pull nested tables out first, so their text is neither lost nor repeated in the outer cell.
    nested = [
        inner.extract() for inner in table.find_all("table") if inner.find_parent("table") is table
    ]
    text = _linearize(*_grid(table))
    if text:
        out.blocks.append(Block(kind="table", text=text))
    for inner in nested:
        _table(inner, out)


def _grid(table: Tag) -> tuple[list[list[str]], bool]:
    """The table's cells as rows, with row/column spans expanded; and whether row 1 is a header."""
    rows: list[list[str]] = []
    spans: dict[int, list[int | str]] = {}  # column -> [rows still to fill, text]
    header = False
    for number, tr in enumerate(table.find_all("tr")):
        cells = tr.find_all(["th", "td"], recursive=False)
        if number == 0:
            header = bool(cells) and all(cell.name == "th" for cell in cells)
        row: list[str] = []
        column = 0
        index = 0
        while index < len(cells) or column in spans:
            if column in spans:
                remaining, text = spans[column]
                row.append(str(text))
                if int(remaining) <= 1:
                    del spans[column]
                else:
                    spans[column][0] = int(remaining) - 1
                column += 1
                continue
            cell = cells[index]
            index += 1
            text = " ".join(_lines(cell))
            rowspan, colspan = _span(cell, "rowspan"), _span(cell, "colspan")
            for _ in range(colspan):
                row.append(text)
                if rowspan > 1:
                    spans[column] = [rowspan - 1, text]
                column += 1
        rows.append(row)
    return rows, header


def _span(cell: Tag, attribute: str) -> int:
    try:
        return min(max(int(str(cell.get(attribute) or 1)), 1), _MAX_SPAN)
    except ValueError:
        return 1


def _linearize(rows: list[list[str]], header: bool) -> str:
    """One line per row. With a header row, each cell is labelled so a line stands on its own."""
    rows = [row for row in rows if any(row)]
    if not rows:
        return ""
    labels = rows[0] if header and len(rows) > 1 else None
    body = rows[1:] if labels else rows
    lines = []
    for row in body:
        if labels and len(row) == len(labels):
            pairs = zip(labels, row, strict=True)
            lines.append("; ".join(f"{label}: {cell}" for label, cell in pairs if cell))
        else:
            lines.append(" | ".join(_unique_neighbours(row)))
    return "\n".join(lines)


def _unique_neighbours(row: list[str]) -> list[str]:
    """Drop the repeats that a merged (colspan) cell leaves behind."""
    return [
        cell for number, cell in enumerate(row) if cell and (number == 0 or cell != row[number - 1])
    ]


def _drop_repeats(blocks: list[Block]) -> list[Block]:
    """Remove long blocks that appear more than once (pages often include a text twice)."""
    seen: set[tuple[str, str]] = set()
    kept: list[Block] = []
    for block in blocks:
        if block.kind != "heading" and len(block.text) >= _MIN_DEDUPE_CHARS:
            key = (block.kind, block.text)
            if key in seen:
                continue
            seen.add(key)
        kept.append(block)
    return kept


def _header_date(last_modified: str | None) -> date | None:
    if not last_modified:
        return None
    try:
        return parsedate_to_datetime(last_modified).date()
    except (TypeError, ValueError):
        return None
