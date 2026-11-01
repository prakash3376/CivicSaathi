"""Which writing system a passage is in, judged from its letters (no model, no dependency)."""

from collections import Counter

_INDIC_RANGES = (
    ("Devanagari", 0x0900, 0x097F),
    ("Bengali", 0x0980, 0x09FF),
    ("Gurmukhi", 0x0A00, 0x0A7F),
    ("Gujarati", 0x0A80, 0x0AFF),
    ("Odia", 0x0B00, 0x0B7F),
    ("Tamil", 0x0B80, 0x0BFF),
    ("Telugu", 0x0C00, 0x0C7F),
    ("Kannada", 0x0C80, 0x0CFF),
    ("Malayalam", 0x0D00, 0x0D7F),
)

# A script is only a hint about the language: Devanagari is also Marathi, Latin may be Hinglish.
LANGUAGE_HINTS = {
    "Latin": "en",
    "Devanagari": "hi",
    "Bengali": "bn",
    "Gurmukhi": "pa",
    "Gujarati": "gu",
    "Odia": "or",
    "Tamil": "ta",
    "Telugu": "te",
    "Kannada": "kn",
    "Malayalam": "ml",
}


def detect_script(text: str) -> str:
    """The dominant script (``Latin``, ``Bengali``, ...), ``mixed`` below 80%, else ``unknown``."""
    counts: Counter[str] = Counter()
    for char in text:
        if not char.isalpha():
            continue
        code = ord(char)
        if code < 0x250:  # Basic Latin through Latin Extended-B
            counts["Latin"] += 1
            continue
        for name, low, high in _INDIC_RANGES:
            if low <= code <= high:
                counts[name] += 1
                break
        else:
            counts["Other"] += 1

    total = sum(counts.values())
    if total == 0:
        return "unknown"
    script, count = counts.most_common(1)[0]
    return script if count / total >= 0.8 else "mixed"
