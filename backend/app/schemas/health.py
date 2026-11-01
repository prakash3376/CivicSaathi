from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(description="'ok' whenever the API is up and serving requests.")
    service: str
    version: str
    environment: str
    timestamp: datetime = Field(description="Server time (UTC) when the check ran.")
    uptime_seconds: float = Field(ge=0, description="Seconds since the API process started.")


class ComponentStatus(BaseModel):
    status: Literal["ok", "degraded", "down", "off"] = Field(
        description="ok: working. degraded: limited. down: not working. off: switched off."
    )
    detail: str | None = Field(default=None, description="A short, safe explanation for operators.")


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"] = Field(
        description=(
            "ok: everything works. degraded: the site works and one part is limited or off (for "
            "example the language model). unavailable: the records that browsing and eligibility "
            "need cannot be loaded (HTTP 503)."
        )
    )
    timestamp: datetime
    components: dict[str, ComponentStatus]
