"""Gate 1: the quote is in the normalised body, exactly once, and long enough to locate.

Offsets are recomputed here rather than trusted from the proposer. A phrase that occurs
twice is rejected as ambiguous instead of pointing the judge window at whichever copy
`find` returns first (fog FA-012).
"""

from __future__ import annotations

from kg.models import Candidate, GateResult

MIN_QUOTE_CHARS = 20


def check(candidate: Candidate, body: str) -> GateResult:
    if len(candidate.quote) < MIN_QUOTE_CHARS:
        return GateResult(False, "quote too short to locate")
    n = body.count(candidate.quote)
    if n == 0:
        return GateResult(False, "quote not verbatim in normalised body")
    if n > 1:
        return GateResult(False, f"quote ambiguous: {n} occurrences")
    start = body.find(candidate.quote)
    return GateResult(True, None, span=(start, start + len(candidate.quote)))
