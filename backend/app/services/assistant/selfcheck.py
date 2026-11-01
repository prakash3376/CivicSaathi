"""A small end-to-end test of the language model that anyone can run with their own key.

``python -m app.cli assistant-check`` asks the configured model a tiny question about a built-in
passage, in English, Bengali and Hindi, and passes only if its reply survives the same grounding
check that every real answer goes through. That one call proves a good deal at once: the key
works, the model name exists, the model returns the JSON we ask for, it copies a quote exactly,
and it can write Bengali and Hindi. Nothing about a real user or a real document is sent.
"""

import secrets
import time
from dataclasses import dataclass

from app.domain.assistant import Draft, Language, Passage
from app.domain.errors import AssistantError
from app.services.grounding.verify import verify
from app.services.llm.base import LanguageModel
from app.services.llm.prompts import build_prompt

SAMPLE = Passage(
    ref="S1",
    chunk_id="self-check",
    source_id="self-check",
    title="Self-check passage",
    url="https://example.gov.in/self-check",
    text=(
        "The upper ceiling for family income has been fixed at Rs.2,50,000/- per annum. "
        "Applications must be submitted online before 30.11.2026."
    ),
)

QUESTIONS: dict[Language, str] = {
    "en": "What is the family income limit, and by when must I apply?",
    "bn": "পারিবারিক আয়ের সীমা কত, আর কবের মধ্যে আবেদন করতে হবে?",
    "hi": "पारिवारिक आय की सीमा क्या है, और आवेदन कब तक करना है?",
}


@dataclass(frozen=True)
class ProbeResult:
    language: Language
    ok: bool
    detail: str


def probe(model: LanguageModel, language: Language) -> ProbeResult:
    prompt = build_prompt(
        QUESTIONS[language], [SAMPLE], language=language, nonce=secrets.token_hex(4)
    )
    started = time.monotonic()
    try:
        draft = model.generate(system=prompt.system, prompt=prompt.user, schema=Draft)
    except AssistantError as error:
        return ProbeResult(language, False, f"{error.code}: {error.message}")
    seconds = time.monotonic() - started

    checked = verify(draft, [SAMPLE], language=language)
    if checked.claims:
        kept, removed = len(checked.claims), len(checked.rejections)
        note = f", {removed} failed the check" if removed else ""
        return ProbeResult(language, True, f"{kept} claim(s) verified in {seconds:.1f}s{note}")
    if not draft.answerable:
        return ProbeResult(
            language, False, "the model said the passage does not answer the question"
        )
    reasons = sorted({reason for item in checked.rejections for reason in item.reasons})
    return ProbeResult(
        language, False, "the reply did not hold up: " + (", ".join(reasons) or "it had no claims")
    )
