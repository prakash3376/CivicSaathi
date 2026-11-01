from pathlib import Path

import pytest

from app.domain.errors import SchemeDataError
from app.services.eligibility.loader import SchemeBook, load_schemes

SOURCES = {
    "demo-guidelines": "https://demo.gov.in/guide.pdf",
    "demo-notice": "https://demo.gov.in/n.pdf",
}

FIELDS = """
[[fields]]
id = "income"
type = "number"
integer = true
minimum = 0
question = { en = "Income?", bn = "আয়?", hi = "আয়?" }
display = { en = "Rs {value}", bn = "{value} টাকা", hi = "{value} টাকা" }

[[fields]]
id = "resident"
type = "yes_no"
question = { en = "Resident?", bn = "বাসিন্দা?", hi = "বাসিন্দা?" }

[[fields]]
id = "how"
type = "choice"
question = { en = "How?", bn = "কীভাবে?", hi = "কীভাবে?" }
choices = [
  { id = "a", label = { en = "A", bn = "ক", hi = "ক" } },
  { id = "b", label = { en = "B", bn = "খ", hi = "খ" } },
]
"""

SCHEME = """
id = "demo"
name = "Demo Scheme"
authority = "Department of Demos"
level = "state"
state = "Demo State"
sectors = ["education"]
source_ids = ["demo-guidelines", "demo-notice"]
summary = { en = "A scheme for demos.", bn = "ডেমোর জন্য একটি প্রকল্প।", hi = "ডেমোর জন্য একটি প্রকল্প।" }

[[criteria]]
id = "income"
label = { en = "Your income is less than Rs 8,00,000", bn = "আপনার আয় 8,00,000 টাকার কম", hi = "আপনার আয় 8,00,000 টাকার কম" }
condition = { field = "income", op = "lt", value = 800000 }
evidence = [{ source_id = "demo-guidelines", quote = "Family income should be less than Rs. 8 Lakh per annum." }]

[[criteria]]
id = "resident"
label = { en = "You live in the state", bn = "আপনি রাজ্যের বাসিন্দা", hi = "আপনি রাজ্যের বাসিন্দা" }
condition = { field = "resident", op = "eq", value = true }
evidence = [{ source_id = "demo-guidelines", quote = "Applicants must be residents of the State." }]

[[criteria]]
id = "how"
label = { en = "You joined in a usual way", bn = "আপনি সাধারণ পথে ভর্তি হয়েছেন", hi = "আপনি সাধারণ পথে ভর্তি হয়েছেন" }
condition = { field = "how", op = "in", value = ["a", "b"] }
evidence = [{ source_id = "demo-guidelines", quote = "Students may be admitted in either of two ways." }]

[[documents]]
id = "photo"
label = { en = "A photograph", bn = "একটি ছবি", hi = "একটি ছবি" }
evidence = [{ source_id = "demo-guidelines", quote = "Attach one recent passport size photograph." }]

[[contacts]]
id = "mail"
label = { en = "Help desk", bn = "সহায়তা", hi = "সহায়তা" }
value = "help@demo.gov.in"
evidence = [{ source_id = "demo-guidelines", quote = "Write to help@demo.gov.in for any query." }]

[[deadlines]]
id = "close"
label = { en = "Last date", bn = "শেষ তারিখ", hi = "শেষ তারিখ" }
on = 2026-10-31
scanned = true
evidence = [{ source_id = "demo-notice", quote = "last date for applications is 31 .10.2026" }]

[apply]
text = { en = "Apply online.", bn = "অনলাইনে আবেদন করুন।", hi = "অনলাইনে আবেদন করুন।" }
url = "https://demo.gov.in"
evidence = [{ source_id = "demo-guidelines", quote = "Applications must be submitted online." }]

[[tracks]]
id = "main"
label = { en = "Main", bn = "মূল", hi = "মূল" }

[tracks.benefit]
text = { en = "Rs 50,000 a year.", bn = "বছরে 50,000 টাকা।", hi = "বছরে 50,000 টাকা।" }
evidence = [{ source_id = "demo-guidelines", quote = "The scholarship is Rs. 50,000 per annum." }]
"""


