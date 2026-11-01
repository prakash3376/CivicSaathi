from datetime import date

import pytest

from app.domain.errors import ExtractionError
from app.services.ingestion.extraction.html import extract_html


def blocks(html: str, **kwargs: str | None) -> list[tuple[str, str]]:
    doc = extract_html(html.encode("utf-8"), source_id="demo", **kwargs)
    return [(block.kind, block.text) for block in doc.blocks]


PAGE = """<!doctype html><html lang="en"><head><title>Menu :: portal</title>
<style>p { color: red }</style><script>var tracking = 1;</script></head><body>
<nav><ul><li>Home</li><li>About us</li></ul></nav>
<header>Site header</header>
<article>
  <h1>Pragati Scholarship</h1>
  <p>Scholarship for girls in <b>technical</b> education,<br>implemented by AICTE.</p>
  <h2>Eligibility</h2>
  <ul><li>Family income below Rs. 8 Lakh<ul><li>per annum</li></ul></li><li>Only girls</li></ul>
</article>
<footer>Copyright notice</footer></body></html>"""


class TestContent:
    def test_keeps_the_main_content_and_drops_the_page_furniture(self) -> None:
        result = blocks(PAGE)

        assert result == [
            ("heading", "Pragati Scholarship"),
            ("paragraph", "Scholarship for girls in technical education,"),
            ("paragraph", "implemented by AICTE."),
            ("heading", "Eligibility"),
            ("list_item", "Family income below Rs. 8 Lakh"),
            ("list_item", "per annum"),
            ("list_item", "Only girls"),
        ]

    def test_headings_carry_their_depth(self) -> None:
        doc = extract_html(PAGE.encode(), source_id="demo")

        assert [(b.text, b.level) for b in doc.blocks if b.kind == "heading"] == [
            ("Pragati Scholarship", 1),
            ("Eligibility", 2),
        ]

    def test_a_selector_pins_the_content_when_the_page_has_no_landmarks(self) -> None:
        html = (
            "<body><div class='menu'>Menu items</div>"
            "<div class='about_main'><p>The real content.</p></div></body>"
        )

        assert blocks(html, selector="div.about_main") == [("paragraph", "The real content.")]

    def test_warns_when_it_has_to_guess_where_the_content_is(self) -> None:
        doc = extract_html(b"<body><div><p>Some text.</p></div></body>", source_id="demo")

        assert any("main-content" in warning for warning in doc.warnings)

    def test_does_not_warn_when_the_page_has_a_main_landmark(self) -> None:
        doc = extract_html(b"<body><main><p>Some text.</p></main></body>", source_id="demo")

        assert doc.warnings == []

    def test_a_selector_that_matches_nothing_is_an_error(self) -> None:
        with pytest.raises(ExtractionError) as error:
            extract_html(b"<body><p>text</p></body>", source_id="demo", selector="div.gone")

        assert error.value.code == "selector_not_found"


ASPNET_PAGE = """<html><body><form method="post" id="form1">
<div><h1>Annapurna Scheme</h1>
<p>The scheme gives monthly help to every eligible woman of the State, as the department decides.</p>
<h2>Who can apply</h2><p>Women who live in the State and are enrolled in the scheme's portal.</p></div>
<form action="/search"><input name="q"><button>Search</button>Search the site</form>
</form></body></html>"""


class TestAPageWrappedInAForm:
    def test_the_content_of_a_form_that_is_the_whole_page_is_read(self) -> None:
        result = blocks(ASPNET_PAGE)

        assert ("heading", "Annapurna Scheme") in result
        assert any("monthly help to every eligible woman" in text for _, text in result)

    def test_a_small_form_inside_it_is_still_dropped(self) -> None:
        assert not any("Search the site" in text for _, text in blocks(ASPNET_PAGE))

    def test_it_says_that_it_did_this(self) -> None:
        doc = extract_html(ASPNET_PAGE.encode("utf-8"), source_id="demo")

        assert any("<form>" in warning for warning in doc.warnings)

    def test_a_search_form_beside_the_content_is_dropped_and_nothing_is_said(self) -> None:
        page = (
            "<html><body><form action='/s'>Find a page in this site</form>"
            "<main><h1>Title of the page</h1>" + "<p>Content of the page. </p>" * 20 + "</main>"
            "</body></html>"
        )
        doc = extract_html(page.encode("utf-8"), source_id="demo")

        assert not any("Find a page" in block.text for block in doc.blocks)
        assert not any("<form>" in warning for warning in doc.warnings)


