from app.domain.assistant import Draft, DraftClaim, Evidence, Passage
from app.services.grounding.verify import (
    MAX_CLAIMS,
    MAX_STATEMENT_CHARS,
    clean_statement,
    verify,
)

INCOME = "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum."
RESIDENT = "Applicants must be residents of the State."
DEADLINE = "Applications must be submitted online before 30.11.2026."
HELPDESK = "For any query write to helpdesk@nsp.gov.in."


def passage(ref: str, text: str) -> Passage:
    return Passage(
        ref=ref,
        chunk_id=f"chunk-{ref}",
        source_id="demo-guidelines",
        title="Demo Scholarship: Guidelines",
        url="https://scholarships.example.gov.in/guidelines.pdf",
        text=text,
    )


PASSAGES = [passage("S1", f"{INCOME} {RESIDENT}"), passage("S2", f"{DEADLINE} {HELPDESK}")]


def claim(statement: str, source: str = "S1", quote: str = INCOME) -> DraftClaim:
    return DraftClaim(statement=statement, evidence=[Evidence(source=source, quote=quote)])


def draft(*claims: DraftClaim) -> Draft:
    return Draft(answerable=True, claims=list(claims))


def reasons(result_draft: Draft) -> list[tuple[str, ...]]:
    return [item.reasons for item in verify(result_draft, PASSAGES).rejections]


class TestAcceptedClaims:
    def test_a_claim_with_a_real_quote_and_matching_figures_is_kept(self) -> None:
        result = verify(draft(claim("Family income must be at most Rs 2,50,000 a year.")), PASSAGES)

        assert result.clean
        [kept] = result.claims
        assert kept.statement == "Family income must be at most Rs 2,50,000 a year."
        [support] = kept.support
        assert support.passage.ref == "S1"
        assert support.quote == INCOME.rstrip(".")  # the document's own words

    def test_a_statement_without_figures_needs_only_a_real_quote(self) -> None:
        result = verify(
            draft(claim("Applicants have to live in the State.", quote=RESIDENT)), PASSAGES
        )

        assert result.clean

    def test_the_source_may_be_written_in_any_common_way(self) -> None:
        for source in ("S1", "s1", "[S1]", "Source 1", "S01"):
            assert verify(draft(claim("Income is capped.", source=source)), PASSAGES).clean, source

    def test_a_quote_in_another_passage_is_attributed_to_the_passage_it_is_in(self) -> None:
        wrongly_labelled = claim("The last date is 30 November 2026.", source="S1", quote=DEADLINE)

        [kept] = verify(draft(wrongly_labelled), PASSAGES).claims

        assert kept.support[0].passage.ref == "S2"

    def test_an_unknown_source_is_fine_if_the_quote_is_real(self) -> None:
        result = verify(draft(claim("Income is capped.", source="S9")), PASSAGES)

        assert result.claims[0].support[0].passage.ref == "S1"

    def test_a_claim_may_rest_on_several_quotes(self) -> None:
        both = DraftClaim(
            statement="Income up to Rs 2,50,000, and apply by 30 November 2026.",
            evidence=[Evidence(source="S1", quote=INCOME), Evidence(source="S2", quote=DEADLINE)],
        )

        [kept] = verify(draft(both), PASSAGES).claims

        assert [item.passage.ref for item in kept.support] == ["S1", "S2"]

    def test_a_bengali_statement_can_rest_on_an_english_quote(self) -> None:
        statement = "পারিবারিক আয় বছরে ২,৫০,০০০ টাকার বেশি হতে পারবে না।"

        assert verify(draft(claim(statement)), PASSAGES).clean

    def test_the_same_quote_twice_counts_once(self) -> None:
        twice = DraftClaim(
            statement="Income is capped.",
            evidence=[Evidence(source="S1", quote=INCOME), Evidence(source="S1", quote=INCOME)],
        )

        [kept] = verify(draft(twice), PASSAGES).claims

        assert len(kept.support) == 1

    def test_stray_references_are_removed_from_the_statement(self) -> None:
        [kept] = verify(draft(claim("Income is capped [S1]. Be sure [S1, S2]")), PASSAGES).claims

        assert kept.statement == "Income is capped. Be sure"


