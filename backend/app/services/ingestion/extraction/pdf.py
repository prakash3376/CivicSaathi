"""PDF text extraction with PDFium, the engine inside Chrome.

PDFium decodes Indian-language and symbol fonts (bullets, dashes) more faithfully than the
pure-Python libraries and copes with the malformed files common on government sites. It can also
render pages to images, which the OCR step for scanned documents will need.
"""

import re
from collections import Counter
from datetime import date
from importlib.metadata import version

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from app.domain.documents import Block, PageInfo, ParsedDocument
from app.domain.errors import ExtractionError
from app.services.segmentation.normalize import collapse_spaces, normalize_text
from app.services.segmentation.structure import lines_to_blocks

MAX_PAGES = 600
# A page whose text is (almost) all invisible is a scan with an OCR layer hidden behind the image.
OCR_INVISIBLE_SHARE = 0.8
_RUNNING_MIN_PAGES = 3
_PAGE_NUMBER = re.compile(r"^(?:\d{1,3}|-\s*\d{1,3}\s*-)$")

_PDF_DATE = re.compile(r"D:(?P<year>\d{4})(?P<month>\d{2})?(?P<day>\d{2})?")
# Bullets from Symbol/Wingdings fonts are decoded as private-use or replacement characters.
_BULLET_GLYPHS = (
    "\U0000f0b7\U0000f0a7\U0000f0d8\U0000f076\U0000fffd"
    "\N{BULLET}\N{BLACK CIRCLE}\N{BLACK SMALL SQUARE}\N{BLACK SQUARE}\N{WHITE BULLET}"
    "\N{TRIANGULAR BULLET}\N{BULLET OPERATOR}"
)
_LEADING_BULLET = re.compile("^[" + _BULLET_GLYPHS + r"]\s*")
_HYPHEN_BREAK = "\U0000fffe"  # PDFium's marker for a hyphen at a line break
_REPLACEMENT = "\U0000fffd"  # what a decoder emits for a character it could not read


def extract_pdf(content: bytes, *, source_id: str) -> ParsedDocument:
    """Read a PDF into page-tagged blocks. Raises ``ExtractionError`` if it cannot be read."""
    try:
        pdf = pdfium.PdfDocument(content)
    except pdfium.PdfiumError as error:
        if "password" in str(error).lower():
            raise ExtractionError(
                "The PDF is password-protected.", code="password_protected"
            ) from error
        raise ExtractionError(
            "The file is not a readable PDF.", code="corrupted_document"
        ) from error

    try:
        if len(pdf) > MAX_PAGES:
            raise ExtractionError(
                f"The PDF has {len(pdf)} pages; the limit is {MAX_PAGES}.", code="too_many_pages"
            )
        texts: list[str] = []
        scanned: list[bool] = []
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                text = _page_text(page)
                texts.append(text)
                scanned.append(bool(text) and _invisible_text_share(page) >= OCR_INVISIBLE_SHARE)
            finally:
                page.close()
        document_date = _metadata_date(pdf.get_metadata_dict())
    finally:
        pdf.close()

    undecodable = sum(text.count(_REPLACEMENT) for text in texts)
    pages = [
        PageInfo(number=number, chars=len(text), ocr_layer=ocr)
        for number, (text, ocr) in enumerate(zip(texts, scanned, strict=True), start=1)
    ]
    blocks: list[Block] = []
    for number, (text, ocr) in enumerate(
        zip(strip_running_lines(texts), scanned, strict=True), start=1
    ):
        blocks.extend(lines_to_blocks(text, page=number, ocr=ocr))

    return ParsedDocument(
        source_id=source_id,
        format="pdf",
        blocks=blocks,
        pages=pages,
        document_date=document_date,
        date_source="pdf-metadata" if document_date else None,
        warnings=_warnings(pages, undecodable),
        extractor=f"pypdfium2 {version('pypdfium2')}",
    )


def strip_running_lines(pages: list[str]) -> list[str]:
    """Remove page headers, footers and page numbers repeated on the pages of a document.

    A line that opens or closes at least half of the pages (and at least three) is a running
    header or footer. A repeated header is kept once, on the first page where it appears, since
    it may be the document's title; repeated footers and page numbers are dropped everywhere.
    """
    if len(pages) < _RUNNING_MIN_PAGES:
        return pages
    split = [[collapse_spaces(line) for line in page.split("\n")] for page in pages]
    counts = Counter(line for lines in split for line in _edges(lines))
    threshold = max(_RUNNING_MIN_PAGES, len(pages) / 2)
    running = {line for line, count in counts.items() if count >= threshold and len(line) <= 120}

    seen: set[str] = set()
    cleaned: list[str] = []
    for lines in split:
        filled = [line for line in lines if line]
        top, bottom = (filled[0], filled[-1]) if filled else ("", "")
        kept: list[str] = []
        for line in lines:
            if (
                line
                and line == bottom
                and line != top
                and (line in running or _PAGE_NUMBER.match(line))
            ):
                continue  # a footer or a page number
            if line and line == top:
                if _PAGE_NUMBER.match(line):
                    continue
                if line in running:
                    if line in seen:
                        continue
                    seen.add(line)
            kept.append(line)
        cleaned.append("\n".join(kept))
    return cleaned


def _edges(lines: list[str]) -> set[str]:
    """The first and last non-empty lines of a page."""
    filled = [line for line in lines if line]
    return {filled[0], filled[-1]} if filled else set()


def _page_text(page: pdfium.PdfPage) -> str:
    textpage = page.get_textpage()
    try:
        raw = textpage.get_text_range()
    finally:
        textpage.close()
    text = normalize_text(raw).replace(_HYPHEN_BREAK, "-")
    return "\n".join(_LEADING_BULLET.sub("• ", line) for line in text.split("\n"))


def _invisible_text_share(page: pdfium.PdfPage) -> float:
    total = invisible = 0
    for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_TEXT], max_depth=3):
        total += 1
        if (
            pdfium_c.FPDFTextObj_GetTextRenderMode(obj.raw)
            == pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE
        ):
            invisible += 1
    return invisible / total if total else 0.0


def _metadata_date(metadata: dict[str, str]) -> date | None:
    """The later of the creation and modification dates in the PDF's own metadata."""
    found: list[date] = []
    for key in ("CreationDate", "ModDate"):
        match = _PDF_DATE.match(metadata.get(key, ""))
        if match:
            try:
                found.append(
                    date(
                        int(match["year"]),
                        int(match["month"] or 1),
                        int(match["day"] or 1),
                    )
                )
            except ValueError:
                continue  # a nonsense date in the metadata
    return max(found) if found else None


def _warnings(pages: list[PageInfo], undecodable: int) -> list[str]:
    warnings: list[str] = []
    scanned = [page.number for page in pages if page.ocr_layer]
    if scanned:
        listed = ", ".join(map(str, scanned))
        warnings.append(
            f"Pages {listed} are scans with an OCR text layer. OCR can misread digits and "
            "letters: verify figures and dates against the original."
        )
    if undecodable:
        warnings.append(
            f"{undecodable} characters could not be decoded (shown as U+FFFD); "
            "some text may be missing or wrong."
        )
    return warnings
