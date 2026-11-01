"""Runtime configuration, read from environment variables and an optional ``backend/.env`` file."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
SOURCES_DIR = BACKEND_DIR / "data" / "sources"  # the curated registry of official sources
SCHEMES_DIR = BACKEND_DIR / "data" / "schemes"  # what each scheme requires, as evaluable rules
CATALOGUE_DIR = BACKEND_DIR / "data" / "catalogue"  # programmes and services, read not questioned
BUDGET_DIR = BACKEND_DIR / "data" / "budget"  # what the budget documents allocate, by year

Environment = Literal["development", "test", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Application settings.

    Each field is read from the upper-case environment variable of the same name
    (``app_env`` -> ``APP_ENV``). Real environment variables win over ``backend/.env``.
    To add a setting, add a field here and a documented line to ``backend/.env.example``.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Environment = "development"
    log_level: LogLevel = "INFO"
    # Browser origins allowed to call the API directly: comma-separated, or a JSON list.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # Where downloaded documents, the vector index and the embedding model are kept.
    # A relative path is resolved against the backend folder.
    data_dir: Path = BACKEND_DIR / "storage"
    # The built website (`frontend/dist`). When set, the API serves it too, on the same origin, so
    # that one process is the whole product (a container, a small host). Unset: API only.
    # A relative path is resolved against the backend folder.
    frontend_dir: Path | None = None
    # Multilingual model used to embed passages and questions (Hindi, Bengali, ... and English).
    # Changing it means re-embedding everything: run the ingest command with --rebuild.
    embedding_model: str = "intfloat/multilingual-e5-small"
    # Limits for downloading official documents. 25 MB is the SPEC limit for a document.
    fetch_timeout_seconds: float = Field(default=30.0, gt=0)
    max_document_mb: int = Field(default=25, gt=0)

    # Opens the knowledge-base health page (GET /api/v1/admin/knowledge) to whoever sends it in
    # the X-Admin-Token header. Without it that page does not exist. Never put it in the frontend.
    admin_token: SecretStr | None = None

    # --- Performance. Both default to on; they are switches so that a measurement can compare. ---
    # Reuse what is expensive to compute and has not changed (the list of indexed sources).
    cache_enabled: bool = True
    # Compress JSON replies of 1 KB or more when the client accepts it.
    compress_responses: bool = True
    # Write one line per request (method, route, status, milliseconds). Never the query string.
    access_log: bool = True
    # Failed admin-token attempts one client address may make per minute; 0 switches it off.
    admin_rate_limit_per_minute: int = Field(default=10, ge=0)

    # Largest request body the API reads, in bytes. Every endpoint takes a few hundred bytes.
    max_request_body_bytes: int = Field(default=65_536, ge=1_024)

    # --- AI assistant ---
    # Google Gemini API key. Without one the assistant is off; the rest of the API still works.
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    # Optional: a different API address (a gateway, a regional endpoint, or a test double).
    gemini_base_url: str | None = None
    gemini_timeout_seconds: float = Field(default=45.0, gt=0)
    # The most one question may wait for the model in all, retries included. It stays under the
    # 60 s the browser waits, so that a reply is never produced for a page that has given up.
    gemini_deadline_seconds: float = Field(default=50.0, gt=0)
    # After this many failures in a row (provider down or rate-limited) the model is not asked for
    # the cooldown, and visitors are shown the matching official passages at once.
    llm_breaker_threshold: int = Field(default=5, ge=1)
    llm_breaker_cooldown_seconds: float = Field(default=30.0, gt=0)
    gemini_max_output_tokens: int = Field(default=4096, ge=256)
    # Optional: how hard the model thinks before answering (lower is faster and cheaper).
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] | None = None
    # Longer questions are refused, which also keeps the cost of a request predictable.
    assistant_max_question_chars: int = Field(default=500, ge=20)
    # Questions one client address may ask per minute; 0 switches the limit off.
    assistant_rate_limit_per_minute: int = Field(default=20, ge=0)

    @field_validator("data_dir")
    @classmethod
    def resolve_data_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator("frontend_dir")
    @classmethod
    def resolve_frontend_dir(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator(
        "gemini_api_key",
        "admin_token",
        "gemini_base_url",
        "gemini_thinking_level",
        "frontend_dir",
        mode="before",
    )
    @classmethod
    def blank_means_unset(cls, value: Any) -> Any:
        """A line such as ``GEMINI_API_KEY=`` in .env is "not set", not an empty key."""
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalise_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            value = json.loads(value) if value.startswith("[") else value.split(",")
        if isinstance(value, list):
            # Browsers send origins without a trailing slash, so normalise before matching.
            cleaned = [
                item.strip().rstrip("/") if isinstance(item, str) else item for item in value
            ]
            return [item for item in cleaned if item != ""]
        return value

    @model_validator(mode="after")
    def reject_wildcard_cors_in_production(self) -> Self:
        if self.is_production and "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must list explicit origins in production, not '*'")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        """The interactive API docs are served everywhere except production."""
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return Settings()
