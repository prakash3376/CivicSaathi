"""Google Gemini through the official ``google-genai`` SDK.

Each call is stateless: the system instruction, the prompt and the expected JSON shape go in, and
nothing is kept on the provider's side by us. The text of a prompt or a reply is never logged; only
the model, the time taken and the token counts are.

Be aware of where the data goes. A question and the passages sent with it leave this server for
Google. On the free tier of the Gemini API, Google may use what it receives to improve its
products; the paid tier does not (see the terms for the Gemini API). Questions have personal
numbers removed first (``app.services.safety.pii``), but a question can still say private things.
"""

import logging
import random
import re
import time
from collections.abc import Callable

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.domain.errors import AssistantError
from app.services.llm.base import T

logger = logging.getLogger(__name__)

# Facts first, with a little room for the model to think; a low temperature keeps quotes exact.
_TEMPERATURE = 0.2
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# A network error is retried only if the connection could not be made (nothing was sent, so the
# call was cheap to lose); a read that timed out already cost the whole timeout.
_RETRY_NETWORK = (httpx.ConnectError, httpx.ConnectTimeout)
_MIN_USEFUL_SECONDS = 3.0  # a retry with less time than this left cannot finish
_MAX_RETRY_AFTER_SECONDS = 10.0  # a provider asking for longer is treated as "busy": give up
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)

# What a user may be told. A wrong key or model name is the operator's problem and is only ever
# described in the log, so both get the same message.
_NOT_AVAILABLE = "The assistant is not available right now. Please try again later."
_MESSAGES = {
    "llm_busy": "The assistant is busy answering many questions. Please try again in a minute.",
    "llm_unavailable": "The assistant did not respond. Please try again in a moment.",
    "llm_auth": _NOT_AVAILABLE,
    "llm_rejected": _NOT_AVAILABLE,
    "llm_blocked": "The AI service declined to answer this question.",
    "llm_bad_output": "The assistant could not prepare a reliable answer. Please try again.",
}


def _failure(code: str) -> AssistantError:
    return AssistantError(_MESSAGES[code], code=code)


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 45.0,
        max_output_tokens: int = 4096,
        thinking_level: str | None = None,
        base_url: str | None = None,
        attempts: int = 2,
        retry_delay_seconds: float = 1.0,
        deadline_seconds: float = 50.0,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        """``attempts`` counts the first try; rate limits, server errors and refused connections
        are tried again after a pause that doubles, with jitter, or as long as the provider's
        ``Retry-After`` asks (up to 10 s). ``deadline_seconds`` is the most one ``generate`` may
        take in all, retries included: the browser gives up at 60 s, and a reply that arrives
        after that is wasted quota. A wrong key or a bad request is never retried.

        The retry loop is ours, not the SDK's, so that the deadline and the pause are ours too.
        ``http_client`` lets a test supply a transport that answers without the network;
        ``sleep``, ``clock`` and ``jitter`` let it do so without waiting.
        """
        self._model = model
        self._timeout = timeout_seconds
        self._attempts = max(1, attempts)
        self._delay = retry_delay_seconds
        self._deadline = deadline_seconds
        self._sleep = sleep
        self._clock = clock
        self._jitter = jitter
        self._max_output_tokens = max_output_tokens
        self._thinking = (
            types.ThinkingConfig(thinking_level=types.ThinkingLevel(thinking_level.upper()))
            if thinking_level
            else None
        )
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                base_url=base_url,
                timeout=int(timeout_seconds * 1000),  # the SDK counts in milliseconds
                httpx_client=http_client,
            ),
        )

    @property
    def name(self) -> str:
        return self._model

    def generate(self, *, system: str, prompt: str, schema: type[T]) -> T:
        started = self._clock()
        attempt = 0
        while True:
            attempt += 1
            remaining = self._deadline - (self._clock() - started)
            try:
                return self._once(system, prompt, schema, min(self._timeout, remaining))
            except _Transient as failure:
                pause = self._pause(failure.retry_after, attempt)
                left = self._deadline - (self._clock() - started) - pause
                too_long = (failure.retry_after or 0) > _MAX_RETRY_AFTER_SECONDS
                if attempt >= self._attempts or left < _MIN_USEFUL_SECONDS or too_long:
                    logger.warning(
                        "Gemini failed (%s) after %d attempt(s); not trying again",
                        failure.error.code,
                        attempt,
                    )
                    raise failure.error from None
                logger.info("Gemini failed (%s); trying again in %.1f s", failure.error.code, pause)
                self._sleep(pause)

    def _pause(self, retry_after: float | None, attempt: int) -> float:
        if retry_after is not None:
            return min(retry_after, _MAX_RETRY_AFTER_SECONDS)
        # Full jitter on a doubling delay, so that many visitors do not retry in step.
        ceiling = self._delay * 2.0 ** (attempt - 1)
        return ceiling * (0.5 + 0.5 * self._jitter())

    def _once(self, system: str, prompt: str, schema: type[T], timeout: float) -> T:
        if timeout < _MIN_USEFUL_SECONDS:
            logger.warning("Gemini was not asked: the time limit for this question is used up")
            raise _failure("llm_unavailable")
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=_TEMPERATURE,
            max_output_tokens=self._max_output_tokens,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=self._thinking,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        )
        started = time.monotonic()
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            )
        except errors.APIError as error:
            failure = _from_api_error(error)
            if error.code in _RETRY_STATUSES:
                raise _Transient(failure, _retry_after(error)) from None
            raise failure from None
        except _RETRY_NETWORK:
            logger.warning("Gemini could not be reached (connection refused or timed out)")
            raise _Transient(_failure("llm_unavailable"), None) from None
        except httpx.HTTPError:
            logger.warning("Gemini could not be reached (network error or timeout)")
            raise _failure("llm_unavailable") from None

        usage = response.usage_metadata
        logger.info(
            "Gemini %s answered in %d ms (%s prompt tokens, %s output tokens)",
            self._model,
            (time.monotonic() - started) * 1000,
            usage.prompt_token_count if usage else "?",
            usage.candidates_token_count if usage else "?",
        )
        return _parse(response, schema)


