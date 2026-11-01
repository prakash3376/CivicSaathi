"""The second pass of SPEC section 6: check every claim the model drafted against its sources.

A claim is kept when
  * a quote it offers is found, word for word, in one of the passages the model was given;
  * and every figure, month and web address in its statement is in the words it quotes.

This cannot tell whether a statement *means* what its quote means. What it does guarantee is that
each statement is tied to real words of an official document that the user can open and read, and
that no amount, date or address appears that the document does not contain (rules R1 and R2).
Everything else is rejected, and the reason is recorded so the model can be told what to fix.
No reason ever holds text from the question, a passage or the draft.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.assistant import Draft, DraftClaim, Language, Passage
from app.services.grounding.language import writes_in
from app.services.grounding.numbers import Problem, unsupported
from app.services.grounding.text import Located, Squashed, find_quote, is_long_enough, squash

Reason = Literal[
    "empty",
    "too_long",
    "duplicate",
    "language",
    "no_evidence",
    "unknown_source",
    "quote_not_found",
    "quote_too_short",
    Problem,
]

MAX_CLAIMS = 10
MAX_STATEMENT_CHARS = 600
MAX_SUPPORT_PER_CLAIM = 3

_REFERENCE = re.compile(r"\s*\[\s*S\d+(?:\s*[,;]\s*S\d+)*\s*\]")
_DIGITS = re.compile(r"\d+")


@dataclass(frozen=True)
class Support:
    """One quote of a claim, found in a passage."""

    passage: Passage
    located: Located

    @property
    def quote(self) -> str:
        """The words as the document writes them, not as the model re-typed them."""
        return self.located.words(self.passage.text)


@dataclass(frozen=True)
class VerifiedClaim:
    statement: str
    support: tuple[Support, ...]


@dataclass(frozen=True)
class Rejection:
    index: int  # position in the draft
    reasons: tuple[Reason, ...]


@dataclass(frozen=True)
class Verification:
    claims: tuple[VerifiedClaim, ...] = ()
    rejections: tuple[Rejection, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.rejections


def clean_statement(statement: str) -> str:
    """A statement as it will be shown: no stray source references, one line of white space."""
    return " ".join(_REFERENCE.sub("", statement).split())


def verify(
    draft: Draft, passages: Sequence[Passage], *, language: Language | None = None
) -> Verification:
    """Keep the claims of ``draft`` that hold up against ``passages``; say why the rest do not.

    With ``language`` given, a statement that is not written in it does not hold up either.
    """
    squashed = [squash(passage.text) for passage in passages]
    kept: list[VerifiedClaim] = []
    rejected: list[Rejection] = []
    seen: set[str] = set()

    for index, claim in enumerate(draft.claims[:MAX_CLAIMS]):
        statement = clean_statement(claim.statement)
        reasons = _statement_problems(statement, seen, language)
        support: list[Support] = []
        if not reasons:
            support, reasons = _check_evidence(statement, claim, passages, squashed)
        if reasons:
            rejected.append(Rejection(index, tuple(reasons)))
            continue
        seen.add(squash(statement).chars)
        kept.append(VerifiedClaim(statement, tuple(support)))

    return Verification(tuple(kept), tuple(rejected))


def _statement_problems(statement: str, seen: set[str], language: Language | None) -> list[Reason]:
    if not statement:
        return ["empty"]
    if len(statement) > MAX_STATEMENT_CHARS:
        return ["too_long"]
    if squash(statement).chars in seen:
        return ["duplicate"]
    if language is not None and not writes_in(statement, language):
        return ["language"]
    return []


def _check_evidence(
    statement: str, claim: DraftClaim, passages: Sequence[Passage], squashed: Sequence[Squashed]
) -> tuple[list[Support], list[Reason]]:
    if not claim.evidence:
        return [], ["no_evidence"]

    support: list[Support] = []
    failures: set[Reason] = set()
    for evidence in claim.evidence:
        if not is_long_enough(evidence.quote):
            failures.add("quote_too_short")  # said apart: the quote may well be in the passage
            continue
        found = _find_support(evidence.source, evidence.quote, passages, squashed)
        if found is None:
            known = _hinted(evidence.source, passages) is not None  # position 0 is a real passage
            failures.add("quote_not_found" if known else "unknown_source")
        elif found not in support:
            support.append(found)
    support = support[:MAX_SUPPORT_PER_CLAIM]

    # One quote that holds up is enough to keep a claim; the quotes that failed are dropped.
    if not support:
        return [], sorted(failures)
    problems: list[Reason] = [*unsupported(statement, [item.quote for item in support])]
    return support, problems


def _hinted(source: str, passages: Sequence[Passage]) -> int | None:
    """Which passage the model says it quoted ("S2", "s2", "[S2]", "Source 2")."""
    digits = _DIGITS.search(source)
    if digits is None:
        return None
    wanted = f"S{int(digits.group())}"
    return next((i for i, passage in enumerate(passages) if passage.ref == wanted), None)


def _find_support(
    source: str, quote: str, passages: Sequence[Passage], squashed: Sequence[Squashed]
) -> Support | None:
    # The reference is only a hint. A quote that is really in another passage is still a real
    # quote, and that passage is the one the user will be shown.
    hinted = _hinted(source, passages)
    order = [] if hinted is None else [hinted]
    order += [position for position in range(len(passages)) if position != hinted]
    for position in order:
        located = find_quote(quote, squashed[position])
        if located is not None:
            return Support(passages[position], located)
    return None
