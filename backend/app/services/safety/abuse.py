"""Requests the assistant must refuse outright, without spending a model call on them.

SPEC section 9: refuse abusive or illegal-evasion requests, for example "how to fake an income
certificate". These patterns look for the *intent to do it*, which means an intent phrase ("how
to", "I want to", "help me") followed by the act. A question that merely mentions forgery ("what
is the penalty for forging a certificate?", "how do I check if a certificate is fake?") is a fair
question about the rules and must still be answered. The system prompt carries the same policy
for what these patterns miss.
"""

import re
import unicodedata

_INTENT = (
    r"(?:how (?:to|do i|can i|could i|would i|should i|do we|can we)|i want to|i need to|"
    r"i am trying to|i'm trying to|help me|teach me|show me|ways? to|tricks? to|"
    r"tips? (?:to|for|on)|can you (?:make|help|create|give)|please (?:make|create))"
)
_DOCUMENTS = (
    r"(?:certificate|document|proof|marksheet|mark sheet|income|caste|domicile|residence|bonafide|"
    r"signature|stamp|seal|aadhaar|bank statement|letter|id card|ration card)"
)
# Not "duplicate": a duplicate marksheet is a genuine document the board issues on request.
_FAKE = r"(?:fake|forged|false|fabricated|bogus|counterfeit|photoshopped)"
_FORGE = (
    r"(?:forge|forging|fabricate|fabricating|counterfeit|counterfeiting|falsify|falsifying|"
    r"tamper with)"
)

_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # "how to make / get / buy a fake income certificate"
        rf"\b{_INTENT}\b[^.?!]{{0,25}}\b(?:make|get|create|arrange|buy|produce|prepare|obtain|"
        rf"print|generate|submit)\b[^.?!]{{0,25}}\b{_FAKE}\b[^.?!]{{0,30}}\b{_DOCUMENTS}\b",
        # "I want to forge an income certificate"
        rf"\b{_INTENT}\b[^.?!]{{0,25}}\b{_FORGE}\b[^.?!]{{0,30}}\b{_DOCUMENTS}\b",
        # "how can I fool the income verification"
        rf"\b{_INTENT}\b[^.?!]{{0,25}}\b(?:cheat|fool|trick|deceive|evade|mislead)\b[^.?!]{{0,40}}"
        r"\b(?:verification|eligibility|income limit|income criteria|inspection|income check|"
        r"checks?|officials?|authorities)\b",
        # Bengali: "how do I make a fake income certificate"
        r"(?:কীভাবে|কিভাবে)[^।?!]{0,25}(?:জাল|নকল|ভুয়া)[^।?!]{0,30}"
        r"(?:শংসাপত্র|সার্টিফিকেট|প্রমাণপত্র|সনদ|নথি|কাগজ)",
        # Hindi: "how do I make a fake income certificate"
        r"कैसे[^।?!]{0,25}(?:नकली|फर्जी|फ़र्ज़ी|जाली)[^।?!]{0,30}"
        r"(?:प्रमाण\s?पत्र|सर्टिफिकेट|दस्तावेज़?|आय)",
    )
)


def is_forgery_request(question: str) -> bool:
    """True if the question asks how to fake documents or to cheat the eligibility checks."""
    folded = " ".join(unicodedata.normalize("NFKC", question).split())
    folded = folded.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")  # what phone keyboards type
    return any(pattern.search(folded) for pattern in _PATTERNS)
