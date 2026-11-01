"""Greetings, thanks, goodbyes and "who are you?": answered with fixed texts, without a model.

A person who says "hello" to a voice assistant expects a hello back, not "the documents do not
say". These utterances are recognised by rules and answered from ``messages.py``. The rule is
strict on purpose: the whole utterance must be made of the words of one kind ("hello", "thank you
so much", "good morning"), so that "hello, what is the income limit?" is still a question and goes
to the documents.
"""

import re
import unicodedata

# Words that, alone or together, make an utterance of that kind. The first set of each pair says
# which words may start it (so that "you" alone is not a greeting); the second is all that is
# allowed in it.
_GREETING_HEAD = frozenset(
    [
        "hi",
        "hii",
        "hello",
        "hey",
        "namaste",
        "namaskar",
        "namaskaar",
        "salaam",
        "salam",
        "good",
        "नमस्ते",
        "नमस्कार",
        "हेलो",
        "हैलो",
        "हाय",
        "प्रणाम",
        "सुप्रभात",
        "নমস্কার",
        "নমস্তে",
        "হ্যালো",
        "হাই",
        "সুপ্রভাত",
    ]
)
_GREETING = _GREETING_HEAD | frozenset(
    [
        "morning",
        "afternoon",
        "evening",
        "there",
        "sir",
        "madam",
        "ji",
        "friend",
        "how",
        "are",
        "you",
        "doing",
        "civicsaathi",
        "civic",
        "saathi",
        "आप",
        "कैसे",
        "हैं",
        "कैसी",
        "हो",
        "जी",
        "सिविकसाथी",
        "साथी",
        "আপনি",
        "কেমন",
        "আছেন",
        "আছো",
        "তুমি",
        "সিভিকসাথী",
        "সাথী",
    ]
)
_THANKS_HEAD = frozenset(
    [
        "thanks",
        "thank",
        "thankyou",
        "thx",
        "shukriya",
        "dhanyavad",
        "धन्यवाद",
        "शुक्रिया",
        "शुक्रिया",
        "थैंक्स",
        "ধন্যবাদ",
        "শুক্রিয়া",
    ]
)
_THANKS = _THANKS_HEAD | frozenset(
    [
        "you",
        "so",
        "much",
        "very",
        "a",
        "lot",
        "ok",
        "okay",
        "great",
        "nice",
        "that",
        "was",
        "helpful",
        "बहुत",
        "ठीक",
        "है",
        "आपका",
        "भी",
        "अच्छा",
        "सहायक",
        "অনেক",
        "আপনাকে",
        "ঠিক",
        "আছে",
        "খুব",
    ]
)
_BYE_HEAD = frozenset(
    ["bye", "goodbye", "tata", "alvida", "अलविदा", "बाय", "टाटा", "বিদায়", "টাটা", "বাই"]
)
_BYE = _BYE_HEAD | frozenset(
    [
        "good",
        "night",
        "see",
        "you",
        "later",
        "take",
        "care",
        "ok",
        "okay",
        "फिर",
        "मिलेंगे",
        "ठीक",
        "है",
        "আবার",
        "দেখা",
        "হবে",
        "ভালো",
        "থাকবেন",
    ]
)

_ABOUT = re.compile(
    r"^(who|what) (are|r) (you|u)$|^what('s| is) your name$|^what can you do$|^what do you do$"
    r"|^how (can|do) you help( me)?$|^what (do|can) you (help|know)( with| about)?$|^help( me)?$"
    r"|^आप कौन हैं$|^आप क्या कर सकते हैं$|^आप क्या करते हैं$|^आपका नाम क्या है$|^मदद$|^मदद करो$"
    r"|^আপনি কে$|^তুমি কে$|^আপনি কী করতে পারেন$|^আপনার নাম কী$|^সাহায্য$"
)


def _tokens(text: str) -> list[str]:
    """Lower-cased words with punctuation (including the danda) removed."""
    kept = "".join(
        " " if unicodedata.category(char).startswith("P") else char for char in text.lower()
    )
    return kept.split()


def _made_of(tokens: list[str], head: frozenset[str], allowed: frozenset[str]) -> bool:
    return (
        bool(tokens)
        and tokens[0] in head
        and all(token in allowed for token in tokens)
        and len(tokens) <= 6
    )


def classify_smalltalk(question: str) -> str | None:
    """The message key (``smalltalk_greeting``, ``_thanks``, ``_bye``, ``_about``) of the reply a
    greeting, thanks, goodbye or "who are you" gets; None for a real question."""
    tokens = _tokens(question)
    if not tokens or len(tokens) > 6:
        return None
    if _ABOUT.match(" ".join(tokens)):
        return "smalltalk_about"
    # "good" starts both a greeting and a goodbye ("good morning", "good night"): night is a bye.
    if _made_of(tokens, _BYE_HEAD, _BYE) or (tokens[0] == "good" and "night" in tokens):
        return "smalltalk_bye"
    if _made_of(tokens, _THANKS_HEAD, _THANKS):
        return "smalltalk_thanks"
    if _made_of(tokens, _GREETING_HEAD, _GREETING):
        return "smalltalk_greeting"
    return None
