from datetime import date, datetime, timedelta

from app.domain.assistant import Citation, Passage
from app.services.assistant.citations import build_citations, source_warnings, warning
from app.services.grounding.text import Located
from app.services.grounding.verify import Support, VerifiedClaim
from tests.factories import NOW

TEXT = (
    "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum. Apply online."
)


def passage(chunk: str = "c1", source: str = "guide", **fields: object) -> Passage:
    base: dict[str, object] = {
        "ref": "S1",
        "chunk_id": chunk,
        "source_id": source,
        "title": "Demo Guidelines",
        "authority": "Department of Demos",
        "url": "https://x.gov.in/a.pdf",
        "text": TEXT,
        "page_start": 3,
        "page_end": 3,
        "section": "ELIGIBILITY",
        "document_date": date(2026, 6, 1),
        "date_source": "pdf-metadata",
        "verified_at": NOW - timedelta(days=2),
        "verification": "verified",
    }
    return Passage(**{**base, **fields})  # type: ignore[arg-type]


def claim(statement: str, *supports: tuple[Passage, tuple[tuple[int, int], ...]]) -> VerifiedClaim:
    return VerifiedClaim(statement, tuple(Support(p, Located(spans)) for p, spans in supports))


def span(words: str) -> tuple[tuple[int, int], ...]:
    start = TEXT.index(words)
    return ((start, start + len(words)),)


INCOME_SPAN = span("upper ceiling for family income has been fixed at Rs.2,50,000/- per annum")
APPLY_SPAN = span("Apply online")


class TestBuildCitations:
    def test_citations_are_numbered_in_the_order_they_are_first_used(self) -> None:
        p = passage()
        claims, citations = build_citations(
            [claim("One.", (p, APPLY_SPAN)), claim("Two.", (p, INCOME_SPAN))], NOW
        )

        assert [c.number for c in citations] == [1, 2]
        assert [c.citations for c in claims] == [[1], [2]]
        assert citations[0].quote == "Apply online"

    def test_two_claims_resting_on_the_same_words_share_a_citation(self) -> None:
        p = passage()

        claims, citations = build_citations(
            [claim("One.", (p, INCOME_SPAN)), claim("Two.", (p, INCOME_SPAN))], NOW
        )

        assert len(citations) == 1
        assert [c.citations for c in claims] == [[1], [1]]

    def test_two_quotes_of_one_passage_are_two_citations_so_each_highlights_its_own_words(
        self,
    ) -> None:
        p = passage()

        _, citations = build_citations(
            [claim("One.", (p, INCOME_SPAN)), claim("Two.", (p, APPLY_SPAN))], NOW
        )

        assert [(h.start, h.end) for c in citations for h in c.highlights] == [
            INCOME_SPAN[0],
            APPLY_SPAN[0],
        ]
        assert all(c.passage == TEXT for c in citations)  # the whole passage is shown each time

    def test_a_claim_with_two_quotes_lists_both_numbers_once(self) -> None:
        a, b = passage("c1"), passage("c2", "other", title="Other Guidelines")

        claims, citations = build_citations(
            [claim("Both.", (a, INCOME_SPAN), (b, APPLY_SPAN), (a, INCOME_SPAN))], NOW
        )

        assert claims[0].citations == [1, 2]
        assert [c.title for c in citations] == ["Demo Guidelines", "Other Guidelines"]

    def test_a_citation_carries_where_the_words_are_and_how_fresh_the_source_is(self) -> None:
        [citation] = build_citations([claim("One.", (passage(), INCOME_SPAN))], NOW)[1]

        assert citation.source_id == "guide"
        assert citation.url == "https://x.gov.in/a.pdf"
        assert (citation.page_start, citation.page_end, citation.section) == (3, 3, "ELIGIBILITY")
        assert citation.document_date == date(2026, 6, 1)
        assert citation.age_days == 152
        assert not citation.stale
        assert citation.verification == "verified"

    def test_a_citation_says_which_language_its_words_are_in(self) -> None:
        [citation] = build_citations([claim("One.", (passage(language="en"), INCOME_SPAN))], NOW)[1]

        assert citation.language == "en"

    def test_an_old_document_is_marked_stale(self) -> None:
        old = passage(document_date=date(2024, 1, 1))

        [citation] = build_citations([claim("One.", (old, INCOME_SPAN))], NOW)[1]

        assert citation.stale

    def test_no_claims_no_citations(self) -> None:
        assert build_citations([], NOW) == ([], [])


