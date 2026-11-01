from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceFormat = Literal["pdf", "html"]
DocumentType = Literal[
    "guidelines",
    "faq",
    "notification",
    "scheme_page",
    "service_page",
    "budget",
    "circular",
]
SchemeLevel = Literal["central", "state"]


class SourceSpec(BaseModel):
    """One curated official source: a document we ingest, and what it must look like.

    Entries live in ``backend/data/sources/*.toml``. A person adds one only after opening the URL
    and confirming it is the real document; the pipeline then re-checks it on every run.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]{2,62}$",
        description="Stable slug, used in storage paths and chunk ids.",
    )
    title: str = Field(min_length=3)
    scheme: str = Field(min_length=3)
    authority: str = Field(min_length=3, description="The issuing body, as the document names it.")
    level: SchemeLevel
    state: str | None = Field(default=None, description="Required for state-level schemes.")
    doc_type: DocumentType
    format: SourceFormat
    url: str
    languages: tuple[str, ...] = ("en",)
    content_selector: str | None = Field(
        default=None, description="CSS selector for the main content of an HTML page."
    )
    expected_phrases: tuple[str, ...] = Field(
        default=(),
        description="Identity phrases that must appear in the text, or the source is rejected.",
    )
    expected_facts: tuple[str, ...] = Field(
        default=(),
        description="Key figures a person confirmed; if one disappears the source is flagged.",
    )
    published_on: date | None = Field(
        default=None,
        description="Date printed on the document, when it has no machine-readable one.",
    )
    legacy_tls: bool = Field(
        default=False,
        description=(
            "Connect to a server that lacks secure TLS renegotiation (RFC 5746), which modern "
            "OpenSSL refuses. The certificate and hostname are still verified. Use it only for a "
            "known official server that cannot be fixed, and say why in notes."
        ),
    )
    curated_on: date = Field(description="When a person last confirmed this entry.")
    notes: str = ""

    @field_validator("url")
    @classmethod
    def require_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("url must start with https://")
        return value

    @model_validator(mode="after")
    def require_state_for_state_schemes(self) -> Self:
        if self.level == "state" and not self.state:
            raise ValueError("state-level sources must name their state")
        return self
