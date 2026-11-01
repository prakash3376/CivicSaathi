from pathlib import Path

import pytest

from app.domain.assistant import Answer, Passage
from app.domain.catalogue import BudgetRecord, Cite
from app.domain.errors import AssistantError
from app.services.evaluation.cases import Case, load_cases
from app.services.evaluation.runner import (
    evaluate_answers,
    evaluate_retrieval,
    summarise_answers,
    summarise_retrieval,
)
from tests.test_search import entry

QUOTE = "PM-KISAN pays Rs 6000 a year to landholding farmer families."

HANDWRITTEN = """
[[cases]]
id = "money"
group = "colloquial"
intent = "scheme_discovery"
question = "Who gets farmer money?"
hi = "किसान को पैसा कौन पाता है?"
entries = ["pm-kisan"]

[[cases]]
id = "weather"
group = "adversarial"
question = "What is the weather today?"
answerable = false

[[cases]]
id = "budget"
group = "numeric"
question = "How much is the health budget?"
sources = ["budget-doc"]
"""


def kisan_entry():  # type: ignore[no-untyped-def]
    built = entry(
        "pm-kisan", "PM-KISAN", "income support for farmer families", "agriculture", "kisan"
    )
    return built.model_copy(
        update={
            "benefits": [
                built.benefits[0].model_copy(
                    update={"evidence": [Cite(source_id="kisan", quote=QUOTE)]}
                )
            ]
        }
    )


def passage(source: str, text: str, number: int = 1) -> Passage:
    return Passage(
        chunk_id=f"{source}:{number}",
        source_id=source,
        title=source,
        url="https://x.gov.in/",
        text=text,
    )


@pytest.fixture
def cases(tmp_path: Path) -> list[Case]:
    (tmp_path / "questions.toml").write_text(HANDWRITTEN, encoding="utf-8")
    return load_cases([kisan_entry()], [], tmp_path)


class TestLoadingTheCases:
    def test_a_question_with_translations_becomes_one_case_per_language(
        self, cases: list[Case]
    ) -> None:
        money = [c for c in cases if c.extras.get("base") == "money"]

        assert {(c.id, c.language) for c in money} == {("money", "en"), ("money.hi", "hi")}
        assert {c.group for c in money} == {"colloquial", "multilingual"}
        assert all(c.sources == {"kisan"} for c in money)

    def test_the_evidence_is_the_verified_quotes_of_the_entries(self, cases: list[Case]) -> None:
        money = next(c for c in cases if c.id == "money")

        assert [q.quote for q in money.quotes] == [QUOTE]

    def test_a_question_the_documents_cannot_answer_has_no_evidence(
        self, cases: list[Case]
    ) -> None:
        weather = next(c for c in cases if c.id == "weather")

        assert (weather.answerable, weather.sources, weather.quotes) == (False, frozenset(), ())

    def test_an_entry_that_does_not_exist_is_an_error(self, tmp_path: Path) -> None:
        (tmp_path / "questions.toml").write_text(
            '[[cases]]\nid = "x"\ngroup = "g"\nquestion = "q"\nentries = ["nope"]\n',
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="unknown entries"):
            load_cases([kisan_entry()], [], tmp_path)

    def test_an_answerable_question_without_evidence_is_an_error(self, tmp_path: Path) -> None:
        (tmp_path / "questions.toml").write_text(
            '[[cases]]\nid = "x"\ngroup = "g"\nquestion = "q"\n', encoding="utf-8"
        )

        with pytest.raises(ValueError, match="needs entries or sources"):
            load_cases([kisan_entry()], [], tmp_path)

    def test_questions_are_derived_from_every_entry(self, cases: list[Case]) -> None:
        derived = [c for c in cases if c.origin == "derived"]

        assert {c.id for c in derived} == {"derived.benefit.pm-kisan"}
        assert derived[0].question == "What does PM-KISAN give?"
        assert derived[0].quotes[0].quote == QUOTE

    def test_budget_questions_are_derived_only_from_records_with_figures(
        self, tmp_path: Path
    ) -> None:
        record = BudgetRecord.model_validate(
            {
                "id": "union-health",
                "budget_year": "2026-27",
                "level": "central",
                "title": "Union Budget 2026-27: Health",
                "department": "Ministry",
                "source_ids": ["budget-doc"],
                "last_verified": "2026-10-31",
                "summary": {"en": "x", "bn": "x", "hi": "x"},
                "statements": [
                    {
                        "text": "A statement.",
                        "evidence": [{"source_id": "budget-doc", "quote": "q" * 40}],
                    }
                ],
            }
        )

        assert not [c for c in load_cases([], [record], tmp_path) if "budget" in c.id]


