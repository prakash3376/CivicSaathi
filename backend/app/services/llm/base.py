"""What the assistant needs from a language model, so the provider can be swapped or faked."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LanguageModel(Protocol):
    """A model that answers a prompt with an object of a given shape.

    Implementations raise ``AssistantError`` (``app.domain.errors``) with one of these codes:
    ``llm_busy`` (rate limit), ``llm_unavailable`` (timeout or provider outage), ``llm_auth`` and
    ``llm_rejected`` (our credentials or request are wrong: an operator must act),
    ``llm_blocked`` (the provider declined this prompt) and ``llm_bad_output`` (the reply was cut
    off or did not have the requested shape).
    """

    @property
    def name(self) -> str:
        """Identifies the model in answers and logs."""
        ...

    def generate(self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Answer ``prompt`` under the instructions in ``system`` as a ``schema`` object."""
        ...