class _Transient(Exception):
    """A failure worth another try: carries what the user may be told if there is none."""

    def __init__(self, error: AssistantError, retry_after: float | None) -> None:
        super().__init__(error.code)
        self.error = error
        self.retry_after = retry_after


def _retry_after(error: errors.APIError) -> float | None:
    """Seconds the provider asked us to wait (the ``Retry-After`` header), if it said."""
    headers = getattr(getattr(error, "response", None), "headers", None)
    value = headers.get("retry-after") if headers is not None else None
    try:
        seconds = float(value) if value is not None else None
    except ValueError:  # an HTTP date: not worth parsing, the doubling delay is used
        return None
    return seconds if seconds is not None and seconds >= 0 else None


def _from_api_error(error: errors.APIError) -> AssistantError:
    # Only the numbers are logged: the provider's message may quote parts of the request.
    status = error.code
    if status in (401, 403):
        logger.error("Gemini refused the API key (HTTP %s): check GEMINI_API_KEY", status)
        return _failure("llm_auth")
    if status == 429:
        logger.warning("Gemini rate limit or quota reached (HTTP 429)")
        return _failure("llm_busy")
    if status in (400, 404, 422):
        logger.error(
            "Gemini rejected the request (HTTP %s, %s): check GEMINI_MODEL and the settings",
            status,
            error.status,
        )
        return _failure("llm_rejected")
    logger.warning("Gemini is unavailable (HTTP %s)", status)
    return _failure("llm_unavailable")


def _parse(response: types.GenerateContentResponse, schema: type[T]) -> T:
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason:
        logger.warning("Gemini blocked the prompt (%s)", feedback.block_reason.name)
        raise _failure("llm_blocked")

    candidate = response.candidates[0] if response.candidates else None
    finish = candidate.finish_reason if candidate else None
    if finish == types.FinishReason.MAX_TOKENS:
        logger.warning("Gemini's reply was cut off at the output token limit")
        raise _failure("llm_bad_output")
    finished_normally = (
        None,
        types.FinishReason.STOP,
        types.FinishReason.FINISH_REASON_UNSPECIFIED,
    )
    if finish is not None and finish not in finished_normally:
        logger.warning("Gemini stopped without an answer (%s)", finish.name)
        raise _failure("llm_blocked")

    text = response.text
    if not text:
        logger.warning("Gemini returned no text")
        raise _failure("llm_bad_output")
    fenced = _FENCE.match(text)
    try:
        return schema.model_validate_json(fenced.group(1) if fenced else text)
    except ValidationError:
        # Not chained: the error text would quote the model's reply.
        logger.warning("Gemini's reply did not have the requested shape")
        raise _failure("llm_bad_output") from None
