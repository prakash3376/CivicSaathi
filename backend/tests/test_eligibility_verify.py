from pathlib import Path

import pytest

from app import cli
from app.core.config import get_settings
from app.domain.eligibility import FieldDef, LocalText
from app.services.eligibility.formatting import describe_answer, format_number
from app.services.eligibility.loader import SchemeBook, load_schemes
from app.services.eligibility.verify import all_evidence, check_evidence
from app.services.ingestion.registry import load_registry


@pytest.fixture(scope="module")
def book() -> SchemeBook:
    return load_schemes(sources={spec.id: spec.url for spec in load_registry()})


class TestFormatNumber:
    @pytest.mark.parametrize(
        ("value", "shown"),
        [
            (0, "0"),
            (999, "999"),
            (1000, "1,000"),
            (250000, "2,50,000"),
            (800000, "8,00,000"),
            (1234567, "12,34,567"),
            (123456789, "12,34,56,789"),
            (60.0, "60"),
            (59.5, "59.5"),
            (1500.25, "1,500.25"),
            (-250000, "-2,50,000"),
        ],
    )
    def test_indian_grouping_without_a_needless_decimal(self, value: float, shown: str) -> None:
        assert format_number(value) == shown


class TestDescribeAnswer:
    FIELD = FieldDef.model_validate(
        {
            "id": "x",
            "type": "number",
            "question": {"en": "Q?", "bn": "প্রশ্ন?", "hi": "प्रश्न?"},
            "display": {
                "en": "Rs {value} a year",
                "bn": "বছরে {value} টাকা",
                "hi": "प्रति वर्ष {value} रुपये",
            },
        }
    )
    PLAIN = FieldDef.model_validate(
        {"id": "x", "type": "number", "question": {"en": "Q?", "bn": "প্রশ্ন?", "hi": "प्रश्न?"}}
    )
    CHOICE = FieldDef.model_validate(
        {
            "id": "x",
            "type": "choice",
            "question": {"en": "Q?", "bn": "প্রশ্ন?", "hi": "प्रश्न?"},
            "choices": [{"id": "a", "label": {"en": "Option A", "bn": "বিকল্প ক", "hi": "विकल्प क"}}],
        }
    )

    def test_yes_and_no_in_both_languages(self) -> None:
        assert describe_answer(self.FIELD, True) == LocalText(en="Yes", bn="হ্যাঁ", hi="हाँ")
        assert describe_answer(self.FIELD, False) == LocalText(en="No", bn="না", hi="नहीं")

    def test_a_number_uses_the_fields_template(self) -> None:
        shown = describe_answer(self.FIELD, 250000)

        assert shown.en == "Rs 2,50,000 a year"
        assert shown.bn == "বছরে 2,50,000 টাকা"

    def test_a_number_without_a_template_is_shown_plainly(self) -> None:
        assert describe_answer(self.PLAIN, 72.5) == LocalText(en="72.5", bn="72.5", hi="72.5")

    def test_a_choice_shows_its_label(self) -> None:
        assert describe_answer(self.CHOICE, "a").bn == "বিকল্প ক"


class TestCheckEvidence:
    def test_every_scheme_has_quotes_to_check(self, book: SchemeBook) -> None:
        assert all(list(all_evidence(scheme)) for scheme in book.schemes)

    def test_labels_say_what_each_quote_is_for(self, book: SchemeBook) -> None:
        labels = {label for scheme in book.schemes for label, _ in all_evidence(scheme)}

        assert "criterion income" in labels
        assert "apply" in labels
        assert "benefit of ug" in labels

    def test_documents_that_contain_every_quote_leave_no_problem(self, book: SchemeBook) -> None:
        everything = {
            evidence.source_id: " ".join(
                e.quote
                for s in book.schemes
                for _, e in all_evidence(s)
                if e.source_id == evidence.source_id
            )
            for scheme in book.schemes
            for _, evidence in all_evidence(scheme)
        }

        assert check_evidence(book, everything.get) == []

    def test_a_document_that_is_not_indexed_is_reported_by_name(self, book: SchemeBook) -> None:
        problems = check_evidence(book, lambda _source: None)

        assert problems
        assert all("is not indexed" in problem for problem in problems)

    def test_a_quote_the_document_no_longer_contains_is_reported(self, book: SchemeBook) -> None:
        problems = check_evidence(book, lambda _source: "The document was rewritten entirely.")

        assert problems
        assert all("not found in" in problem for problem in problems)

    def test_quotes_are_found_across_line_breaks_and_spacing(self, book: SchemeBook) -> None:
        def rewrapped(source_id: str) -> str:
            quotes = [
                e.quote
                for s in book.schemes
                for _, e in all_evidence(s)
                if e.source_id == source_id
            ]
            return "\n".join(" ".join(quote.split()).replace(" ", "  \n ", 1) for quote in quotes)

        assert check_evidence(book, rewrapped) == []


class TestTheSchemesCommands:
    @pytest.fixture(autouse=True)
    def _data_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        get_settings.cache_clear()
        yield  # type: ignore[misc]
        get_settings.cache_clear()

    def test_schemes_lists_every_scheme_with_its_tracks(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cli.main(["schemes"]) == 0

        output = capsys.readouterr().out
        assert "aicte-pragati" in output
        assert "svmcm" in output
        for track in ("degree", "diploma", "hs", "ug", "pg", "pg-k3"):
            assert track in output

    def test_schemes_check_fails_when_the_documents_are_not_indexed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cli.main(["schemes-check"]) == 1

        output = capsys.readouterr().out
        assert "is not indexed" in output
        assert "problems." in output
