"""Cost-based threshold selection — arithmetic, not a hyperparameter.

0.5 is a convention inherited from balanced data and symmetric costs. Almost no
real deployment has either. If a false negative costs 10× what a false positive
costs, the threshold that minimises expected cost is nowhere near 0.5, and
tuning it "until precision looks right" is choosing an operating point by feel
while pretending it came from the model.

This module is the deterministic-code-owns-the-decision boundary: the model
produces the content (probabilities), and a pure function over a cost matrix
produces the decision. Nothing here fits, samples, or reads global state — the
same inputs return the same result forever, which is what makes the chosen
threshold auditable after the fact.

Expected cost at threshold t, over n rows:

    cost(t) = cost_fp * FP(t) + cost_fn * FN(t)

Only the *ratio* of the two costs matters for the argmin; the absolute values
matter for reporting a number to a stakeholder, so both are kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ThresholdResult:
    """The chosen operating point and the evidence for it.

    `cost_at_default` is carried so a report can state what the 0.5 convention
    would have cost — the saving is the argument for having done this at all.
    """

    threshold: float
    expected_cost: float
    cost_at_default: float
    cost_fp: float
    cost_fn: float
    n_flagged: int
    precision: float
    recall: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    sweep: list[tuple[float, float]] = field(default_factory=list)
    """(threshold, expected_cost) over the candidate grid — the curve a report
    draws to show how flat or sharp the optimum is."""

    @property
    def savings_vs_default(self) -> float:
        """Cost avoided relative to thresholding at 0.5. Negative would mean the
        default was already better, which happens when costs are near-symmetric."""
        return self.cost_at_default - self.expected_cost

    @property
    def cost_ratio(self) -> float:
        return self.cost_fn / self.cost_fp


def expected_cost(
    y_true,
    y_prob,
    threshold: float,
    *,
    cost_fp: float,
    cost_fn: float,
    positive_label: Any = 1,
) -> float:
    """Total misclassification cost at one threshold. Pure."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    actual = (y_true == positive_label).astype(int)
    flagged = (y_prob >= threshold).astype(int)

    false_positives = int(np.sum((flagged == 1) & (actual == 0)))
    false_negatives = int(np.sum((flagged == 0) & (actual == 1)))
    return cost_fp * false_positives + cost_fn * false_negatives


def choose_threshold(
    y_true,
    y_prob,
    *,
    cost_fp: float,
    cost_fn: float,
    positive_label: Any = 1,
    candidates: Any = None,
) -> ThresholdResult:
    """Pick the threshold minimising expected cost. Pure function.

    The candidate grid defaults to the unique predicted probabilities, which is
    exact rather than approximate: the confusion matrix only changes as the
    threshold crosses an observed score, so every distinct operating point the
    data admits is in that set and a finer grid buys nothing. Ties break toward
    the **lower** threshold, which flags more rows — under an asymmetric cost
    matrix where `cost_fn > cost_fp`, that is the conservative side.

    Raises `ValueError` on non-positive costs: a zero cost makes one error class
    free, and the minimiser then degenerates to flagging everything or nothing —
    a result that looks like a decision but is an artefact of the input.
    """
    if cost_fp <= 0 or cost_fn <= 0:
        raise ValueError(
            f"costs must be positive, got cost_fp={cost_fp}, cost_fn={cost_fn}. "
            "A zero cost makes one error class free and the optimum degenerates "
            "to flagging everything or nothing."
        )

    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError(
            f"y_true has {len(y_true)} rows and y_prob has {len(y_prob)}; they must match"
        )
    if len(y_true) == 0:
        raise ValueError("cannot choose a threshold from an empty set of predictions")

    actual = (y_true == positive_label).astype(int)

    if candidates is None:
        grid = np.unique(y_prob)
    else:
        grid = np.unique(np.asarray(candidates, dtype=float))

    sweep: list[tuple[float, float]] = []
    best_threshold = float(grid[0])
    best_cost = float("inf")
    for t in grid:
        flagged = y_prob >= t
        false_positives = int(np.sum(flagged & (actual == 0)))
        false_negatives = int(np.sum(~flagged & (actual == 1)))
        cost = cost_fp * false_positives + cost_fn * false_negatives
        sweep.append((float(t), float(cost)))
        # Strict `<` with an ascending grid keeps the lowest threshold among ties.
        if cost < best_cost:
            best_cost = float(cost)
            best_threshold = float(t)

    flagged = y_prob >= best_threshold
    tp = int(np.sum(flagged & (actual == 1)))
    fp = int(np.sum(flagged & (actual == 0)))
    fn = int(np.sum(~flagged & (actual == 1)))
    tn = int(np.sum(~flagged & (actual == 0)))

    return ThresholdResult(
        threshold=best_threshold,
        expected_cost=best_cost,
        cost_at_default=expected_cost(
            y_true, y_prob, 0.5, cost_fp=cost_fp, cost_fn=cost_fn, positive_label=positive_label
        ),
        cost_fp=float(cost_fp),
        cost_fn=float(cost_fn),
        n_flagged=int(np.sum(flagged)),
        precision=tp / (tp + fp) if (tp + fp) else 0.0,
        recall=tp / (tp + fn) if (tp + fn) else 0.0,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        sweep=sweep,
    )


def threshold_for_capacity(y_prob, capacity: int) -> float:
    """The threshold that flags exactly `capacity` rows — the fixed-resource case.

    When the constraint is "the team can work 200 accounts a day", cost
    minimisation is the wrong frame: the budget is fixed and the only question is
    which 200. This returns the score of the `capacity`-th ranked row.
    """
    y_prob = np.asarray(y_prob, dtype=float)
    if capacity <= 0:
        raise ValueError(f"capacity must be positive, got {capacity}")
    if capacity >= len(y_prob):
        return float(np.min(y_prob))
    return float(np.sort(y_prob)[::-1][capacity - 1])
