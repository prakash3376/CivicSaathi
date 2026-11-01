"""What the API needs from the assistant, in a module that is cheap to import.

The API imports this when it starts. The assistant itself (ChromaDB, the embedding model, the
Gemini SDK) takes about two seconds to import and is needed only when the first question or the
first list of sources arrives, so ``app.services.assistant.factory`` is imported then. That keeps
every server start and every ``--reload`` quick, and means a broken install of one of those
libraries cannot stop ``/health`` from answering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.assistant.catalog import SourceCatalog
    from app.services.assistant.service import AssistantService


@dataclass(frozen=True)
class AssistantRuntime:
    """Something to answer questions and something to list the sources."""

    service: AssistantService
    catalog: SourceCatalog