class TestMeasuringRetrieval:
    def test_it_finds_the_rank_of_the_right_document_and_of_the_right_words(
        self, cases: list[Case]
    ) -> None:
        money = [c for c in cases if c.id == "money"]

        def search(_case: Case) -> list[Passage]:
            return [
                passage("other", "something else", 1),
                passage("kisan", "Rules of the scheme in general.", 2),
                passage("kisan", f"Introduction. {QUOTE} More text.", 3),
            ]

        [result] = evaluate_retrieval(money, search)

        assert (result.source_rank, result.evidence_rank) == (2, 3)
        assert result.top == ["other", "kisan", "kisan"]

    def test_a_quote_is_matched_ignoring_spacing_and_case(self, cases: list[Case]) -> None:
        money = [c for c in cases if c.id == "money"]
        spaced = "pm-kisan   PAYS Rs 6000 a year\nto landholding farmer families."

        [result] = evaluate_retrieval(money, lambda _c: [passage("kisan", spaced)])

        assert result.evidence_rank == 1

    def test_a_quote_in_another_document_does_not_count(self, cases: list[Case]) -> None:
        money = [c for c in cases if c.id == "money"]

        [result] = evaluate_retrieval(money, lambda _c: [passage("other", QUOTE)])

        assert (result.source_rank, result.evidence_rank) == (None, None)

    def test_nothing_found_is_a_miss_and_is_counted(self, cases: list[Case]) -> None:
        results = evaluate_retrieval([c for c in cases if c.id == "money"], lambda _c: [])

        summary = summarise_retrieval(results, 5)

        assert summary["overall"]["source_recall@5"] == 0.0
        assert summary["overall"]["mrr"] == 0.0

    def test_the_summary_counts_hits_within_k_and_averages_the_ranks(
        self, cases: list[Case]
    ) -> None:
        wanted = [c for c in cases if c.answerable and c.origin == "handwritten"]
        ranks = iter([1, 7, None])

        def search(case: Case) -> list[Passage]:
            rank = next(ranks)
            if rank is None:
                return []
            found = [passage("other", "x", n) for n in range(1, rank)]
            return [*found, passage(next(iter(case.sources)), "y", rank)]

        results = evaluate_retrieval(wanted, search)
        summary = summarise_retrieval(results, 5)["overall"]

        assert summary["cases"] == 3
        assert summary["source_recall@5"] == round(1 / 3, 3)
        assert summary["mrr"] == round((1 + 1 / 7) / 3, 3)

    def test_questions_the_documents_cannot_answer_are_not_scored_as_misses(
        self, cases: list[Case]
    ) -> None:
        results = evaluate_retrieval([c for c in cases if c.id == "weather"], lambda _c: [])

        assert summarise_retrieval(results, 5)["overall"]["cases"] == 0

    def test_intent_accuracy_is_counted_on_the_labelled_cases(self, cases: list[Case]) -> None:
        labelled = [c for c in cases if c.id in {"money", "weather"}]

        results = evaluate_retrieval(labelled, lambda _c: [])
        summary = summarise_retrieval(results, 5)

        # "money" is labelled scheme_discovery; "Who gets farmer money?" reads as eligibility.
        assert summary["intent_cases"] == 1
        assert summary["intent_accuracy"] in (0.0, 1.0)


def answer(*, answerable: bool, source: str | None = None, text: str = "Rs 6000 a year.") -> Answer:
    from app.domain.assistant import AnswerClaim, Citation

    citations = (
        [
            Citation(
                number=1,
                source_id=source,
                title="t",
                authority="a",
                url="https://x.gov.in/",
                passage="p",
                quote="q",
                verification="verified",
                stale=False,
                ocr=False,
            )
        ]
        if source
        else []
    )
    return Answer(
        answerable=answerable,
        language="en",
        text=text,
        claims=[AnswerClaim(text=text, citations=[1])] if source else [],
        citations=citations,
        disclaimer="d",
    )


class TestMeasuringAnswers:
    def test_an_answer_that_cites_a_right_document_is_correct(self, cases: list[Case]) -> None:
        pool = [c for c in cases if c.id == "money"]

        [result] = evaluate_answers(pool, lambda _c: answer(answerable=True, source="kisan"))

        assert (result.correct, result.cited_right_source, result.language_ok) == (True, True, True)

    def test_an_answer_that_cites_a_wrong_document_is_not(self, cases: list[Case]) -> None:
        pool = [c for c in cases if c.id == "money"]

        [result] = evaluate_answers(pool, lambda _c: answer(answerable=True, source="other"))

        assert result.correct is False

    def test_abstaining_is_right_only_when_the_documents_cannot_answer(
        self, cases: list[Case]
    ) -> None:
        weather = [c for c in cases if c.id == "weather"]
        money = [c for c in cases if c.id == "money"]

        [abstained] = evaluate_answers(weather, lambda _c: answer(answerable=False))
        [wrongly] = evaluate_answers(money, lambda _c: answer(answerable=False))
        [answered] = evaluate_answers(weather, lambda _c: answer(answerable=True, source="kisan"))

        assert (abstained.correct, wrongly.correct, answered.correct) == (True, False, False)

    def test_a_failure_of_the_assistant_is_counted_as_an_error_not_as_a_wrong_answer(
        self, cases: list[Case]
    ) -> None:
        def ask(_case: Case) -> Answer:
            raise AssistantError("busy", code="llm_busy")

        [result] = evaluate_answers([c for c in cases if c.id == "money"], ask)
        summary = summarise_answers([result])

        assert (result.correct, result.error) == (False, "llm_busy")
        assert summary["errors"] == 1
