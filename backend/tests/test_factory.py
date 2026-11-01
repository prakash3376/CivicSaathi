from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.domain.errors import AssistantError
from app.services.assistant import factory
from app.services.assistant.factory import build_model, build_runtime
from app.services.llm.resilient import GuardedModel


def settings_for(tmp_path: Path, **overrides: Any) -> Settings:
    return Settings(_env_file=None, app_env="test", data_dir=tmp_path, **overrides)


def test_without_an_api_key_there_is_no_model(tmp_path: Path) -> None:
    assert build_model(settings_for(tmp_path)) is None


def test_the_settings_reach_the_gemini_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: dict[str, Any] = {}

    class RecordingClient:
        def __init__(self, **options: Any) -> None:
            received.update(options)

    monkeypatch.setattr(factory, "GeminiClient", RecordingClient)
    settings = settings_for(
        tmp_path,
        gemini_api_key="the-key",
        gemini_model="gemini-x",
        gemini_base_url="https://gateway.example",
        gemini_timeout_seconds=12,
        gemini_max_output_tokens=2048,
        gemini_thinking_level="low",
    )

    model = build_model(settings)

    assert isinstance(model, GuardedModel)  # the model sits behind a circuit breaker
    assert isinstance(model.inner, RecordingClient)

    assert received == {
        "api_key": "the-key",  # the real value, not the SecretStr wrapper
        "model": "gemini-x",
        "base_url": "https://gateway.example",
        "timeout_seconds": 12,
        "deadline_seconds": 50.0,
        "max_output_tokens": 2048,
        "thinking_level": "low",
    }


def test_a_blank_api_key_in_the_environment_means_no_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    assert build_model(settings_for(tmp_path)) is None


def test_building_the_runtime_needs_neither_a_key_nor_an_embedding_model(tmp_path: Path) -> None:
    runtime = build_runtime(settings_for(tmp_path))  # downloads nothing, loads nothing

    assert runtime.catalog.sources() == []
    with pytest.raises(AssistantError) as error:
        runtime.service.ask("What is the income limit?")
    assert error.value.code == "assistant_not_configured"


def test_the_question_length_limit_comes_from_the_settings(tmp_path: Path) -> None:
    runtime = build_runtime(settings_for(tmp_path, assistant_max_question_chars=30))

    with pytest.raises(AssistantError) as error:
        runtime.service.ask("x " * 40)

    assert error.value.code == "question_too_long"