class TestRejectedClaims:
    def test_a_wrong_amount_is_rejected(self) -> None:
        assert reasons(draft(claim("Family income must be at most Rs 3,00,000 a year."))) == [
            ("number",)
        ]

    def test_a_figure_that_is_in_the_passage_but_not_in_the_quote_is_rejected(self) -> None:
        # The deadline is in S2 and the claim quotes S1: figures must be in the quoted words.
        statement = "Income up to Rs 2,50,000 and apply before 30 November 2026."

        found = reasons(draft(claim(statement)))

        assert found == [("number", "month")]

    def test_a_wrong_month_is_rejected(self) -> None:
        wrong = claim("The last date is 30 December 2026.", source="S2", quote=DEADLINE)

        assert reasons(draft(wrong)) == [("month",)]

    def test_an_address_the_quote_does_not_contain_is_rejected(self) -> None:
        wrong = claim("Write to help@nsp.gov.in.", source="S2", quote=HELPDESK)

        assert reasons(draft(wrong)) == [("link",)]

    def test_an_invented_quote_is_rejected(self) -> None:
        invented = claim(
            "Every girl gets double.", quote="Girl students receive double the amount."
        )

        assert reasons(draft(invented)) == [("quote_not_found",)]

    def test_a_quote_that_is_nowhere_and_a_source_that_does_not_exist(self) -> None:
        invented = claim("Every girl gets double.", source="S9", quote="Girls receive double pay.")

        assert reasons(draft(invented)) == [("unknown_source",)]

    def test_a_quote_that_is_too_short_to_mean_anything_is_rejected_for_that_reason(self) -> None:
        # "Rs.2,50,000" is in the passage, so "not found" would be a false thing to tell the model.
        assert reasons(draft(claim("Income is capped.", quote="Rs.2,50,000"))) == [
            ("quote_too_short",)
        ]

    def test_a_short_quote_does_not_spoil_a_claim_that_has_a_good_one_too(self) -> None:
        both = DraftClaim(
            statement="Income is capped.",
            evidence=[
                Evidence(source="S1", quote="Rs.2,50,000"),
                Evidence(source="S1", quote=INCOME),
            ],
        )

        assert verify(draft(both), PASSAGES).clean

    def test_a_claim_without_evidence_is_rejected(self) -> None:
        bare = DraftClaim(statement="Income is capped.", evidence=[])

        assert reasons(draft(bare)) == [("no_evidence",)]

    def test_an_empty_statement_is_rejected(self) -> None:
        assert reasons(draft(claim("  [S1]  "))) == [("empty",)]

    def test_a_very_long_statement_is_rejected(self) -> None:
        assert reasons(draft(claim("word " * MAX_STATEMENT_CHARS))) == [("too_long",)]

    def test_a_repeated_statement_is_rejected(self) -> None:
        once = claim("Income is capped.")

        result = verify(draft(once, once), PASSAGES)

        assert len(result.claims) == 1
        assert [item.reasons for item in result.rejections] == [("duplicate",)]

    def test_a_reason_is_recorded_with_the_position_of_the_claim(self) -> None:
        good = claim("Income is capped.")
        bad = claim("Income is capped at Rs 9.", quote="Not a real quote from the passage")

        result = verify(draft(good, bad), PASSAGES)

        assert [item.statement for item in result.claims] == ["Income is capped."]
        assert [item.index for item in result.rejections] == [1]
        assert not result.clean

    def test_a_claim_keeps_its_good_quote_when_another_quote_fails(self) -> None:
        mixed = DraftClaim(
            statement="Income is capped.",
            evidence=[
                Evidence(source="S1", quote="A sentence the passage does not contain."),
                Evidence(source="S1", quote=INCOME),
            ],
        )

        result = verify(draft(mixed), PASSAGES)

        assert result.clean
        assert len(result.claims[0].support) == 1

    def test_no_reason_carries_any_text(self) -> None:
        secret = claim("Secret 9876 statement.", quote="A quote that is secret and not present.")

        [rejection] = verify(draft(secret), PASSAGES).rejections

        assert rejection.reasons == ("quote_not_found",)
        assert "9876" not in repr(rejection)


class TestLanguage:
    BENGALI = "পারিবারিক আয় বছরে ২,৫০,০০০ টাকার বেশি হতে পারবে না।"

    def test_an_english_statement_is_rejected_when_bengali_was_asked_for(self) -> None:
        found = verify(draft(claim("Income is capped.")), PASSAGES, language="bn")

        assert [item.reasons for item in found.rejections] == [("language",)]

    def test_a_bengali_statement_is_rejected_when_english_was_asked_for(self) -> None:
        found = verify(draft(claim(self.BENGALI)), PASSAGES, language="en")

        assert [item.reasons for item in found.rejections] == [("language",)]

    def test_a_statement_in_the_right_language_is_kept(self) -> None:
        assert verify(draft(claim(self.BENGALI)), PASSAGES, language="bn").clean
        assert verify(draft(claim("Income is capped.")), PASSAGES, language="en").clean

    def test_no_language_means_no_check(self) -> None:
        assert verify(draft(claim(self.BENGALI), claim("Income is capped.")), PASSAGES).clean


class TestLimits:
    def test_claims_beyond_the_cap_are_ignored(self) -> None:
        # Different words, no digits: a figure would be rejected for not being in the quote.
        many = [claim(f"Income is capped {chr(ord('a') + n)}.") for n in range(MAX_CLAIMS + 5)]

        result = verify(draft(*many), PASSAGES)

        assert len(result.claims) == MAX_CLAIMS

    def test_an_empty_draft_verifies_to_nothing(self) -> None:
        result = verify(Draft(answerable=False, claims=[]), PASSAGES)

        assert result.claims == ()
        assert result.clean

    def test_no_passages_means_no_claim_can_hold_up(self) -> None:
        result = verify(draft(claim("Income is capped.")), [])

        assert result.claims == ()
        assert [item.reasons for item in result.rejections] == [("unknown_source",)]


def test_clean_statement_collapses_white_space() -> None:
    assert clean_statement("  Income \n is   capped. [S2] ") == "Income is capped."
