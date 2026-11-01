import pytest

from app.services.grounding.numbers import figures, links, unsupported


class TestNumbers:
    @pytest.mark.parametrize(
        "text",
        [
            "Rs.2,50,000/- per annum",
            "Rs. 2.5 lakh",
            "2.5 lakhs",
            "Rs 250000",
            "250,000",
            "২,৫০,০০০ টাকা",
            "२,५०,००० रुपये",
            "2.5 लाख",
        ],
    )
    def test_one_amount_however_it_is_written(self, text: str) -> None:
        assert figures(text).numbers == {"250000"}

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1 crore", {"10000000"}),
            ("1,00,00,000", {"10000000"}),
            ("10,00,000", {"1000000"}),
            ("1,000,000", {"1000000"}),
            ("5 lakhs", {"500000"}),
            ("25 thousand", {"25000"}),
            ("60%", {"60"}),
            ("60 per cent", {"60"}),
            ("2.50", {"2.5"}),
            ("7.5 CGPA", {"7.5"}),
            ("classes 9, 10 and 11", {"9", "10", "11"}),
            ("classes 9,10", {"9", "10"}),  # not a thousands separator
            ("30th", {"30"}),
            ("011-29581118", {"11", "29581118"}),
            ("lakh and crore", set()),  # a multiplier alone is not a figure
            ("no figures here", set()),
        ],
    )
    def test_how_figures_are_read(self, text: str, expected: set[str]) -> None:
        assert figures(text).numbers == expected

    def test_a_different_amount_is_a_different_figure(self) -> None:
        assert figures("Rs.2,50,000").numbers != figures("Rs.25,000").numbers


class TestDates:
    @pytest.mark.parametrize(
        "text", ["30.11.2026", "30/11/2026", "30-11-2026", "30/11/26", "30 November 2026"]
    )
    def test_the_same_date_in_the_usual_formats(self, text: str) -> None:
        found = figures(text)

        assert found.numbers == {"30", "2026"}
        assert found.months == {11}

    def test_an_iso_date(self) -> None:
        found = figures("2026-06-01")

        assert (found.numbers, found.months) == ({"1", "2026"}, {6})

    def test_a_day_with_an_ordinal_and_a_comma(self) -> None:
        found = figures("the 30th of November, 2026")

        assert (found.numbers, found.months) == ({"30", "2026"}, {11})

    def test_an_academic_session(self) -> None:
        assert figures("2025-26").numbers == {"2025", "2026"}
        assert figures("2025-2026").numbers == {"2025", "2026"}
        assert figures("2025\N{EN DASH}26").numbers == {"2025", "2026"}

    def test_a_date_made_of_numbers_that_cannot_be_a_month_is_left_as_numbers(self) -> None:
        found = figures("12.34.2026")

        assert found.months == set()
        assert {"2026"} <= found.numbers

    @pytest.mark.parametrize(
        ("text", "months"),
        [
            ("November", {11}),
            ("by the end of December", {12}),
            ("30 Nov 2026", {11}),
            ("Nov", set()),  # an abbreviation counts only beside a day or year
            ("30 May 2026", {5}),
            ("MAY 2026", {5}),
            ("30 of May", {5}),
            ("students of class 12 may apply", set()),  # the verb, not the month
            ("candidates may apply", set()),
            ("applications open in March", {3}),
            ("the mayor decided", set()),  # "mayor" is not "may"
            ("৩০ নভেম্বর ২০২৬", {11}),
            ("ডিসেম্বর মাসে", {12}),
            ("30 नवंबर 2026", {11}),
            ("३० मई", {5}),
            ("मई", set()),
            ("মেয়েদের জন্য", set()),  # Bengali "for girls" starts like the month "মে"
            ("৩০ মে", {5}),
        ],
    )
    def test_months_named_in_words(self, text: str, months: set[int]) -> None:
        assert figures(text).months == months


class TestLinks:
    def test_the_same_address_written_differently_is_one_address(self) -> None:
        assert (
            links("https://www.nsp.gov.in/")
            == links("nsp.gov.in")
            == links("see http://nsp.gov.in, then")
        )

    def test_an_address_is_reduced_to_what_identifies_it(self) -> None:
        assert links("https://scholarships.gov.in/Fresh/") == {"scholarshipsgovinfresh"}

    def test_email_addresses_are_addresses(self) -> None:
        assert links("write to helpdesk@nsp.gov.in.") == {"helpdesknspgovin"}

    def test_a_full_stop_ending_a_sentence_is_not_part_of_the_address(self) -> None:
        assert links("Visit nsp.gov.in.") == links("Visit nsp.gov.in")

    @pytest.mark.parametrize("text", ["e.g. this", "i.e. that", "Rs.2 only", "No. 5 applies"])
    def test_ordinary_text_has_no_address(self, text: str) -> None:
        assert links(text) == frozenset()


class TestUnsupported:
    QUOTE = "family income has been fixed at Rs.2,50,000/- per annum"

    def test_a_statement_with_the_quoted_figures_holds_up(self) -> None:
        assert unsupported("Income must be below Rs 2,50,000 a year.", [self.QUOTE]) == []

    def test_the_same_amount_in_other_words_holds_up(self) -> None:
        assert unsupported("The limit is 2.5 lakh rupees.", [self.QUOTE]) == []

    def test_a_bengali_statement_with_bengali_digits_holds_up(self) -> None:
        statement = "পারিবারিক আয় বছরে ২,৫০,০০০ টাকার বেশি হতে পারবে না।"

        assert unsupported(statement, [self.QUOTE]) == []

    def test_a_different_amount_does_not(self) -> None:
        assert unsupported("Income must be below Rs 3,00,000.", [self.QUOTE]) == ["number"]

    def test_an_extra_figure_does_not(self) -> None:
        assert unsupported("Income below Rs 2,50,000 and 60% marks.", [self.QUOTE]) == ["number"]

    def test_a_statement_with_no_figures_holds_up(self) -> None:
        assert unsupported("Your family income must stay under the ceiling.", [self.QUOTE]) == []

    def test_a_wrong_month_does_not_even_if_the_day_and_year_match(self) -> None:
        quote = "must apply before 30.11.2026"

        assert unsupported("The last date is 30 December 2026.", [quote]) == ["month"]
        assert unsupported("The last date is 30 November 2026.", [quote]) == []

    def test_an_address_the_quote_lacks_does_not(self) -> None:
        quote = "write to helpdesk@nsp.gov.in for any query"

        assert unsupported("Write to help@nsp.gov.in.", [quote]) == ["link"]
        assert unsupported("Write to helpdesk@nsp.gov.in.", [quote]) == []

    def test_figures_may_be_spread_over_several_quotes(self) -> None:
        quotes = ["income at Rs.2,50,000/- per annum", "apply before 30.11.2026"]

        assert unsupported("Income up to Rs 2,50,000; apply by 30 November 2026.", quotes) == []

    def test_every_kind_of_problem_is_reported(self) -> None:
        quote = "apply before 30.11.2026 at nsp.gov.in"

        found = unsupported("Apply by 5 December 2027 at other.gov.in.", [quote])

        assert found == ["number", "month", "link"]

    def test_no_quotes_support_no_figures(self) -> None:
        assert unsupported("It costs Rs 500.", []) == ["number"]
