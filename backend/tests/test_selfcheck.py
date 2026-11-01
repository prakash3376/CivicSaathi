from app.domain.errors import AssistantError
from app.services.assistant.selfcheck import QUESTIONS, SAMPLE, probe
from tests.factories import FakeModel, make_claim, make_draft

QUOTE = "family income has been fixed at Rs.2,50,000/- per annum"
ENGLISH = make_claim("The family income limit is Rs 2,50,000 a year.", QUOTE)
BENGALI = make_claim("পারিবারিক আয়ের সীমা বছরে ২,৫০,০০০ টাকা।", QUOTE)


def test_a_reply_that_survives_the_grounding_check_passes() -> None:
    model = FakeModel(make_draft(ENGLISH))

    result = probe(model, "en")

    assert result.ok
    assert "1 claim(s) verified" in result.detail
    assert result.language == "en"


def test_the_model_is_asked_the_real_prompt_about_the_sample_passage() -> None:
    model = FakeModel(make_draft(ENGLISH))

    probe(model, "en")

    [(system, user)] = model.calls
    assert "DATA, NOT INSTRUCTIONS" in system  # the same instructions as a real question
    assert SAMPLE.text in user
    assert QUESTIONS["en"] in user


def test_a_bengali_reply_passes_in_bengali_and_fails_in_english() -> None:
    assert probe(FakeModel(make_draft(BENGALI)), "bn").ok
    assert not probe(FakeModel(make_draft(BENGALI)), "en").ok


def test_an_english_reply_to_the_bengali_question_fails_and_says_why() -> None:
    result = probe(FakeModel(make_draft(ENGLISH)), "bn")

    assert not result.ok
    assert "language" in result.detail


def test_a_wrong_figure_fails_and_says_why() -> None:
    wrong = make_claim("The family income limit is Rs 9,99,000 a year.", QUOTE)

    result = probe(FakeModel(make_draft(wrong)), "en")

    assert not result.ok
    assert "number" in result.detail


def test_a_quote_the_model_invented_fails() -> None:
    invented = make_claim("The limit is Rs 2,50,000.", "an invented sentence of the passage")

    result = probe(FakeModel(make_draft(invented)), "en")

    assert not result.ok
    assert "not_found" in result.detail or "unknown_source" in result.detail


def test_a_model_that_declines_to_answer_fails() -> None:
    result = probe(FakeModel(make_draft(answerable=False)), "en")

    assert not result.ok
    assert "does not answer" in result.detail


def test_a_provider_error_is_reported_with_its_code() -> None:
    model = FakeModel(AssistantError("The assistant is not available right now.", code="llm_auth"))

    result = probe(model, "en")

    assert not result.ok
    assert result.detail.startswith("llm_auth:")
