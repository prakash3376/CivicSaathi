# ruff: noqa: E501  (the word lists are long lines of alternatives; wrapping them hides them)
"""What a question is for, decided by rules and not by a model.

The intent does not change what the assistant may say (every claim still needs a quote); it decides
how to look: which documents to favour, whether earlier questions are needed to understand this
one, and what to offer next (a check of eligibility, the budget, a service page). Rules cost no
model call and can be tested; ``python -m app.cli eval`` measures them on labelled questions.

Words are matched in English, Hindi and Bengali. The first rule that matches wins, so the order
below is the order of precedence.
"""

import re
from dataclasses import dataclass
from typing import Literal

Intent = Literal[
    "scheme_discovery",
    "scheme_information",
    "eligibility",
    "benefit_amount",
    "application_procedure",
    "required_documents",
    "notification_explanation",
    "policy_rights",
    "budget",
    "policy_comparison",
    "public_service",
    "general_civic",
    "follow_up",
    "out_of_scope",
]

INTENTS: tuple[Intent, ...] = (
    "scheme_discovery",
    "scheme_information",
    "eligibility",
    "benefit_amount",
    "application_procedure",
    "required_documents",
    "notification_explanation",
    "policy_rights",
    "budget",
    "policy_comparison",
    "public_service",
    "general_civic",
    "follow_up",
    "out_of_scope",
)


def _words(*alternatives: str) -> re.Pattern[str]:
    return re.compile("|".join(alternatives), re.IGNORECASE)


# Not about government at all.
_OUT_OF_SCOPE = _words(
    r"\bweather\b|\bcricket\b|\bfootball\b|\bmovie\b|\bfilm\b|\brecipe\b|\bhoroscope\b|\bjoke\b",
    r"\bstock price\b|\bbitcoin\b|\bsong\b|\bignore (all |your )?(previous |prior )?instructions\b",
    r"\bfake\b.*\b(certificate|document)|\bforge\b",
    r"मौसम|क्रिकेट|फ़िल्म|फिल्म|আবহাওয়া|ক্রিকেট|সিনেমা",
)
_COMPARISON = _words(
    r"\bchanged?\b.*\b(previous|earlier|old|last)\b|\bcompared? (with|to)\b|\bold (and|vs|versus) new\b",
    r"\bprevious (notification|version|rule|policy)\b|\bwhat('s| is| has) changed\b|\bamendment\b",
    r"पिछली अधिसूचना|क्या बदला|बदलाव|আগের বিজ্ঞপ্তি|কী বদলেছে|পরিবর্তন",
)
_BUDGET = _words(
    r"\bbudget\b|\ballocation|\ballocated\b|\bset aside\b|\bincome tax\b|\bexpenditure\b|\bfiscal\b",
    r"\bgst\b|\bcustoms duty\b|\btax (slab|change|relief)",
    r"बजट|आवंटन|आयकर|बাজেট|বরাদ্দ|আয়কর",
)
_NOTIFICATION = _words(
    r"\bexplain (this|the) (government )?(notification|circular|order|policy)\b|\bnotification\b",
    r"अधिसूचना|বিজ্ঞপ্তি",
)
_RIGHTS = _words(r"\bmy rights\b|\bright to\b|\bcitizen rights\b|\blegal rights\b", r"अधिकार|অধিকার")
_DOCUMENTS = _words(
    r"\bdocuments?\b|\bpapers\b|\bproof\b|\bwhat (do|should) i (need|bring|carry)\b",
    r"दस्तावेज़|दस्तावेज|कागज़|কাগজ|নথি",
)
_SERVICE = _words(
    r"\bcertificate\b|\bration card\b|\bmutation\b|\bland record|\brecord of rights\b|\brti\b",
    r"\bright to information\b|\bbirth (and|or) death\b|\bjob card\b|\be-?shram\b|\bdigilocker\b",
    r"\bpatta\b|\bbangla sahayata\b|\bregistration\b",
    r"प्रमाणपत्र|प्रमाण पत्र|राशन कार्ड|आरटीआई|শংসাপত্র|রেশন কার্ড|আরটিআই",
)
_ELIGIBILITY = _words(
    r"\bwho (can|may|is eligible|is allowed|qualifies)\b|\beligib|\bqualify\b|\bage limit\b",
    r"\bwho is (covered|entitled)\b|\bam i (covered|entitled)\b|\bminimum age\b|\bincome limit\b",
    r"कौन.*(पात्र|आवेदन|पा सकता|पा सकती)|पात्र|योग्य|কারা.*(আবেদন|পেতে)|যোগ্য",
)
_AMOUNT = _words(
    r"\bhow (much|many)\b|\bamount\b|\bhow big\b|\bwhat is the (rate|ceiling|maximum|limit)\b",
    r"कितना|कितनी|कितने|কত\b",
)
_PROCEDURE = _words(
    r"\bhow (do|can|should|to|does)\b.*\b(apply|get|obtain|register|enrol|enroll|receive|claim)\b",
    r"\bhow to apply\b|\bapply for\b|\bapplication (process|procedure|steps)\b|\bwhere (do|can) i apply\b",
    r"कैसे.*(आवेदन|मिल|बन|पा)|आवेदन कैसे|কীভাবে.*(আবেদন|পাওয়া|পান|করব|করবেন)",
)
_DISCOVERY = _words(
    r"\bwhat\b.*\b(schemes?|programmes?|assistance|benefits?|help|support|options)\b.*\b(available|can i|may be|get)\b",
    r"\bwhich (schemes?|programmes?)\b|\bwhat (government )?(schemes?|programmes?|assistance|benefits?)\b",
    r"\bwhat can i (get|use|receive)\b|\bwhat help\b|\bwhat financial\b|\bwhat pension",
    r"\bwhat\b.*\b(is|are) available\b|\bavailable (for|in|to)\b",
    r"कौन-सी.*(योजना|सहायता|कार्यक्रम|बीमा)|कौन से.*(योजना|कार्यक्रम)|क्या सहायता|कौन-सा.*(मिलता|उपलब्ध)",
    r"কোন.*(প্রকল্প|সহায়তা|কর্মসূচি|বিমা|পেনশন)|কোন.*(পাওয়া যায়|আছে)",
)
_INFORMATION = _words(
    r"\bwhat is\b|\bwhat are\b|\btell me about\b|\bpurpose of\b|\bwhat does\b|\bis .* (still )?running\b",
    r"क्या है|किसलिए|কী\b|কীসের",
)
_ANAPHORA = _words(
    r"^(and |what about |how about )?(it|its|this|that|they|their|them|these|those)\b|\b(it|its|this scheme|that scheme)\b",
    r"\bfor (it|this|that)\b|^(इसमें|इसके|इसका|इसकी|इसे|यह|ये|उसमें|এতে|এর|এটি|এটা|ওতে)",
)
_SHORT_WORDS = 5  # a question this short, after an earlier one, probably leans on it