def load(
    tmp_path: Path, *changes: tuple[str, str], scheme: str = SCHEME, fields: str = FIELDS
) -> SchemeBook:
    for old, new in changes:
        assert old in scheme, f"the test's change does not apply: {old!r}"
        scheme = scheme.replace(old, new)
    (tmp_path / "fields.toml").write_text(fields, encoding="utf-8")
    (tmp_path / "demo.toml").write_text(scheme, encoding="utf-8")
    return load_schemes(tmp_path, sources=SOURCES)


def refused(tmp_path: Path, *changes: tuple[str, str], **options: str) -> str:
    with pytest.raises(SchemeDataError) as error:
        load(tmp_path, *changes, **options)
    return error.value.message


class TestAValidScheme:
    def test_it_loads(self, tmp_path: Path) -> None:
        book = load(tmp_path)

        [scheme] = book.schemes
        assert scheme.id == "demo"
        assert book.scheme("demo") is scheme
        assert book.scheme("nope") is None
        assert scheme.sectors == ["education"]

    def test_a_scheme_names_its_sector_and_only_a_known_one(self, tmp_path: Path) -> None:
        message = refused(tmp_path, ('sectors = ["education"]', 'sectors = ["astrology"]'))

        assert "sector" in message

    def test_a_scheme_without_a_sector_is_refused(self, tmp_path: Path) -> None:
        assert "sector" in refused(tmp_path, ('sectors = ["education"]\n', ""))

    def test_questions_follow_the_criteria_once_each(self, tmp_path: Path) -> None:
        book = load(tmp_path)
        [scheme] = book.schemes

        assert [q.field for q in book.questions(scheme, scheme.tracks[0])] == [
            "income",
            "resident",
            "how",
        ]

    def test_a_criterion_can_word_its_own_question(self, tmp_path: Path) -> None:
        asked = ('condition = { field = "income", op = "lt", value = 800000 }',
                 'condition = { field = "income", op = "lt", value = 800000 }\n'
                 'ask = { en = "What did your family earn?", bn = "পরিবারের আয় কত?", hi = "পরিবারের আয় কত?" }')  # fmt: skip
        book = load(tmp_path, asked)
        [scheme] = book.schemes

        [income, *_] = book.questions(scheme, scheme.tracks[0])

        assert income.text.en == "What did your family earn?"

    def test_a_number_may_be_written_in_words_in_the_quote(self, tmp_path: Path) -> None:
        changes = (
            ('condition = { field = "income", op = "lt", value = 800000 }',
             'condition = { field = "income", op = "lte", value = 2 }'),
            ('Rs 8,00,000', 'two'),
            ('8,00,000 টাকার কম', 'দুই'),
            ('Family income should be less than Rs. 8 Lakh per annum.',
             'Up to Two Girls per family.'),
        )  # fmt: skip

        assert load(tmp_path, *changes).schemes

    def test_a_deadline_quote_from_a_scan_need_not_match_its_date_figure_for_figure(
        self, tmp_path: Path
    ) -> None:
        # The quote has "31 .10.2026" as OCR read it; only its presence is checked.
        assert load(tmp_path).schemes[0].deadlines[0].scanned

    def test_an_address_on_a_sources_own_host_is_fine_without_a_quote(self, tmp_path: Path) -> None:
        assert load(tmp_path).schemes[0].apply.url == "https://demo.gov.in"

    def test_an_address_in_the_quote_is_fine_on_any_host(self, tmp_path: Path) -> None:
        changes = (
            ('url = "https://demo.gov.in"', 'url = "https://portal.gov.in"'),
            (
                "Applications must be submitted online.",
                "Apply at https://portal.gov.in/apply today.",
            ),
        )

        assert load(tmp_path, *changes).schemes[0].apply.url == "https://portal.gov.in"


