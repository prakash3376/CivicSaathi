import re

import pytest

from app.domain.assistant import Language
from app.services.assistant.messages import MESSAGES, say
from app.services.grounding.language import writes_in

# Every warning code the assistant can give has a message ``warn_<code>`` in each language.
WARNING_CODES = [
    "date_unknown",
    "stale",
    "verification_due",
    "scanned",
    "sanitized",
    "claims_removed",
    "language_fallback",
    "personal_data",
]


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", text))


@pytest.mark.parametrize("language", ["bn", "hi"])
def test_every_language_says_the_same_things(language: Language) -> None:
    assert MESSAGES["en"].keys() == MESSAGES[language].keys()


@pytest.mark.parametrize("language", ["bn", "hi"])
def test_every_language_uses_the_same_placeholders(language: Language) -> None:
    for key, english in MESSAGES["en"].items():
        assert placeholders(english) == placeholders(MESSAGES[language][key]), key


def test_every_warning_the_assistant_gives_has_a_message() -> None:
    for code in WARNING_CODES:
        assert f"warn_{code}" in MESSAGES["en"], code


@pytest.mark.parametrize("key", sorted(MESSAGES["en"]))
def test_each_message_is_written_in_its_language(key: str) -> None:
    assert writes_in(MESSAGES["en"][key], "en"), key
    assert writes_in(MESSAGES["bn"][key], "bn"), key
    assert writes_in(MESSAGES["hi"][key], "hi"), key


def test_no_message_is_left_unfinished() -> None:
    for language in MESSAGES.values():
        for text in language.values():
            assert text.strip()
            assert not re.search(r"TODO|FIXME|XXX", text)


def test_the_english_disclaimer_is_the_one_the_spec_requires() -> None:
    # SPEC rule R6, word for word.
    assert MESSAGES["en"]["disclaimer"] == (
        "Informational summary, not legal advice. Check the official document before acting."
    )


def test_say_fills_in_the_placeholders() -> None:
    text = say("en", "warn_stale", title="Demo Guidelines", date="2024-01-01")

    assert text.startswith("Demo Guidelines is dated 2024-01-01")
    assert "{" not in say("bn", "warn_stale", title="Demo", date="2024-01-01")
    assert "{" not in say("hi", "warn_stale", title="Demo", date="2024-01-01")


def test_a_missing_placeholder_is_an_error_not_a_silent_blank() -> None:
    with pytest.raises(KeyError):
        say("en", "warn_stale", title="Demo")
