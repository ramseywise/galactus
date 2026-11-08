"""Judge-seat calibration against human gold: pure functions, no model calls.

Each seat is an instrument. It is scored on `split=test` only, per seat, and every figure
carries its `n`. A metric with no denominator is `NotApplicable`, never 0.0.

Conventions (decided here, stated so no reader has to guess):

* Truth: a gold row is *supported* iff `gold == "positive"`; `hard_negative` and `control`
  rows are *not supported*.
* Prediction: a seat predicts *supported* iff its label is `supported`. `unclear` counts as
  not supported, because the router sends it to review rather than accepting it.
* `not_run` (the seat returned no verdict) is excluded from every rate and counted in
  `n_not_run`. It is never read as a prediction.
* When a seat has several repeats, the first repeat supplies every metric except test-retest;
  pooling repeats would inflate `n` with non-independent rows.
* `score` is read as the seat's P(supported); ECE assumes that.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from kg.models import NotApplicable, SeatLabel

Z95 = 1.96
ECE_BINS = 10


@dataclass(frozen=True)
class Obs:
    """One seat call on one gold row. `label is None` means the seat did not run."""

    id: str
    gold: str  # positive | hard_negative | control
    split: str  # train | dev | test
    label: SeatLabel | None
    score: float | None = None


@dataclass(frozen=True)
class Confusion:
    tp: int
    fn: int
    fp: int
    tn: int
    not_run: int = 0

    @property
    def n(self) -> int:
        return self.tp + self.fn + self.fp + self.tn


@dataclass(frozen=True)
class Rate:
    value: float
    n: int  # the denominator the rate was computed on


@dataclass(frozen=True)
class Kappa:
    value: float
    lo: float
    hi: float
    n: int


@dataclass(frozen=True)
class SeatCalibration:
    seat: str
    n_test: int
    n_not_run: int
    confusion: Confusion
    tpr: Rate | NotApplicable
    tnr: Rate | NotApplicable
    kappa: Kappa | NotApplicable
    ece: Rate | NotApplicable
    retest: Rate | NotApplicable
    hard_negative_precision: Rate | NotApplicable
    hard_negative_tnr: Rate | NotApplicable
    control_tnr: Rate | NotApplicable


def _truth(o: Obs) -> bool:
    return o.gold == "positive"


def confusion(obs: Sequence[Obs]) -> Confusion:
    tp = fn = fp = tn = not_run = 0
    for o in obs:
        if o.label is None:
            not_run += 1
            continue
        pred = o.label == "supported"
        if _truth(o):
            tp, fn = (tp + 1, fn) if pred else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if pred else (fp, tn + 1)
    return Confusion(tp, fn, fp, tn, not_run)


def _rate(num: int, den: int, what: str) -> Rate | NotApplicable:
    if den == 0:
        return NotApplicable(f"no {what}")
    return Rate(num / den, den)


def tpr(c: Confusion) -> Rate | NotApplicable:
    """True-positive rate: supported triples the seat called supported."""
    return _rate(c.tp, c.tp + c.fn, "positive rows with a verdict")


def tnr(c: Confusion) -> Rate | NotApplicable:
    """True-negative rate: unsupported triples the seat did not accept."""
    return _rate(c.tn, c.tn + c.fp, "negative rows with a verdict")


def wilson(successes: int, n: int, z: float = Z95) -> tuple[float, float] | NotApplicable:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return NotApplicable("no observations")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def cohens_kappa(c: Confusion) -> Kappa | NotApplicable:
    """Cohen's κ = (p_o - p_e) / (1 - p_e) between the seat and the human label.

    The Wilson interval is computed on the **observed agreement** p_o = (tp + tn) / n, the
    only binomial proportion in κ, and mapped through κ(p) = (p - p_e) / (1 - p_e) with the
    chance agreement p_e held fixed. κ is monotone in p_o, so the endpoints map directly.
    This is an approximation: it ignores the sampling variance of p_e, so it is slightly
    narrower than the large-sample κ interval. NotApplicable when n = 0 or p_e = 1 (one
    class on both sides, where κ is undefined).
    """
    n = c.n
    if n == 0:
        return NotApplicable("no rows with a verdict")
    actual_pos, actual_neg = c.tp + c.fn, c.tn + c.fp
    pred_pos, pred_neg = c.tp + c.fp, c.tn + c.fn
    p_e = (actual_pos * pred_pos + actual_neg * pred_neg) / (n * n)
    if p_e >= 1.0:
        return NotApplicable("kappa undefined: chance agreement is 1 (a single class)")
    interval = wilson(c.tp + c.tn, n)
    assert not isinstance(interval, NotApplicable)

    def to_kappa(p: float) -> float:
        return (p - p_e) / (1 - p_e)

    return Kappa(to_kappa((c.tp + c.tn) / n), to_kappa(interval[0]), to_kappa(interval[1]), n)


def expected_calibration_error(
    scores: Sequence[float], truths: Sequence[bool], bins: int = ECE_BINS
) -> Rate | NotApplicable:
    """ECE = sum over bins of (|bin| / n) * |mean(truth) - mean(score)|; `n` is the row count.

    Equal-width bins on [0, 1]; a score of exactly 1.0 falls in the last bin.
    """
    if len(scores) != len(truths):
        raise ValueError("scores and truths differ in length")
    n = len(scores)
    if n == 0:
        return NotApplicable("no scored rows")
    members: list[list[int]] = [[] for _ in range(bins)]
    for i, s in enumerate(scores):
        if not 0.0 <= s <= 1.0:
            raise ValueError(f"score {s} outside [0, 1]")
        members[min(int(s * bins), bins - 1)].append(i)
    total = 0.0
    for idx in members:
        if idx:
            conf = sum(scores[i] for i in idx) / len(idx)
            acc = sum(truths[i] for i in idx) / len(idx)
            total += len(idx) / n * abs(acc - conf)
    return Rate(total, n)


def test_retest(repeats: Sequence[Sequence[Obs]]) -> Rate | NotApplicable:
    """Mean pairwise agreement of the supported/not-supported call across repeats.

    Rows are matched by id; a row any repeat did not run is dropped. `n` is the number of
    rows compared. This measures repeatability, not validity: a repeatable judge
    reproduces its bias exactly.
    """
    if len(repeats) < 2:
        return NotApplicable("fewer than two repeats")
    maps = [{o.id: o.label for o in rep} for rep in repeats]
    ids = set(maps[0]).intersection(*maps[1:])
    ids = {i for i in ids if all(m[i] is not None for m in maps)}
    if not ids:
        return NotApplicable("no row ran in every repeat")
    k = len(maps)
    pairs = k * (k - 1) // 2
    agree = 0.0
    for i in ids:
        calls = [m[i] == "supported" for m in maps]
        agree += sum(calls[a] == calls[b] for a in range(k) for b in range(a + 1, k)) / pairs
    return Rate(agree / len(ids), len(ids))


def hard_negative_precision(obs: Sequence[Obs]) -> Rate | NotApplicable:
    """Precision of `supported` calls over positives and *hard negatives only* (spec F3).

    tp / (tp + fp_hard): of everything the seat accepted from the pool where the quote is
    verbatim and the entities are right, how much was truly supported. Controls are left
    out so injection resistance does not mask relation errors. `n` is the accepted count.
    """
    accepted = [
        o for o in obs if o.label == "supported" and o.gold in ("positive", "hard_negative")
    ]
    tp = sum(o.gold == "positive" for o in accepted)
    return _rate(tp, len(accepted), "accepted positive-or-hard-negative rows")


def _tnr_of(obs: Sequence[Obs], gold: str) -> Rate | NotApplicable:
    pool = [o for o in obs if o.gold == gold and o.label is not None]
    return _rate(
        sum(o.label != "supported" for o in pool), len(pool), f"{gold} rows with a verdict"
    )


def calibrate_seat(
    seat: str, repeats: Sequence[Sequence[Obs]], *, split: str = "test"
) -> SeatCalibration:
    """Metrics for one seat. `repeats[0]` supplies everything but test-retest."""
    scoped = [[o for o in rep if o.split == split] for rep in repeats]
    primary = scoped[0] if scoped else []
    c = confusion(primary)
    scored = [o for o in primary if o.label is not None and o.score is not None]
    return SeatCalibration(
        seat=seat,
        n_test=len(primary),
        n_not_run=c.not_run,
        confusion=c,
        tpr=tpr(c),
        tnr=tnr(c),
        kappa=cohens_kappa(c),
        ece=expected_calibration_error(
            [o.score for o in scored if o.score is not None], [_truth(o) for o in scored]
        ),
        retest=test_retest(scoped),
        hard_negative_precision=hard_negative_precision(primary),
        hard_negative_tnr=_tnr_of(primary, "hard_negative"),
        control_tnr=_tnr_of(primary, "control"),
    )


def calibrate(
    by_seat: Mapping[str, Sequence[Sequence[Obs]]], *, split: str = "test"
) -> dict[str, SeatCalibration]:
    """Per-seat calibration. `by_seat[name]` is a list of repeats, each a list of `Obs`."""
    return {name: calibrate_seat(name, reps, split=split) for name, reps in by_seat.items()}