class TestNumbersAreSacred:
    def test_a_figure_in_the_english_wording_that_the_quote_does_not_state(
        self, tmp_path: Path
    ) -> None:
        message = refused(tmp_path, ("less than Rs 8,00,000", "less than Rs 7,00,000"))

        assert "English wording" in message
        assert "number" in message
        assert "demo / main.income" in message

    def test_a_figure_in_the_bengali_wording_that_the_quote_does_not_state(
        self, tmp_path: Path
    ) -> None:
        assert "Bengali wording" in refused(tmp_path, ("8,00,000 টাকার কম", "9,00,000 টাকার কম"))

    def test_a_figure_in_the_hindi_wording_that_the_quote_does_not_state(
        self, tmp_path: Path
    ) -> None:
        message = refused(
            tmp_path,
            (
                'bn = "আপনার আয় 8,00,000 টাকার কম", hi = "আপনার আয় 8,00,000 টাকার কম"',
                'bn = "আপনার আয় 8,00,000 টাকার কম", hi = "आपकी आय 9,00,000 रुपये से कम है"',
            ),
        )

        assert "Hindi" in message
        assert "9,00,000" in message

    def test_bengali_digits_are_read_as_the_same_figure(self, tmp_path: Path) -> None:
        assert load(tmp_path, ("8,00,000 টাকার কম", "৮,০০,০০০ টাকার কম")).schemes

    def test_the_value_a_rule_compares_with_must_be_in_its_quote(self, tmp_path: Path) -> None:
        message = refused(tmp_path, ("value = 800000", "value = 700000"))

        assert "700000" in message
        assert "not in its quote" in message

    def test_a_month_the_quote_does_not_contain(self, tmp_path: Path) -> None:
        message = refused(tmp_path, ("You live in the state", "You lived here by 5 November"))

        assert "month" in message

    def test_a_benefit_amount_must_match_its_quote(self, tmp_path: Path) -> None:
        assert "benefit main" in refused(tmp_path, ("Rs 50,000 a year.", "Rs 60,000 a year."))

    def test_a_contact_must_be_exactly_what_the_document_says(self, tmp_path: Path) -> None:
        assert "contact mail" in refused(
            tmp_path, ('value = "help@demo.gov.in"', 'value = "help@demo.gov.org"')
        )

    def test_a_summary_may_state_no_figure(self, tmp_path: Path) -> None:
        message = refused(tmp_path, ("A scheme for demos.", "A scheme paying Rs 5,000."))

        assert "summary" in message


class TestEvidence:
    def test_a_quote_too_short_to_mean_anything(self, tmp_path: Path) -> None:
        assert "too short" in refused(
            tmp_path, ("Applicants must be residents of the State.", "Residents.")
        )

    def test_a_rule_with_no_evidence_at_all(self, tmp_path: Path) -> None:
        message = refused(
            tmp_path,
            ('evidence = [{ source_id = "demo-guidelines", quote = "Applicants must be residents of the State." }]',
             "evidence = []"),
        )  # fmt: skip

        assert "evidence" in message

    def test_a_quote_from_a_source_the_scheme_does_not_use(self, tmp_path: Path) -> None:
        scheme = SCHEME.replace(
            'source_ids = ["demo-guidelines", "demo-notice"]', 'source_ids = ["demo-guidelines"]'
        )
        # the deadline cites demo-notice, which is now not one of its sources

        assert "not one of its sources" in refused(tmp_path, scheme=scheme)

    def test_a_source_that_is_not_in_the_registry(self, tmp_path: Path) -> None:
        assert "not in the source registry" in refused(
            tmp_path,
            (
                'source_ids = ["demo-guidelines", "demo-notice"]',
                'source_ids = ["demo-guidelines", "ghost"]',
            ),
        )


