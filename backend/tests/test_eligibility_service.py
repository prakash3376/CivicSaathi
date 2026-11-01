import itertools
import math
from datetime import date
from typing import Any

import pytest

from app.domain.eligibility import EligibilityResult
from app.services.eligibility.loader import SchemeBook, load_schemes
from app.services.eligibility.service import EligibilityInputError, SchemeService
from app.services.ingestion.registry import load_registry

TODAY = date(2026, 10, 31)

# A girl who meets every Pragati rule for a degree course.
PRAGATI: dict[str, Any] = {
    "gender": "female",
    "girls_in_family": 1,
    "family_income": 500000,
    "receives_other_scholarship": False,
    "institution_aicte_approved": True,
    "admission_type": "first_year",
}
# A student who meets every SVMCM rule for an undergraduate course.
SVMCM_UG: dict[str, Any] = {
    "institution_in_west_bengal": True,
    "receives_other_scholarship": False,
    "family_income": 200000,
    "marks_percent": 72,
}


@pytest.fixture(scope="module")
def book() -> SchemeBook:
    return load_schemes(sources={spec.id: spec.url for spec in load_registry()})


@pytest.fixture
def service(book: SchemeBook) -> SchemeService:
    return SchemeService(book, clock=lambda: TODAY)


def check(service: SchemeService, scheme: str, track: str, **answers: Any) -> EligibilityResult:
    return service.check(scheme, track, answers)


def statuses(result: EligibilityResult) -> dict[str, str]:
    return {c.id: c.status for c in result.criteria}


class TestPragati:
    def test_a_girl_meeting_every_rule_is_eligible_with_every_criterion_met(
        self, service: SchemeService
    ) -> None:
        result = check(service, "aicte-pragati", "degree", **PRAGATI)

        assert result.outcome == "eligible"
        assert set(statuses(result).values()) == {"met"}
        assert result.unanswered == []

    def test_every_criterion_comes_with_the_words_of_the_document(
        self, service: SchemeService
    ) -> None:
        result = check(service, "aicte-pragati", "degree", **PRAGATI)

        for criterion in result.criteria:
            assert criterion.evidence
            assert all(e.quote and e.source_id for e in criterion.evidence)

    def test_income_exactly_8_lakh_is_not_eligible_because_the_faq_says_less_than(
        self, service: SchemeService
    ) -> None:
        result = check(service, "aicte-pragati", "degree", **{**PRAGATI, "family_income": 800000})

        assert result.outcome == "not_eligible"
        assert statuses(result)["income"] == "not_met"
        assert next(c for c in result.criteria if c.id == "income").answer_text is not None

    def test_one_rupee_under_the_limit_is_eligible(self, service: SchemeService) -> None:
        assert (
            check(
                service, "aicte-pragati", "degree", **{**PRAGATI, "family_income": 799999}
            ).outcome
            == "eligible"
        )

    def test_a_skipped_income_needs_more_info_and_asks_for_it(self, service: SchemeService) -> None:
        answers = {k: v for k, v in PRAGATI.items() if k != "family_income"}

        result = check(service, "aicte-pragati", "degree", **answers)

        assert result.outcome == "need_more_info"
        assert result.unanswered == ["family_income"]
        assert statuses(result)["income"] == "unknown"

    @pytest.mark.parametrize(
        ("change", "failed"),
        [
            ({"gender": "male"}, "female"),
            ({"girls_in_family": 3}, "two_girls"),
            ({"receives_other_scholarship": True}, "no_other_scholarship"),
            ({"institution_aicte_approved": False}, "aicte_approved"),
            ({"admission_type": "other"}, "admission"),
        ],
    )
    def test_each_rule_alone_can_say_no(
        self, service: SchemeService, change: dict[str, Any], failed: str
    ) -> None:
        result = check(service, "aicte-pragati", "degree", **{**PRAGATI, **change})

        assert result.outcome == "not_eligible"
        assert [i for i, s in statuses(result).items() if s == "not_met"] == [failed]

    def test_two_girls_is_allowed_and_three_is_not(self, service: SchemeService) -> None:
        assert (
            check(service, "aicte-pragati", "degree", **{**PRAGATI, "girls_in_family": 2}).outcome
            == "eligible"
        )
        assert (
            check(service, "aicte-pragati", "degree", **{**PRAGATI, "girls_in_family": 3}).outcome
            == "not_eligible"
        )

    def test_lateral_entry_is_accepted(self, service: SchemeService) -> None:
        result = check(
            service, "aicte-pragati", "diploma", **{**PRAGATI, "admission_type": "lateral_entry"}
        )

        assert result.outcome == "eligible"

    def test_a_definite_no_stands_even_if_other_questions_are_skipped(
        self, service: SchemeService
    ) -> None:
        result = check(service, "aicte-pragati", "degree", gender="male")

        assert result.outcome == "not_eligible"
        assert "family_income" in result.unanswered

    def test_nothing_answered_needs_more_info_about_everything(
        self, service: SchemeService
    ) -> None:
        result = check(service, "aicte-pragati", "degree")

        assert result.outcome == "need_more_info"
        assert result.unanswered == [
            "gender", "girls_in_family", "family_income", "receives_other_scholarship",
            "institution_aicte_approved", "admission_type",
        ]  # fmt: skip

    def test_skipping_any_question_of_an_eligible_profile_never_gives_eligible(
        self, service: SchemeService
    ) -> None:
        # SPEC AC6, on the real rules: all 63 ways of skipping at least one question.
        fields = list(PRAGATI)
        for size in range(1, len(fields) + 1):
            for skipped in itertools.combinations(fields, size):
                answers = {k: v for k, v in PRAGATI.items() if k not in skipped}

                result = service.check("aicte-pragati", "degree", answers)

                assert result.outcome == "need_more_info", skipped
                assert set(result.unanswered) == set(skipped), skipped

    def test_the_two_tracks_have_their_own_rules_and_documents(
        self, service: SchemeService
    ) -> None:
        degree = service.details("aicte-pragati")
        assert degree is not None
        by_track = {t.id: t for t in degree.tracks}

        assert "twelfth_certificate" in {d.id for d in by_track["degree"].documents}
        assert "twelfth_certificate" not in {d.id for d in by_track["diploma"].documents}
        assert "iti_certificate" in {d.id for d in by_track["diploma"].documents}


