"""Builds small, valid PDFs for tests, so extraction is tested without any binary fixtures."""

from collections.abc import Sequence


def _escape(text: str) -> bytes:
    # WinAnsiEncoding is Windows-1252: it has the bullet and en dash that real documents use.
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("cp1252")


def make_pdf(
    pages: Sequence[Sequence[str]],
    *,
    creation_date: str | None = None,
    invisible_text: bool = False,
) -> bytes:
    """A PDF with one page per list of text lines, set in Helvetica.

    ``invisible_text`` uses text render mode 3, which is how scanners hide an OCR layer behind
    the page image. ``creation_date`` is a PDF date such as ``"D:20260301000000"``.
    """
    page_count = len(pages)
    first_page = 5  # object 4 is the optional Info dictionary
    page_numbers = [first_page + 2 * index for index in range(page_count)]
    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    info = b"<< /Creator (tests)"
    if creation_date:
        info += b" /CreationDate (" + creation_date.encode() + b")"
    objects[4] = info + b" >>"

    for page_number, lines in zip(page_numbers, pages, strict=True):
        content_number = page_number + 1
        operations = [b"BT", b"/F1 11 Tf", b"14 TL", b"56 780 Td"]
        if invisible_text:
            operations.append(b"3 Tr")
        operations += [b"(" + _escape(line) + b") Tj T*" for line in lines]
        operations.append(b"ET")
        stream = b"\n".join(operations)
        objects[page_number] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_number} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>"
        ).encode()
        objects[content_number] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(output)
        output += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"

    size = max(objects) + 1
    xref_start = len(output)
    output += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for number in range(1, size):
        output += f"{offsets[number]:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {size} /Root 1 0 R /Info 4 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return bytes(output)