class TestRulesAreWellFormed:
    def test_a_field_that_does_not_exist(self, tmp_path: Path) -> None:
        assert "'ghost' is not defined" in refused(
            tmp_path, ('field = "resident"', 'field = "ghost"')
        )

    def test_a_number_compared_with_text(self, tmp_path: Path) -> None:
        assert "needs a numeric comparison" in refused(
            tmp_path, ("value = 800000", 'value = "lots"')
        )

    def test_a_yes_or_no_compared_with_an_order(self, tmp_path: Path) -> None:
        assert "yes or no" in refused(
            tmp_path, ('field = "resident", op = "eq"', 'field = "resident", op = "lt"')
        )

    def test_a_yes_or_no_compared_with_a_number(self, tmp_path: Path) -> None:
        assert "yes or no" in refused(tmp_path, ('op = "eq", value = true', 'op = "eq", value = 1'))

    def test_a_choice_that_is_not_one_of_the_choices(self, tmp_path: Path) -> None:
        assert "only has the choices" in refused(
            tmp_path, ('value = ["a", "b"]', 'value = ["a", "zzz"]')
        )

    def test_a_choice_compared_with_an_order(self, tmp_path: Path) -> None:
        assert "only has the choices" in refused(
            tmp_path,
            (
                'field = "how", op = "in", value = ["a", "b"]',
                'field = "how", op = "gt", value = "a"',
            ),
        )

    def test_in_with_a_single_value(self, tmp_path: Path) -> None:
        assert "does not go with" in refused(
            tmp_path, ('op = "in", value = ["a", "b"]', 'op = "in", value = "a"')
        )

    def test_two_criteria_with_one_id(self, tmp_path: Path) -> None:
        assert "same id" in refused(tmp_path, ('id = "resident"', 'id = "income"'))

    def test_a_track_omitting_something_that_is_not_common(self, tmp_path: Path) -> None:
        assert "not a common rule" in refused(
            tmp_path, ('id = "main"', 'id = "main"\nomit_common = ["ghost"]')
        )

    def test_an_address_that_is_not_https(self, tmp_path: Path) -> None:
        assert "https" in refused(
            tmp_path, ('url = "https://demo.gov.in"', 'url = "http://demo.gov.in"')
        )

    def test_an_address_that_is_neither_on_a_source_host_nor_quoted(self, tmp_path: Path) -> None:
        assert "neither on a source's host" in refused(
            tmp_path, ('url = "https://demo.gov.in"', 'url = "https://elsewhere.example"')
        )

    def test_a_misspelt_key_is_not_ignored(self, tmp_path: Path) -> None:
        message = refused(tmp_path, ('id = "photo"', 'id = "photo"\nlabell = "oops"'))

        assert "demo.toml" in message
        assert "labell" in message

    def test_a_missing_bengali_text(self, tmp_path: Path) -> None:
        assert "bn" in refused(tmp_path, ('bn = "একটি ছবি", hi = "একটি ছবি"', 'bn = ""'))

    def test_broken_toml(self, tmp_path: Path) -> None:
        assert "could not be read" in refused(tmp_path, scheme="id = [unclosed")

    def test_two_schemes_with_one_id(self, tmp_path: Path) -> None:
        load(tmp_path)
        (tmp_path / "copy.toml").write_text(SCHEME, encoding="utf-8")

        with pytest.raises(SchemeDataError, match="another scheme already has the id"):
            load_schemes(tmp_path, sources=SOURCES)


class TestFields:
    def test_a_choice_without_choices(self, tmp_path: Path) -> None:
        fields = FIELDS.replace(
            'choices = [\n  { id = "a", label = { en = "A", bn = "ক", hi = "ক" } },\n  { id = "b", label = { en = "B", bn = "খ", hi = "খ" } },\n]\n',
            "",
        )

        assert "has no choices" in refused(tmp_path, fields=fields)

    def test_a_field_defined_twice(self, tmp_path: Path) -> None:
        assert "defined twice" in refused(tmp_path, fields=FIELDS + FIELDS)
