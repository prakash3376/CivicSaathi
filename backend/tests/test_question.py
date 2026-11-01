import pytest

from app.domain.assistant import Language, LanguageChoice
from app.services.assistant.question import resolve_language, tidy


class TestTidy:
    def test_white_space_is_collapsed_and_trimmed(self) -> None:
        assert tidy("  What  is\n the\tlimit?  ") == "What is the limit?"

    def test_invisible_and_control_characters_are_removed(self) -> None:
        assert tidy("in\N{ZERO WIDTH SPACE}come\x00 li\x07mit") == "income limit"

    def test_text_is_normalised(self) -> None:
        assert tidy("e\N{COMBINING ACUTE ACCENT}") == "\N{LATIN SMALL LETTER E WITH ACUTE}"

    def test_an_empty_or_blank_question_becomes_empty(self) -> None:
        assert tidy("   \n\t ") == ""


class TestResolveLanguage:
    @pytest.mark.parametrize("choice", ["en", "bn", "hi"])
    def test_an_explicit_choice_is_honoured_whatever_the_question_is_written_in(
        self, choice: LanguageChoice
    ) -> None:
        assert resolve_language("বৃত্তির জন্য আয়ের সীমা কত?", choice) == (choice, False)
        assert resolve_language("What is the income limit?", choice) == (choice, False)

    @pytest.mark.parametrize(
        ("question", "expected"),
        [
            ("What is the income limit?", "en"),
            ("বৃত্তির জন্য পারিবারিক আয়ের সীমা কত?", "bn"),
            ("SVMCM scholarship এর জন্য কত নম্বর লাগবে এবং কীভাবে আবেদন করব", "bn"),
            ("छात्रवृत्ति के लिए आय की सीमा क्या है?", "hi"),
            ("SVMCM छात्रवृत्ति के लिए कितने अंक चाहिए और कैसे आवेदन करूँ", "hi"),
            ("mujhe scholarship ke baare mein batao", "en"),  # Hindi in Latin letters
            ("60 2025 1000", "en"),  # no letters at all
        ],
    )
    def test_auto_picks_the_language_of_the_question(
        self, question: str, expected: Language
    ) -> None:
        assert resolve_language(question, "auto") == (expected, False)

    @pytest.mark.parametrize(
        "question",
        [
            "உதவித்தொகைக்கான வருமான வரம்பு என்ன?",  # Tamil
            "શિષ્યવૃત્તિ માટે આવકની મર્યાદા શું છે?",  # Gujarati
        ],
    )
    def test_a_language_we_do_not_offer_is_answered_in_english_and_flagged(
        self, question: str
    ) -> None:
        assert resolve_language(question, "auto") == ("en", True)