# What wins even over a follow-up: a comparison, the budget, an explanation of a notification.
_PRIORITY: tuple[tuple[re.Pattern[str], Intent], ...] = (
    (_COMPARISON, "policy_comparison"),
    (_BUDGET, "budget"),
    (_NOTIFICATION, "notification_explanation"),
)
# The rest, by what the question is about.
_BY_TOPIC: tuple[tuple[re.Pattern[str], Intent], ...] = (
    (_RIGHTS, "policy_rights"),
    (_SERVICE, "public_service"),
    (_DOCUMENTS, "required_documents"),
    (_ELIGIBILITY, "eligibility"),
    (_AMOUNT, "benefit_amount"),
    (_PROCEDURE, "application_procedure"),
    (_DISCOVERY, "scheme_discovery"),
    (_INFORMATION, "scheme_information"),
)


@dataclass(frozen=True)
class Classified:
    intent: Intent
    # The earlier question the answer depends on, when this one cannot stand alone.
    needs_history: bool


def classify(question: str, *, has_history: bool = False) -> Classified:
    """The intent of ``question``; with earlier questions, a short or "it"-style one is a follow-up."""
    text = " ".join(question.split())
    if _OUT_OF_SCOPE.search(text):
        return Classified("out_of_scope", False)
    leans = has_history and (
        _ANAPHORA.search(text) is not None or len(text.split()) <= _SHORT_WORDS
    )
    for pattern, intent in _PRIORITY:
        if pattern.search(text):
            return Classified(intent, leans)
    if leans:
        return Classified("follow_up", True)
    for pattern, intent in _BY_TOPIC:
        if pattern.search(text):
            return Classified(intent, leans)
    return Classified("general_civic", False)
