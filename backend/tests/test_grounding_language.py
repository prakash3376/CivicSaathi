import pytest

from app.domain.assistant import Language
from app.services.grounding.language import writes_in

ENGLISH = "Your family income must stay below the yearly limit."
BENGALI = "পারিবারিক আয় বছরে আড়াই লাখ টাকার বেশি হতে পারবে না।"
HINDI = "आपकी पारिवारिक आय सीमा से कम होनी चाहिए।"


@pytest.mark.parametrize(
    ("text", "language", "expected"),
    [
        (ENGLISH, "en", True),
        (ENGLISH, "bn", False),
        (BENGALI, "bn", True),
        (BENGALI, "en", False),
        (HINDI, "hi", True),
        (HINDI, "en", False),
        (HINDI, "bn", False),
        (BENGALI, "hi", False),
        (ENGLISH, "hi", False),
        ("SVMCM के लिए 60% अंक चाहिए।", "hi", True),  # an acronym inside Hindi
        ("SVMCM-এ আবেদন করতে ৬০% নম্বর লাগবে।", "bn", True),  # an acronym inside Bengali
        ("The SVMCM scheme asks for 60% marks (Rs.2,50,000).", "en", True),
    ],
)
def test_a_statement_is_judged_by_its_letters(
    text: str, language: Language, expected: bool
) -> None:
    assert writes_in(text, language) is expected


@pytest.mark.parametrize("language", ["en", "bn", "hi"])
@pytest.mark.parametrize("text", ["", "60%", "UG 60%", "Rs.2,50,000/-", "SVMCM"])
def test_a_statement_with_hardly_any_letters_fits_any_language(
    text: str, language: Language
) -> None:
    assert writes_in(text, language)