class TestSvmcm:
    def test_a_student_meeting_every_rule_is_eligible(self, service: SchemeService) -> None:
        assert check(service, "svmcm", "ug", **SVMCM_UG).outcome == "eligible"

    def test_income_exactly_2_50_000_is_eligible_because_the_guidelines_say_not_more_than(
        self, service: SchemeService
    ) -> None:
        assert (
            check(service, "svmcm", "ug", **{**SVMCM_UG, "family_income": 250000}).outcome
            == "eligible"
        )

    def test_income_one_rupee_over_is_not_eligible_without_a_waiver(
        self, service: SchemeService
    ) -> None:
        answers = {**SVMCM_UG, "family_income": 250001, "board_topper": False}

        result = check(service, "svmcm", "ug", **answers)

        assert result.outcome == "not_eligible"
        assert statuses(result)["income"] == "not_met"

    def test_income_over_the_limit_asks_about_the_waiver_before_saying_no(
        self, service: SchemeService
    ) -> None:
        result = check(service, "svmcm", "ug", **{**SVMCM_UG, "family_income": 400000})

        assert result.outcome == "need_more_info"
        assert result.unanswered == ["board_topper"]

    def test_a_board_topper_is_exempt_from_the_income_limit(self, service: SchemeService) -> None:
        answers = {**SVMCM_UG, "family_income": 900000, "board_topper": True}

        result = check(service, "svmcm", "ug", **answers)

        assert result.outcome == "eligible"
        income = next(c for c in result.criteria if c.id == "income")
        assert (income.status, income.waived) == ("met", True)

    def test_a_board_topper_question_left_blank_does_not_hold_up_a_low_income(
        self, service: SchemeService
    ) -> None:
        # Within the limit, the waiver cannot change anything: no need to ask.
        assert check(service, "svmcm", "ug", **SVMCM_UG).unanswered == []

    @pytest.mark.parametrize(
        ("marks", "outcome"),
        [(60, "eligible"), (59.99, "not_eligible"), (100, "eligible"), (0, "not_eligible")],
    )
    def test_at_least_60_includes_60(
        self, service: SchemeService, marks: float, outcome: str
    ) -> None:
        assert (
            check(service, "svmcm", "ug", **{**SVMCM_UG, "marks_percent": marks}).outcome == outcome
        )

    def test_each_level_has_its_own_marks(self, service: SchemeService) -> None:
        answers = {**SVMCM_UG, "marks_percent": 55}

        assert check(service, "svmcm", "ug", **answers).outcome == "not_eligible"  # 60 needed
        assert (
            check(service, "svmcm", "pg", **{**answers, "marks_percent": 53}).outcome == "eligible"
        )
        assert (
            check(service, "svmcm", "pg", **{**answers, "marks_percent": 52.9}).outcome
            == "not_eligible"
        )

    def test_the_madhyamik_level_also_asks_about_the_board(self, service: SchemeService) -> None:
        answers = {**SVMCM_UG, "marks_percent": 80}

        needs = check(service, "svmcm", "hs", **answers)
        no = check(service, "svmcm", "hs", **answers, passed_wb_board=False)
        yes = check(service, "svmcm", "hs", **answers, passed_wb_board=True)

        assert (needs.outcome, needs.unanswered) == ("need_more_info", ["passed_wb_board"])
        assert no.outcome == "not_eligible"
        assert yes.outcome == "eligible"

    def test_kanyashree_k3_has_no_income_question_and_no_income_documents(
        self, service: SchemeService
    ) -> None:
        details = service.details("svmcm")
        assert details is not None
        k3 = next(t for t in details.tracks if t.id == "pg-k3")
        ug = next(t for t in details.tracks if t.id == "ug")

        assert "family_income" not in {q.field for q in k3.questions}
        assert "income_documents" not in {d.id for d in k3.documents}
        assert "income_documents" in {d.id for d in ug.documents}
        assert "bank_details" in {d.id for d in k3.documents}

    def test_a_kanyashree_k3_applicant_with_a_high_income_is_eligible(
        self, service: SchemeService
    ) -> None:
        answers = {
            "institution_in_west_bengal": True,
            "receives_other_scholarship": False,
            "gender": "female",
            "marks_percent": 45,
        }

        assert check(service, "svmcm", "pg-k3", **answers).outcome == "eligible"
        assert (
            check(service, "svmcm", "pg-k3", **{**answers, "marks_percent": 44}).outcome
            == "not_eligible"
        )
        assert (
            check(service, "svmcm", "pg-k3", **{**answers, "gender": "male"}).outcome
            == "not_eligible"
        )

    def test_a_student_outside_west_bengal_is_not_eligible(self, service: SchemeService) -> None:
        assert (
            check(
                service, "svmcm", "ug", **{**SVMCM_UG, "institution_in_west_bengal": False}
            ).outcome
            == "not_eligible"
        )


