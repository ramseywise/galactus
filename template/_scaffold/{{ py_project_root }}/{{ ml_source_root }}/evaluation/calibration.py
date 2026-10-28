"""Probability calibration — making 0.7 mean "roughly 70% of these pay".

Calibration is usually filed under polish. Here it is a **correctness property**,
because of what consumes the output: `threshold.choose_threshold` computes an
expected cost by multiplying probabilities against a cost matrix. That arithmetic
is only meaningful if the probabilities are probabilities. A model that ranks
perfectly but outputs 0.9 for everything has a fine ROC-AUC and makes the cost
calculation return nonsense — it will recommend contacting everyone or no one.

Tree ensembles are the common offender: averaging over trees pushes predictions
toward the middle, and boosting with a log-loss objective often pushes them
toward the extremes. Neither is wrong as a *ranking*; both are wrong as
*probabilities*.

Which calibrator to use:

- **sigmoid** (Platt) fits two parameters. Correct when the distortion is
  monotone and roughly S-shaped, and it is the safe choice on small validation
  sets because two parameters cannot overfit much.
- **isotonic** fits an arbitrary monotone step function. Strictly more flexible,
  and strictly more able to overfit — the usual guidance is >1000 validation
  rows before preferring it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

from ml.evaluation.metrics import CurvePoints

Method = Literal["sigmoid", "isotonic"]

DEFAULT_ISOTONIC_MIN_SAMPLES = 1000
"""Below this many rows, isotonic regression tends to fit the validation noise;
`recommend_method` falls back to sigmoid."""


@dataclass(frozen=True)
class CalibrationReport:
    """Before/after evidence that calibration did something — or did not.

    `improved` is the honest bit. Calibration is not guaranteed to help, and a
    report that only ever says "calibrated" teaches the reader nothing. When the
    Brier score gets worse, that is worth seeing.
    """

    method: str
    brier_before: float
    brier_after: float
    expected_calibration_error_before: float
    expected_calibration_error_after: float
    curve_before: CurvePoints
    curve_after: CurvePoints
    n_bins: int

    @property
    def improved(self) -> bool:
        return self.brier_after < self.brier_before

    @property
    def brier_delta(self) -> float:
        """Negative is better — the reduction in Brier score."""
        return self.brier_after - self.brier_before

    @property
    def ece_before(self) -> float:
        """Short alias — reports abbreviate expected calibration error to ECE."""
        return self.expected_calibration_error_before

    @property
    def ece_after(self) -> float:
        return self.expected_calibration_error_after


def recommend_method(n_samples: int) -> Method:
    """sigmoid on small validation sets, isotonic when there is enough data."""
    return "isotonic" if n_samples >= DEFAULT_ISOTONIC_MIN_SAMPLES else "sigmoid"


def reliability_curve(y_true, y_prob, *, n_bins: int = 10) -> CurvePoints:
    """Mean predicted probability vs. observed frequency, per bin.

    A perfectly calibrated model lies on the diagonal. Empty bins are dropped
    rather than plotted at zero, which would draw a line to the origin that no
    data supports.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # right=False with a final-bin fix so p == 1.0 lands in the last bin rather
    # than in an out-of-range index.
    bin_ids = np.clip(np.digitize(y_prob, edges[1:-1], right=False), 0, n_bins - 1)

    predicted: list[float] = []
    observed: list[float] = []
    for b in range(n_bins):
        mask = bin_ids == b
        if not np.any(mask):
            continue
        predicted.append(float(np.mean(y_prob[mask])))
        observed.append(float(np.mean(y_true[mask])))

    return CurvePoints(
        x=predicted,
        y=observed,
        label="reliability",
        x_label="mean predicted probability",
        y_label="observed frequency",
        baseline=None,
    )


def expected_calibration_error(y_true, y_prob, *, n_bins: int = 10) -> float:
    """ECE — the bin-count-weighted mean gap between confidence and accuracy.

    A single number for "how far off are the probabilities", where the Brier
    score conflates calibration with discrimination. Weighted by bin population
    so a nearly-empty extreme bin cannot dominate.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_ids = np.clip(np.digitize(y_prob, edges[1:-1], right=False), 0, n_bins - 1)

    total = 0.0
    for b in range(n_bins):
        mask = bin_ids == b
        count = int(np.sum(mask))
        if count == 0:
            continue
        gap = abs(float(np.mean(y_true[mask])) - float(np.mean(y_prob[mask])))
        total += (count / len(y_true)) * gap
    return total


def calibrate_classifier(
    estimator: Any,
    *,
    method: Method = "sigmoid",
    cv: Any = 5,
    ensemble: bool = True,
) -> CalibratedClassifierCV:
    """Wrap an estimator in `CalibratedClassifierCV`.

    `cv="prefit"` calibrates an already-fitted estimator against a held-out set;
    an integer cross-validates, refitting the base estimator per fold. The
    integer form is the leakage-safe default: with `"prefit"` it is the caller's
    responsibility to have kept the calibration rows out of training, and that
    responsibility is easy to forget.
    """
    if method not in ("sigmoid", "isotonic"):
        raise ValueError(f"unknown calibration method {method!r}; valid: sigmoid, isotonic")
    return CalibratedClassifierCV(estimator, method=method, cv=cv, ensemble=ensemble)


def assess_calibration(
    y_true,
    prob_before,
    prob_after,
    *,
    method: str,
    n_bins: int = 10,
    positive_label: Any = 1,
) -> CalibrationReport:
    """Build the before/after report from two probability vectors."""
    y_true = np.asarray(y_true)
    binary_true = (y_true == positive_label).astype(int)
    before = np.asarray(prob_before, dtype=float)
    after = np.asarray(prob_after, dtype=float)

    return CalibrationReport(
        method=method,
        brier_before=float(brier_score_loss(binary_true, before)),
        brier_after=float(brier_score_loss(binary_true, after)),
        expected_calibration_error_before=expected_calibration_error(
            binary_true, before, n_bins=n_bins
        ),
        expected_calibration_error_after=expected_calibration_error(
            binary_true, after, n_bins=n_bins
        ),
        curve_before=reliability_curve(binary_true, before, n_bins=n_bins),
        curve_after=reliability_curve(binary_true, after, n_bins=n_bins),
        n_bins=n_bins,
    )
