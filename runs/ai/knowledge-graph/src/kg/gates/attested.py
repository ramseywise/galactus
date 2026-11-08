"""Gate 2: both entity surface forms appear inside the quote.

Compared in `norm_surface` form (NFC, casefolded, whitespace collapsed), so the quote may
capitalise an entity differently from the proposer's surface form. An entity the quote
does not name is the proposer's inference, not the page's claim.
"""

from __future__ import annotations

from kg.models import Candidate, GateResult
from kg.profile.normalise import norm_surface


def check(candidate: Candidate) -> GateResult:
    quote = norm_surface(candidate.quote)
    missing = [
        side
        for side, surface in (("subject", candidate.subject), ("object", candidate.object))
        if norm_surface(surface) not in quote
    ]
    if missing:
        return GateResult(False, f"{' and '.join(missing)} not named in the quote")
    return GateResult(True, None)