class TestChecklist:
    def test_documents_that_depend_on_an_answer_are_maybe_until_it_is_given(
        self, service: SchemeService
    ) -> None:
        result = check(service, "aicte-pragati", "degree")

        by_id = {d.id: d.applicability for d in result.checklist.documents}

        assert by_id["diploma_certificate"] == "maybe"
        assert by_id["tenth_certificate"] == "needed"
        assert by_id["category"] == "maybe"  # the FAQ says "if applicable"

    def test_a_document_for_lateral_entry_is_needed_for_those_who_joined_that_way(
        self, service: SchemeService
    ) -> None:
        result = check(
            service, "aicte-pragati", "degree", **{**PRAGATI, "admission_type": "lateral_entry"}
        )

        assert {d.id: d.applicability for d in result.checklist.documents}[
            "diploma_certificate"
        ] == "needed"

    def test_it_is_left_out_for_those_who_did_not(self, service: SchemeService) -> None:
        result = check(service, "aicte-pragati", "degree", **PRAGATI)

        assert "diploma_certificate" not in {d.id for d in result.checklist.documents}

    def test_every_document_has_evidence(self, service: SchemeService) -> None:
        for scheme in service.catalogue():
            result = check(service, scheme.id, scheme.tracks[0].id)
            assert result.checklist.documents
            assert all(d.evidence for d in result.checklist.documents)

    def test_it_carries_steps_contacts_where_to_apply_and_what_is_not_stated(
        self, service: SchemeService
    ) -> None:
        checklist = check(service, "aicte-pragati", "degree", **PRAGATI).checklist

        assert [s.id for s in checklist.steps] == [
            "apply_online",
            "check_details",
            "institute_verifies",
        ]
        assert {c.value for c in checklist.contacts} == {
            "pragati@aicte-india.org", "011-29581118", "helpdesk@nsp.gov.in",
        }  # fmt: skip
        assert checklist.apply.url == "https://scholarships.gov.in"
        assert checklist.not_stated  # fees: the documents do not say (rule R1)

    def test_a_scheme_whose_documents_give_no_deadline_says_so_instead(
        self, service: SchemeService
    ) -> None:
        checklist = check(service, "svmcm", "ug", **SVMCM_UG).checklist

        assert checklist.deadlines == []
        assert any("last date" in text.en.lower() for text in checklist.not_stated)

    def test_the_disclaimer_is_always_there_in_both_languages(self, service: SchemeService) -> None:
        result = check(service, "svmcm", "ug")

        assert result.disclaimer.en.startswith("Informational summary, not legal advice")
        assert result.disclaimer.bn
        assert result.disclaimer.hi.startswith("यह केवल जानकारी")


