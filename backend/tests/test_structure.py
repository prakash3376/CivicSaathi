import pytest

from app.services.segmentation.structure import (
    clause_label,
    heading_depth,
    lines_to_blocks,
    list_marker,
)


class TestClauseLabel:
    @pytest.mark.parametrize(
        ("text", "label"),
        [
            ("1. Up to Two Girls per family.", "1"),
            ("2) Family income should be less than Rs. 8 Lakh", "2"),
            ("2.1 Scope of the scheme", "2.1"),
            ("3.1.2. Amount of the award", "3.1.2"),
            ("(a) first condition", "(a)"),
            ("(iv) fourth condition", "(iv)"),
            ("Q.3 How can I apply?", "Q.3"),
            ("Q. 19 What are the reasons of rejection?", "Q.19"),
        ],
    )
    def test_finds_the_clause_number(self, text: str, label: str) -> None:
        assert clause_label(text) == label

    @pytest.mark.parametrize(
        "text",
        [
            "8 Lakh per annum.",  # a wrapped line that happens to start with a number
            "2.5 lakh per year",  # a decimal, not a clause
            "19.06.2026 Date of issue",
            "Rs. 8 Lakh",
            "The scheme benefits students.",
        ],
    )
    def test_ignores_numbers_that_are_not_clauses(self, text: str) -> None:
        assert clause_label(text) == ""

    def test_a_bullet_is_a_list_item_without_a_clause_number(self) -> None:
        assert list_marker("• Copy of the HSC certificate.") == ""
        assert list_marker("Plain sentence.") is None


class TestHeadingDepth:
    @pytest.mark.parametrize(
        "line",
        [
            "SVMCMS GUIDELINES",
            "ALLOCATION AND RATE OF SCHOLARSHIP",
            "MEANS JUDGING CRITERIA",
            "ANNEXURE-I",
            "Annexure II",
            "Chapter 3",
            "अध्याय 2",
            "Q.1 Who is eligible for PRAGATI Scholarship?",
            "2. Eligibility",
            "3.1 Scope of the scheme",
        ],
    )
    def test_recognises_headings(self, line: str) -> None:
        assert heading_depth(line) is not None

    @pytest.mark.parametrize(
        "line",
        [
            "UG (SCIENCE)",  # a table cell in capitals
            "COURSES, UGC",
            "UG (MEDICAL-DEGREE) AND",  # ends on a connecting word: the line continues
            "NSP",
            "DPI",
            "SCHOLARSHIP RATE PER MONTH 1000/-",
            "2. Family income should be less than Rs. 8 Lakh",  # a wrapped list item
            "3. Students admitted in UG Degree Level",
            "The scheme benefits students.",
            "",
        ],
    )
    def test_does_not_mistake_other_lines_for_headings(self, line: str) -> None:
        assert heading_depth(line) is None

    def test_numbered_headings_are_nested_by_their_number(self) -> None:
        assert heading_depth("2. Eligibility") == 1
        assert heading_depth("2.1 Scope of the scheme") == 2

    def test_questions_are_second_level_headings(self) -> None:
        assert heading_depth("Q.7 Eligibility when a candidate drops out?") == 2


