"""Verdict -> tier, band-rate guard, and the two operating-point views."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kg.config import DEFAULT_BAND_RATE_HALT
from kg.models import NotApplicable, Tier, Verdict


class BuildHalted(RuntimeError):  # noqa: N818 — name fixed by the plan
    """The review band is too large to queue; stop the build instead of making a wall of work."""


def assign(verdict: Verdict, t_lo: float, t_hi: float) -> Tier:
    """Route one verdict. `score` is P(supported).

    `unclear` -> review whatever the score (the judge said it could not decide). Otherwise
    the score decides, but a label that contradicts the score's side (not_supported with an
    accept-range score, supported with a reject-range score) goes to review: a disagreement
    inside one verdict is not evidence to act on automatically.
    """
    if verdict.label == "unclear":
        return "review"
    if verdict.score >= t_hi:
        return "accept" if verdict.label == "supported" else "review"
    if verdict.score <= t_lo:
        return "reject" if verdict.label == "not_supported" else "review"
    return "review"


def band_rate(tiers: Sequence[Tier]) -> float | NotApplicable:
    """Share of judged candidates routed to review; no denominator is named, never 0.0."""
    if not tiers:
        return NotApplicable("no judged candidates")
    return sum(t == "review" for t in tiers) / len(tiers)


def halt_if_over(rate: float | NotApplicable, limit: float = DEFAULT_BAND_RATE_HALT) -> None:
    """Raise BuildHalted when the band rate exceeds `limit`. NotApplicable never halts."""
    if isinstance(rate, NotApplicable):
        return
    if rate > limit:
        raise BuildHalted(f"review band rate {rate:.2f} exceeds limit {limit:.2f}")


def risk_coverage(scores: Sequence[float], labels: Sequence[bool]) -> list[tuple[float, float]]:
    """Selective-risk curve: accept the top-k by score; (coverage, error rate among accepted).

    `labels[i]` is True when the triple is truly supported. Tied scores enter together, so
    coverage is strictly increasing.
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels differ in length")
    n = len(scores)
    ranked = sorted(zip(scores, labels, strict=True), key=lambda x: -x[0])
    curve: list[tuple[float, float]] = []
    errors = 0
    i = 0
    while i < n:
        j = i
        while j < n and ranked[j][0] == ranked[i][0]:
            errors += not ranked[j][1]
            j += 1
        curve.append((j / n, errors / j))
        i = j
    return curve


@dataclass(frozen=True)
class FloorPoint:
    t_lo: float
    t_hi: float
    band_rate: float
    accept_precision: float
    reject_precision: float | NotApplicable


def floor_point(
    scores: Sequence[float], labels: Sequence[bool], precision: float = 0.90
) -> FloorPoint | NotApplicable:
    """Minimum-band operating point at a precision floor (OntoSmith's rule).

    t_hi: lowest threshold whose accepted set (score >= t_hi) is >= `precision` truly
    supported. t_lo: highest threshold whose rejected set (score < t_lo) is >= `precision`
    truly unsupported (t_lo = lowest score, rejecting nothing, if none qualifies). Precision
    is not monotone in the cut, so every distinct score is tried. The band is what lies
    between; t_lo is capped at t_hi. Compare with the priced `thresholds` to report both.
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels differ in length")
    if not scores:
        return NotApplicable("no labelled candidates")
    n = len(scores)
    cuts = sorted(set(scores))
    t_hi = next(
        (
            c
            for c in cuts
            if _frac([lab for s, lab in zip(scores, labels, strict=True) if s >= c], True)
            >= precision
        ),
        None,
    )
    if t_hi is None:
        return NotApplicable(f"no threshold reaches precision {precision:.2f}")
    acc = [lab for s, lab in zip(scores, labels, strict=True) if s >= t_hi]
    t_lo = cuts[0]
    rej_prec: float | NotApplicable = NotApplicable("nothing rejected")
    for c in reversed(cuts):
        rej = [lab for s, lab in zip(scores, labels, strict=True) if s < c]
        if rej and _frac(rej, False) >= precision:
            t_lo, rej_prec = c, _frac(rej, False)
            break
    t_lo = min(t_lo, t_hi)
    n_band = sum(t_lo <= s < t_hi for s in scores)
    return FloorPoint(t_lo, t_hi, n_band / n, _frac(acc, True), rej_prec)


def _frac(items: Sequence[bool], want: bool) -> float:
    return sum(x == want for x in items) / len(items) if items else 0.0