class TestDeadlines:
    def deadline(self, book: SchemeBook, today: date) -> Any:
        summary = next(
            s
            for s in SchemeService(book, clock=lambda: today).catalogue()
            if s.id == "aicte-pragati"
        )
        assert summary.deadline is not None
        return summary.deadline

    def test_before_the_date_it_is_open_with_the_days_left(self, book: SchemeBook) -> None:
        deadline = self.deadline(book, date(2026, 10, 20))

        assert (deadline.status, deadline.days_left) == ("open", 11)

    def test_on_the_day_it_closes_today(self, book: SchemeBook) -> None:
        deadline = self.deadline(book, date(2026, 10, 31))

        assert (deadline.status, deadline.days_left) == ("closes_today", 0)

    def test_after_the_date_it_is_closed(self, book: SchemeBook) -> None:
        deadline = self.deadline(book, date(2026, 11, 1))

        assert (deadline.status, deadline.days_left) == ("closed", None)

    def test_the_date_comes_from_a_scan_and_says_so(self, book: SchemeBook) -> None:
        assert self.deadline(book, TODAY).scanned is True


class TestCatalogue:
    def test_every_scheme_is_listed_with_its_tracks(self, service: SchemeService) -> None:
        listed = {s.id: [t.id for t in s.tracks] for s in service.catalogue()}

        assert listed == {
            "aicte-pragati": ["degree", "diploma"],
            "svmcm": ["hs", "ug", "pg", "pg-k3", "diploma"],
        }

    def test_a_scheme_with_no_stated_deadline_has_none(self, service: SchemeService) -> None:
        assert next(s for s in service.catalogue() if s.id == "svmcm").deadline is None

    def test_details_say_what_each_track_requires_and_pays(self, service: SchemeService) -> None:
        details = service.details("svmcm")
        assert details is not None
        ug = next(t for t in details.tracks if t.id == "ug")

        assert "1,000" in ug.benefit.text.en
        assert "1,500" in ug.benefit.text.en
        assert [c.id for c in ug.criteria] == [
            "in_west_bengal",
            "no_other_scholarship",
            "income",
            "marks",
        ]
        assert [q.field for q in ug.questions] == [
            "institution_in_west_bengal", "receives_other_scholarship", "family_income",
            "board_topper", "marks_percent",
        ]  # fmt: skip

    def test_an_unknown_scheme_has_no_details(self, service: SchemeService) -> None:
        assert service.details("ghost") is None