def citation_of(**fields: object) -> Citation:
    return build_citations([claim("One.", (passage(**fields), INCOME_SPAN))], NOW)[1][0]


class TestSourceWarnings:
    def test_a_current_verified_source_has_no_warning(self) -> None:
        assert source_warnings([citation_of()], "en", NOW) == []

    def test_a_document_older_than_twelve_months_is_flagged_with_its_date(self) -> None:
        [found] = source_warnings([citation_of(document_date=date(2024, 1, 1))], "en", NOW)

        assert found.code == "stale"
        assert found.source_ids == ["guide"]
        assert found.message.startswith("Demo Guidelines is dated 2024-01-01")

    def test_a_document_with_no_date_is_flagged_as_undated_not_as_stale(self) -> None:
        found = source_warnings([citation_of(document_date=None)], "en", NOW)

        assert [item.code for item in found] == ["date_unknown"]

    def test_a_source_not_checked_for_a_month_is_flagged(self) -> None:
        long_ago = NOW - timedelta(days=45)

        [found] = source_warnings([citation_of(verified_at=long_ago)], "en", NOW)

        assert found.code == "verification_due"
        assert "2026-09-16" in found.message

    def test_a_scanned_source_is_flagged(self) -> None:
        [found] = source_warnings([citation_of(ocr=True)], "en", NOW)

        assert found.code == "scanned"

    def test_a_source_that_had_instructions_removed_is_flagged_if_it_is_cited(self) -> None:
        cited = [citation_of()]

        assert [w.code for w in source_warnings(cited, "en", NOW, sanitized_sources={"guide"})] == [
            "sanitized"
        ]
        assert source_warnings(cited, "en", NOW, sanitized_sources={"another-source"}) == []

    def test_one_source_is_flagged_once_however_often_it_is_cited(self) -> None:
        stale = passage(document_date=date(2024, 1, 1))
        _, citations = build_citations(
            [claim("One.", (stale, INCOME_SPAN)), claim("Two.", (stale, APPLY_SPAN))], NOW
        )

        assert [w.code for w in source_warnings(citations, "en", NOW)] == ["stale"]

    def test_each_source_is_flagged_for_itself(self) -> None:
        old = passage("c1", "old-source", document_date=date(2024, 1, 1), title="Old")
        undated = passage("c2", "undated-source", document_date=None, title="Undated")
        _, citations = build_citations(
            [claim("One.", (old, INCOME_SPAN), (undated, APPLY_SPAN))], NOW
        )

        found = source_warnings(citations, "en", NOW)

        assert [(w.code, w.source_ids) for w in found] == [
            ("stale", ["old-source"]),
            ("date_unknown", ["undated-source"]),
        ]

    def test_a_naive_verification_time_does_not_crash(self) -> None:
        naive = datetime(2026, 10, 30, 9, 0)  # no time zone
        assert source_warnings([citation_of(verified_at=naive)], "en", NOW) == []

    def test_warnings_are_written_in_the_language_of_the_answer(self) -> None:
        [found] = source_warnings([citation_of(ocr=True)], "bn", NOW)

        assert "Demo Guidelines" in found.message
        assert "স্ক্যান" in found.message  # Bengali for "scanned"


def test_a_notice_is_the_fixed_message_for_its_code() -> None:
    notice = warning("en", "claims_removed")

    assert notice.code == "claims_removed"
    assert notice.source_ids == []
    assert "removed" in notice.message
    assert warning("bn", "stale", "guide", title="T", date="2024-01-01").source_ids == ["guide"]
