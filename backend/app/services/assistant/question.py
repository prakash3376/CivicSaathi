"""What the user typed: tidied, and the language to answer in."""

import unicodedata

from app.domain.assistant import Language, LanguageChoice
from app.services.grounding.language import script_share
from app.services.segmentation.scripts import detect_script

_NATIVE_SHARE_NEEDED = 0.4  # of the letters, for a mixed question to count as Bengali or Hindi


def tidy(question: str) -> str:
    """Normalised, with invisible and control characters gone and white space collapsed."""
    text = unicodedata.normalize("NFC", question)
    text = "".join(
        char for char in text if char.isspace() or unicodedata.category(char) not in ("Cc", "Cf")
    )
    return " ".join(text.split())


def resolve_language(question: str, choice: LanguageChoice) -> tuple[Language, bool]:
    """The language to answer in, and whether it is a fallback from one we do not offer.

    English, Hindi and Bengali are offered. A question written in Tamil or any other language is
    answered in English, and the user is told so (SPEC rule R8).
    """
    if choice != "auto":
        return choice, False
    script = detect_script(question)
    if script == "Bengali":
        return "bn", False
    if script == "Devanagari":
        return "hi", False
    if script == "mixed":  # for example Bengali or Hindi with English words in it
        bengali, hindi = script_share(question, "bn"), script_share(question, "hi")
        if max(bengali, hindi) >= _NATIVE_SHARE_NEEDED:
            return ("bn" if bengali >= hindi else "hi"), False
        return "en", False
    if script in ("Latin", "unknown"):
        return "en", False
    return "en", True