class TestAnswersAreCheckedWithoutBeingEchoed:
    SECRET = "SECRET-ANSWER-9876"

    def refused(
        self, service: SchemeService, scheme: str, track: str, answers: dict[str, Any]
    ) -> EligibilityInputError:
        with pytest.raises(EligibilityInputError) as error:
            service.check(scheme, track, answers)
        assert self.SECRET not in error.value.message
        return error.value

    def test_an_unknown_scheme(self, service: SchemeService) -> None:
        assert self.refused(service, "ghost", "x", {}).code == "unknown_scheme"

    def test_an_unknown_track(self, service: SchemeService) -> None:
        assert self.refused(service, "svmcm", "ghost", {}).code == "unknown_track"

    def test_an_unknown_question_is_refused_and_its_name_is_not_echoed(
        self, service: SchemeService
    ) -> None:
        error = self.refused(service, "svmcm", "ug", {self.SECRET: 1})

        assert error.code == "unknown_question"

    def test_a_question_of_another_track_is_refused(self, service: SchemeService) -> None:
        assert self.refused(service, "svmcm", "ug", {"gender": "female"}).code == "unknown_question"

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("family_income", SECRET),
            ("family_income", True),
            ("family_income", 1.5),
            ("family_income", -1),
            ("family_income", 10**12),
            ("family_income", math.nan),
            ("family_income", math.inf),
            ("marks_percent", 100.5),
            ("marks_percent", -0.1),
            ("receives_other_scholarship", SECRET),
            ("receives_other_scholarship", 1),
            ("institution_in_west_bengal", "yes"),
        ],
    )
    def test_an_answer_that_does_not_suit_its_question(
        self, service: SchemeService, field: str, value: Any
    ) -> None:
        error = self.refused(service, "svmcm", "ug", {field: value})

        assert error.code == "invalid_answer"
        assert field in error.message  # the question is named: it is ours, not the person's

    def test_a_choice_that_is_not_offered(self, service: SchemeService) -> None:
        assert (
            self.refused(service, "aicte-pragati", "degree", {"gender": self.SECRET}).code
            == "invalid_answer"
        )

    def test_a_null_answer_is_a_skipped_question(self, service: SchemeService) -> None:
        result = service.check("aicte-pragati", "degree", {**PRAGATI, "family_income": None})

        assert result.outcome == "need_more_info"

    def test_a_whole_number_sent_as_a_float_is_accepted(self, service: SchemeService) -> None:
        assert (
            service.check("aicte-pragati", "degree", {**PRAGATI, "family_income": 500000.0}).outcome
            == "eligible"
        )


class TestAnswersShownBackInWords:
    def test_an_income_with_indian_grouping_in_both_languages(self, service: SchemeService) -> None:
        result = check(service, "aicte-pragati", "degree", **{**PRAGATI, "family_income": 900000})

        income = next(c for c in result.criteria if c.id == "income")

        assert income.answer_text is not None
        assert income.answer_text.en == "Rs 9,00,000 a year"
        assert income.answer_text.bn == "বছরে 9,00,000 টাকা"
        assert income.answer_text.hi == "प्रति वर्ष 9,00,000 रुपये"

    def test_yes_no_and_choices_are_shown_in_words(self, service: SchemeService) -> None:
        result = check(
            service, "aicte-pragati", "degree", **{**PRAGATI, "admission_type": "lateral_entry"}
        )
        by_id = {c.id: c.answer_text for c in result.criteria}

        assert by_id["no_other_scholarship"] is not None
        assert by_id["no_other_scholarship"].en == "No"
        assert by_id["admission"] is not None
        assert "lateral entry" in by_id["admission"].en

    def test_a_skipped_question_has_no_answer_text(self, service: SchemeService) -> None:
        result = check(service, "aicte-pragati", "degree")

        assert all(c.answer_text is None for c in result.criteria)


class TestDeterminism:
    """SPEC AC5."""

    def test_the_same_answers_give_the_same_result_whatever_their_order(
        self, service: SchemeService
    ) -> None:
        forward = service.check("aicte-pragati", "degree", dict(PRAGATI))
        backward = service.check("aicte-pragati", "degree", dict(reversed(list(PRAGATI.items()))))

        assert forward == backward

    def test_asking_twice_gives_the_same_result(self, service: SchemeService) -> None:
        assert service.check("svmcm", "ug", SVMCM_UG) == service.check("svmcm", "ug", SVMCM_UG)

    def test_the_answers_passed_in_are_not_modified(self, service: SchemeService) -> None:
        answers = {**PRAGATI, "family_income": None}
        before = dict(answers)

        service.check("aicte-pragati", "degree", answers)

        assert answers == before
