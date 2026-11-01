from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import BACKEND_DIR, Settings
from app.main import create_app


def test_defaults_suit_local_development(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_ENV", "LOG_LEVEL", "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert "http://localhost:5173" in settings.cors_origins
    assert settings.docs_enabled


def test_cors_origins_accept_comma_separated_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example/ ,https://b.example,, ")

    assert Settings(_env_file=None).cors_origins == ["https://a.example", "https://b.example"]


def test_cors_origins_accept_a_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example", "https://b.example/"]')

    assert Settings(_env_file=None).cors_origins == ["https://a.example", "https://b.example"]


def test_log_level_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert Settings(_env_file=None).log_level == "DEBUG"


def test_unknown_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_wildcard_cors_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(_env_file=None, app_env="production", cors_origins=["*"])


def test_data_settings_have_sensible_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATA_DIR", "EMBEDDING_MODEL", "FETCH_TIMEOUT_SECONDS", "MAX_DOCUMENT_MB"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.data_dir == BACKEND_DIR / "storage"
    assert settings.embedding_model == "intfloat/multilingual-e5-small"
    assert settings.fetch_timeout_seconds == 30
    assert settings.max_document_mb == 25  # the SPEC limit for a document


def test_a_relative_data_dir_is_resolved_against_the_backend_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", "var/data")

    assert Settings(_env_file=None).data_dir == (BACKEND_DIR / "var" / "data").resolve()


def test_an_absolute_data_dir_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    assert Settings(_env_file=None).data_dir == tmp_path


@pytest.mark.parametrize(
    ("name", "value"), [("FETCH_TIMEOUT_SECONDS", "0"), ("MAX_DOCUMENT_MB", "-1")]
)
def test_limits_must_be_positive(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


ASSISTANT_VARIABLES = (
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_BASE_URL",
    "GEMINI_TIMEOUT_SECONDS",
    "GEMINI_MAX_OUTPUT_TOKENS",
    "GEMINI_THINKING_LEVEL",
    "ASSISTANT_MAX_QUESTION_CHARS",
    "ASSISTANT_RATE_LIMIT_PER_MINUTE",
)


def test_the_assistant_is_off_by_default_with_safe_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ASSISTANT_VARIABLES:
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.gemini_api_key is None
    assert settings.gemini_base_url is None
    assert settings.gemini_thinking_level is None
    assert settings.gemini_timeout_seconds == 45
    assert settings.gemini_max_output_tokens == 4096
    assert settings.assistant_max_question_chars == 500
    assert settings.assistant_rate_limit_per_minute == 20


@pytest.mark.parametrize("name", ["GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_THINKING_LEVEL"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_line_in_the_env_file_means_not_set(
    monkeypatch: pytest.MonkeyPatch, name: str, blank: str
) -> None:
    monkeypatch.setenv(name, blank)

    settings = Settings(_env_file=None)

    assert settings.gemini_api_key is None
    assert settings.gemini_base_url is None
    assert settings.gemini_thinking_level is None


def test_the_api_key_never_appears_when_settings_are_printed_or_dumped() -> None:
    settings = Settings(_env_file=None, gemini_api_key="AIzaSy-very-secret")

    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "AIzaSy-very-secret"
    for rendering in (repr(settings), str(settings), settings.model_dump_json()):
        assert "very-secret" not in rendering


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GEMINI_TIMEOUT_SECONDS", "0"),
        ("GEMINI_MAX_OUTPUT_TOKENS", "100"),
        ("GEMINI_THINKING_LEVEL", "extreme"),
        ("ASSISTANT_MAX_QUESTION_CHARS", "5"),
        ("ASSISTANT_RATE_LIMIT_PER_MINUTE", "-1"),
    ],
)
def test_assistant_limits_are_validated(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_a_thinking_level_and_a_zero_rate_limit_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "low")
    monkeypatch.setenv("ASSISTANT_RATE_LIMIT_PER_MINUTE", "0")

    settings = Settings(_env_file=None)

    assert settings.gemini_thinking_level == "low"
    assert settings.assistant_rate_limit_per_minute == 0


class TestEnvExample:
    """backend/.env.example is the documentation of the settings, so it must stay complete."""

    path = BACKEND_DIR / ".env.example"

    def test_every_setting_has_a_line_in_it(self) -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        documented = {line.split("=")[0] for line in lines if "=" in line and line[0] != "#"}

        missing = {name.upper() for name in Settings.model_fields} - documented

        assert not missing, f"add these to backend/.env.example: {sorted(missing)}"

    def test_the_example_loads_and_means_the_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in Settings.model_fields:
            monkeypatch.delenv(name.upper(), raising=False)

        from_example = Settings(_env_file=self.path)

        assert from_example == Settings(_env_file=None)

    def test_it_holds_no_real_key(self) -> None:
        text = self.path.read_text(encoding="utf-8")

        assert "AIza" not in text  # the prefix of every Google API key

    def test_the_privacy_trade_off_of_the_free_tier_is_explained(self) -> None:
        assert "free tier" in self.path.read_text(encoding="utf-8")


def test_production_hides_the_interactive_docs() -> None:
    settings = Settings(
        _env_file=None, app_env="production", cors_origins=["https://civicsaathi.example"]
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/api/v1/openapi.json").status_code == 404
        assert "docs" not in client.get("/").json()
