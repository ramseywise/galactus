"""Prices and the two thresholds they imply.

Taken from the course note `13-automate-review-or-reject.md` (Chow reject option with an
imperfect reviewer). Route costs are straight lines in p, the probability the triple is
WRONG (unsupported):

    accept: p * a            reject: (1 - p) * r
    review: h + p * (1 - c) * a + (1 - p) * f * r

with a = wrong_accept, r = wrong_reject, h = review, c = reviewer_tpr (catch rate: the
reviewer rejects a wrong triple), f = reviewer_fpr (false alarm: the reviewer rejects a good
one). The crossings:

    p_accept = (h + f r) / (c a + f r)           accept when p < p_accept
    p_reject = (r (1 - f) - h) / ((1 - c) a + r (1 - f))   reject when p > p_reject

Our score is P(supported) = 1 - p, so t_hi = 1 - p_accept and t_lo = 1 - p_reject:
score >= t_hi accepts, score <= t_lo rejects, in between goes to review.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prices:
    """Costs in one common unit (a review = 1).

    wrong_accept: an unsupported triple reaches a plan doc (10).
    wrong_reject: a supported triple is thrown away (3). The plan sketched 1, but with
        review = 1 and a 5% false-alarm reviewer the review route is then never the cheapest
        (review 1 > r(1 - f) = 0.95), so the band is empty and nothing is ever reviewed.
    review: one human review (1).
    reviewer_tpr / reviewer_fpr: reviewer rejects a wrong / a good triple (0.95 / 0.05).
    """

    wrong_accept: float = 10.0
    wrong_reject: float = 3.0
    review: float = 1.0
    reviewer_tpr: float = 0.95
    reviewer_fpr: float = 0.05

    def __post_init__(self) -> None:
        for name in ("wrong_accept", "wrong_reject", "review"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be > 0")
        if not 0 < self.reviewer_tpr <= 1 or not 0 <= self.reviewer_fpr < 1:
            raise ValueError("reviewer_tpr must be in (0, 1], reviewer_fpr in [0, 1)")
        if self.reviewer_tpr <= self.reviewer_fpr:
            raise ValueError("reviewer_tpr must exceed reviewer_fpr (reviewer must beat a coin)")


def thresholds(p: Prices) -> tuple[float, float]:
    """(t_lo, t_hi) on P(supported). Always t_lo <= t_hi; t_lo < t_hi iff a review band exists.

    When the reviewer is too dear or too weak for the review line to ever be cheapest, the
    note falls back to one threshold, where accepting and rejecting cost the same
    (p* = r / (a + r)); both returned values then equal 1 - p* and nothing routes to review.
    """
    a, r, h = p.wrong_accept, p.wrong_reject, p.review
    c, f = p.reviewer_tpr, p.reviewer_fpr
    keep = r * (1 - f)
    p_accept = (h + f * r) / (c * a + f * r)
    p_reject = (keep - h) / ((1 - c) * a + keep)
    if p_accept < p_reject:
        return 1 - p_reject, 1 - p_accept
    single = 1 - r / (a + r)
    return single, single
