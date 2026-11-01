"""Failures raised while collecting, reading or indexing documents.

Each carries a short, stable ``code`` for programs and a ``message`` that is safe to show to people.
"""


class IngestionError(Exception):
    """Base class: a document could not be collected, read or indexed."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class RegistryError(IngestionError):
    """The curated source registry is malformed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_registry")


class FetchError(IngestionError):
    """A document could not be downloaded (network, TLS, size, robots.txt, ...)."""


class ExtractionError(IngestionError):
    """A downloaded file could not be turned into text (corrupted, password-protected, ...)."""


class IndexingError(IngestionError):
    """The embedding model or the vector store could not be used."""


class SchemeDataError(Exception):
    """The scheme rules in ``backend/data/schemes`` are malformed or disagree with their sources.

    The message names the file and the rule, so a person can fix it.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = "invalid_scheme_data"


class AssistantError(Exception):
    """The assistant could not answer. The message is safe to show to a user; ``code`` is stable."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