class TestOddMarkup:
    def test_a_heading_tag_used_for_body_text_becomes_a_paragraph(self) -> None:
        html = (
            "<main><h2>This is really a long sentence that an old site styled as a heading and "
            "it ends with a full stop.</h2>"
            "<h4>The basic allocation and rates will be as under :</h4>"
            "<h6>For HS - level:</h6></main>"
        )

        kinds = [kind for kind, _ in blocks(html)]

        assert kinds == ["paragraph", "paragraph", "heading"]

    def test_carriage_returns_in_the_source_are_not_line_breaks(self) -> None:
        html = "<main><p>The financial assistance will be admissible\r\n to those candidates.</p></main>"

        assert blocks(html) == [
            ("paragraph", "The financial assistance will be admissible to those candidates.")
        ]

    def test_loose_text_and_inline_tags_form_a_paragraph(self) -> None:
        html = "<main><div>Rs.<b>2,50,000</b>/- per <i>annum</i><br>Second line</div></main>"

        assert blocks(html) == [
            ("paragraph", "Rs.2,50,000/- per annum"),
            ("paragraph", "Second line"),
        ]

    def test_repeated_long_blocks_are_kept_once(self) -> None:
        repeated = "<p>This paragraph appears twice on the page and should be kept only once.</p>"

        assert len(blocks(f"<main>{repeated}<p>Other.</p>{repeated}</main>")) == 2

    def test_keeps_indian_language_text(self) -> None:
        assert blocks("<main><p>छात्रवृत्ति योजना</p></main>") == [("paragraph", "छात्रवृत्ति योजना")]


class TestTables:
    def test_each_row_is_labelled_with_its_column_headers(self) -> None:
        html = (
            "<main><table>"
            "<tr><th>Course</th><th>Rate per month</th></tr>"
            "<tr><td>UG (ARTS)</td><td>1000/-</td></tr>"
            "<tr><td>UG (SCIENCE)</td><td>1500/-</td></tr>"
            "</table></main>"
        )

        assert blocks(html) == [
            (
                "table",
                "Course: UG (ARTS); Rate per month: 1000/-\n"
                "Course: UG (SCIENCE); Rate per month: 1500/-",
            )
        ]

    def test_a_cell_that_spans_rows_is_repeated_on_each_row(self) -> None:
        html = (
            "<main><table>"
            "<tr><th>Directorate</th><th>Course</th><th>Rate</th></tr>"
            "<tr><td rowspan='2'>DPI</td><td>UG (ARTS)</td><td>1000/-</td></tr>"
            "<tr><td>UG (SCIENCE)</td><td>1500/-</td></tr>"
            "</table></main>"
        )

        [(_, text)] = blocks(html)

        assert text.splitlines() == [
            "Directorate: DPI; Course: UG (ARTS); Rate: 1000/-",
            "Directorate: DPI; Course: UG (SCIENCE); Rate: 1500/-",
        ]

    def test_a_table_nested_in_a_table_is_read_once(self) -> None:
        html = (
            "<main><table><tr><td>"
            "<table><tr><th>Course</th><th>Rate</th></tr><tr><td>PG (ARTS)</td><td>2000/-</td></tr></table>"
            "</td></tr></table></main>"
        )

        result = blocks(html)

        assert result == [("table", "Course: PG (ARTS); Rate: 2000/-")]

    def test_a_table_without_headers_uses_bars_and_merges_spanning_cells(self) -> None:
        html = "<main><table><tr><td colspan='2'>Notes</td><td>apply</td></tr></table></main>"

        assert blocks(html) == [("table", "Notes | apply")]


class TestDate:
    def test_takes_the_date_from_the_last_modified_header(self) -> None:
        doc = extract_html(
            b"<main><p>Text.</p></main>",
            source_id="demo",
            last_modified="Wed, 21 Oct 2026 07:28:00 GMT",
        )

        assert doc.document_date == date(2026, 10, 21)
        assert doc.date_source == "http-last-modified"

    @pytest.mark.parametrize("header", [None, "", "not a date"])
    def test_has_no_date_without_a_usable_header(self, header: str | None) -> None:
        doc = extract_html(b"<main><p>Text.</p></main>", source_id="demo", last_modified=header)

        assert doc.document_date is None
