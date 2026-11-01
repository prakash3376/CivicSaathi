from app.services.grounding.text import (
    MIN_QUOTE_CHARS,
    find_in_any,
    find_quote,
    is_long_enough,
    squash,
)

PASSAGE = (
    "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum.\n"
    "Applicants must be residents of the State and must apply online before the last date."
)


def words(quote: str, passage: str = PASSAGE) -> str | None:
    """The passage's own words for a quote, or None if the quote is not in the passage."""
    located = find_quote(quote, squash(passage))
    return None if located is None else located.words(passage)


class TestSquash:
    def test_keeps_letters_and_digits_only_in_lower_case(self) -> None:
        assert squash("Rs.2,50,000/- (Per Annum)").chars == "rs250000perannum"

    def test_every_kept_character_knows_where_it_came_from(self) -> None:
        text = "A-b  C"

        squashed = squash(text)

        assert squashed.chars == "abc"
        assert [text[i] for i in squashed.origin] == ["A", "b", "C"]

    def test_digits_of_any_script_become_ascii_digits(self) -> None:
        assert squash("৩০ ३० 30").chars == "303030"

    def test_vowel_signs_are_kept_so_different_words_stay_different(self) -> None:
        assert squash("কি").chars != squash("কী").chars  # Bengali: "what" and "who"

    def test_invisible_characters_are_ignored(self) -> None:
        assert squash("in\N{ZERO WIDTH SPACE}come\N{SOFT HYPHEN}").chars == "income"

    def test_an_expanding_character_points_at_the_one_it_came_from(self) -> None:
        text = "e\N{LATIN SMALL LIGATURE FI}x"

        squashed = squash(text)

        assert squashed.chars == "efix"
        assert squashed.origin == (0, 1, 1, 2)


class TestFindQuote:
    def test_an_exact_quote_is_found(self) -> None:
        quote = "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum"

        assert words(quote + ".") == quote  # a closing full stop is not part of the match

    def test_the_passage_is_returned_in_its_own_words_not_the_models(self) -> None:
        assert words("family income has been fixed at Rs 2,50,000 per annum") == (
            "family income has been fixed at Rs.2,50,000/- per annum"
        )

    def test_case_punctuation_and_line_breaks_do_not_matter(self) -> None:
        assert words("APPLICANTS MUST be residents of the state, and must apply online") == (
            "Applicants must be residents of the State and must apply online"
        )
        assert words("per annum. Applicants must be residents") == (
            "per annum.\nApplicants must be residents"
        )

    def test_a_word_broken_at_the_end_of_a_line_is_found(self) -> None:
        passage = "Marks in the last qualify-\ning examination will be counted."

        assert words("marks in the last qualifying examination", passage) == (
            "Marks in the last qualify-\ning examination"
        )

    def test_straight_and_curly_apostrophes_are_the_same(self) -> None:
        passage = "The student\N{RIGHT SINGLE QUOTATION MARK}s family must live in the State."

        assert words("The student's family must live in the State", passage) is not None

    def test_a_different_word_is_not_found(self) -> None:
        assert words("family income has been fixed at Rs.2,50,000/- per month") is None

    def test_a_different_figure_is_not_found(self) -> None:
        assert words("family income has been fixed at Rs.3,50,000/- per annum") is None

    def test_a_quote_that_is_not_in_the_passage_at_all_is_not_found(self) -> None:
        assert words("Every girl student receives the scholarship automatically") is None

    def test_a_quote_must_have_enough_letters_to_mean_something(self) -> None:
        passage = "abcdefghijklmnopqrstuvwxyz"

        assert words("abcdefghijklmn", passage) is None  # one short of the minimum
        assert words("abcdefghijklmno", passage) == "abcdefghijklmno"
        assert MIN_QUOTE_CHARS == 15

    def test_an_empty_quote_is_not_found(self) -> None:
        assert words("") is None
        assert words("   ...   ") is None

    def test_digits_match_across_scripts(self) -> None:
        passage = "বার্ষিক পারিবারিক আয়ের সীমা ২,৫০,০০০ টাকা"

        assert words("বার্ষিক পারিবারিক আয়ের সীমা 2,50,000 টাকা", passage) == passage

    def test_a_vowel_sign_makes_a_different_quote(self) -> None:
        passage = "আবেদনকারী কি এই বৃত্তির জন্য যোগ্য"

        assert words("আবেদনকারী কী এই বৃত্তির জন্য যোগ্য", passage) is None

    def test_invisible_characters_in_the_passage_do_not_break_a_match(self) -> None:
        passage = "family in\N{ZERO WIDTH SPACE}come must be below the ceiling"

        assert words("family income must be below the ceiling", passage) is not None

    def test_the_first_occurrence_is_used(self) -> None:
        passage = "income ceiling applies here. income ceiling applies here."

        located = find_quote("income ceiling applies here", squash(passage))

        assert located is not None
        assert located.spans == ((0, 27),)

    def test_spans_are_positions_in_the_original_text(self) -> None:
        located = find_quote("family income has been fixed", squash(PASSAGE))

        assert located is not None
        [(start, end)] = located.spans
        assert PASSAGE[start:end] == "family income has been fixed"


class TestIsLongEnough:
    def test_it_counts_letters_and_digits_only(self) -> None:
        assert is_long_enough("a b-c.d,e f g h i j k l m n o")  # fifteen, with noise between
        assert not is_long_enough("a b-c.d,e f g h i j k l m n")  # fourteen

    def test_omissions_add_nothing(self) -> None:
        assert not is_long_enough("abcdefgh ... ijklmn")  # fourteen either side of the dots

    def test_it_agrees_with_what_find_quote_will_accept(self) -> None:
        for quote in (
            "Rs.2,50,000",
            "per annum",
            "income has been fixed at Rs.2,50,000/- per annum",
        ):
            assert is_long_enough(quote) == (find_quote(quote, squash(PASSAGE)) is not None), quote


class TestOmissions:
    def test_the_parts_around_an_ellipsis_are_found_separately(self) -> None:
        quote = "The upper ceiling for family income ... per annum."

        assert (
            words(quote) == "The upper ceiling for family income \N{HORIZONTAL ELLIPSIS} per annum"
        )

    def test_three_dots_and_the_ellipsis_character_and_brackets_all_mean_an_omission(self) -> None:
        for mark in ("...", "\N{HORIZONTAL ELLIPSIS}", "[...]", "[\N{HORIZONTAL ELLIPSIS}]"):
            quote = f"The upper ceiling for family income {mark} per annum"

            assert words(quote) is not None, mark

    def test_the_parts_may_come_in_any_order(self) -> None:
        quote = "per annum ... The upper ceiling for family income"

        assert words(quote) is not None

    def test_one_missing_part_fails_the_whole_quote(self) -> None:
        quote = "The upper ceiling for family income ... and girls get double"

        assert words(quote) is None

    def test_parts_that_touch_are_one_highlight(self) -> None:
        located = find_quote("The upper ceiling ... ceiling for family income", squash(PASSAGE))

        assert located is not None
        assert len(located.spans) == 1


class TestFindInAny:
    def test_returns_the_first_passage_holding_the_quote(self) -> None:
        passages = [squash("nothing relevant here at all"), squash(PASSAGE), squash(PASSAGE)]

        found = find_in_any("family income has been fixed at Rs.2,50,000/- per annum", passages)

        assert found is not None
        assert found[0] == 1

    def test_returns_none_when_no_passage_has_it(self) -> None:
        assert find_in_any("this sentence is nowhere to be seen", [squash(PASSAGE)]) is None
