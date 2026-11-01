"""Putting the real pieces together: the index, the embedding model, the registry and Gemini.

Nothing here runs when the application starts. The assistant is built on the first request that
needs it, so a missing index or API key can never stop the rest of the API (the health check, for
one) from working. Building does not download anything either: the embedding model is fetched by
the ingest command, and a question asked before that fails with a clear message.
"""

import logging

from app.core.config import Settings
from app.domain.errors import SchemeDataError
from app.services.assistant.catalog import SourceCatalog
from app.services.assistant.runtime import AssistantRuntime
from app.services.assistant.search import KnowledgeSearch
from app.services.assistant.service import AssistantService
from app.services.catalogue.loader import load_budget, load_catalogue
from app.services.ingestion.registry import load_registry
from app.services.ingestion.storage import ArtifactStore
from app.services.llm.base import LanguageModel
from app.services.llm.gemini import GeminiClient
from app.services.llm.resilient import CircuitBreaker, GuardedModel
from app.services.retrieval.embedder import OnnxE5Embedder
from app.services.retrieval.retriever import Retriever
from app.services.retrieval.store import VectorStore

logger = logging.getLogger(__name__)


def build_model(settings: Settings) -> LanguageModel | None:
    """The configured language model, or None when there is no API key."""
    if settings.gemini_api_key is None:
        return None
    client = GeminiClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        deadline_seconds=settings.gemini_deadline_seconds,
        max_output_tokens=settings.gemini_max_output_tokens,
        thinking_level=settings.gemini_thinking_level,
        base_url=settings.gemini_base_url,
    )
    breaker = CircuitBreaker(
        threshold=settings.llm_breaker_threshold,
        cooldown_seconds=settings.llm_breaker_cooldown_seconds,
    )
    return GuardedModel(client, breaker)


def build_runtime(settings: Settings) -> AssistantRuntime:
    artifacts = ArtifactStore(settings.data_dir)
    store = VectorStore(
        artifacts.chroma_dir,
        embedding_model=settings.embedding_model,
        cache_scans=settings.cache_enabled,
    )
    embedder = OnnxE5Embedder(settings.embedding_model, artifacts.models_dir)
    registry = load_registry()
    urls = {spec.id: spec.url for spec in registry}
    try:
        entries = load_catalogue(sources=urls)
        records = load_budget(sources=urls)
    except SchemeDataError as error:  # the search then works from the documents alone
        logger.error("The catalogue could not be loaded for the search: %s", error.message)
        entries, records = [], []
    service = AssistantService(
        retriever=Retriever(store, embedder),
        model=build_model(settings),
        max_question_chars=settings.assistant_max_question_chars,
        search=KnowledgeSearch(store, embedder, entries=entries, records=records),
    )
    return AssistantRuntime(service=service, catalog=SourceCatalog(store, registry))