class TestLinesToBlocks:
    def test_joins_the_lines_of_a_wrapped_paragraph(self) -> None:
        text = (
            "The upper ceiling for family income has been fixed at\n"
            "Rs.2,50,000/- per annum.\n"
            "There will be no need to submit hard copy."
        )

        blocks = lines_to_blocks(text, page=3)

        assert [block.text for block in blocks] == [
            "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum.",
            "There will be no need to submit hard copy.",
        ]
        assert {block.page for block in blocks} == {3}

    def test_separates_list_items_and_keeps_wrapped_ones_whole(self) -> None:
        text = (
            "Ans: Eligibility criteria under the scheme:\n"
            "1. Up to two girls per family.\n"
            "2. Family income should be less than Rs. 8\n"
            "Lakh per annum.\n"
            "(a) first condition\n"
            "• a bullet"
        )

        blocks = lines_to_blocks(text, page=1)

        assert [(block.kind, block.text) for block in blocks] == [
            ("paragraph", "Ans: Eligibility criteria under the scheme:"),
            ("list_item", "1. Up to two girls per family."),
            ("list_item", "2. Family income should be less than Rs. 8 Lakh per annum."),
            ("list_item", "(a) first condition"),
            ("list_item", "• a bullet"),
        ]

    def test_table_cells_in_capitals_do_not_become_headings(self) -> None:
        text = (
            "ALLOCATION AND RATE OF SCHOLARSHIP\n"
            "UG (SCIENCE)\n"
            "At least 60% marks in Last Qualifying Exam 1500/-\n"
            "COURSES, UGC\n"
            "APPROVED) At least 60% marks 1500/-"
        )

        kinds = [block.kind for block in lines_to_blocks(text, page=2)]

        assert kinds.count("heading") == 1

    def test_drops_page_numbers_written_as_noise(self) -> None:
        text = "First paragraph of the page.\nPage 2 of 7\n- 3 -\nSecond line of the page."

        assert [block.text for block in lines_to_blocks(text, page=2)] == [
            "First paragraph of the page. Second line of the page."
        ]

    def test_merges_an_all_caps_heading_that_wrapped(self) -> None:
        text = (
            "This paragraph is long enough to show how wide a full line of text is on this page.\n"
            "DIRECTIONS FOR RENEWAL OF SVMCM SCHOLARSHIP OF GENERAL DEGREE/POST\n"
            "GRADUATE DEGREE STUDENTS UNDER DIRECTORATE OF PUBLIC INSTRUCTIONS:\n"
            "1st renewal: Submission of SEM 1 marksheet required."
        )

        blocks = lines_to_blocks(text, page=6)

        headings = [block for block in blocks if block.kind == "heading"]
        assert len(headings) == 1
        assert headings[0].text.startswith("DIRECTIONS FOR RENEWAL")
        assert headings[0].text.endswith("PUBLIC INSTRUCTIONS:")

    def test_two_short_headings_in_a_row_stay_separate(self) -> None:
        text = (
            "A line that is wide enough to set the typical width of this page of the document.\n"
            "MEANS JUDGING CRITERIA\n"
            "MERIT JUDGING CRITERIA\n"
            "Candidates are judged by marks."
        )

        headings = [b.text for b in lines_to_blocks(text, page=4) if b.kind == "heading"]

        assert headings == ["MEANS JUDGING CRITERIA", "MERIT JUDGING CRITERIA"]

    def test_a_wrapped_question_is_kept_whole_up_to_its_question_mark(self) -> None:
        text = (
            "Q.5 I am Degree/Diploma student and recipient of one of the merit scholarships of\n"
            "Centre / State Government. Am I eligible?\n"
            "Ans: No."
        )

        blocks = lines_to_blocks(text, page=1)

        assert blocks[0].kind == "heading"
        assert blocks[0].text.endswith("Am I eligible?")
        assert [block.text for block in blocks[1:]] == ["Ans: No."]

    def test_a_question_without_a_question_mark_does_not_swallow_its_answer(self) -> None:
        text = (
            "Q.17 Whom to contact after submission of online scholarship application\n"
            "Ans: After submission students should check all the credentials."
        )

        blocks = lines_to_blocks(text, page=2)

        assert (
            blocks[0].text
            == "Q.17 Whom to contact after submission of online scholarship application"
        )
        assert blocks[1].text.startswith("Ans:")

    def test_keeps_a_trailing_hyphen_when_joining_wrapped_lines(self) -> None:
        text = "The scheme is valid for 2021-\n22 and later years."

        assert (
            lines_to_blocks(text, page=1)[0].text
            == "The scheme is valid for 2021-22 and later years."
        )

    def test_marks_blocks_from_a_scan(self) -> None:
        blocks = lines_to_blocks("Some scanned text of a notice.", page=1, ocr=True)

        assert blocks[0].ocr is True
