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
    fold_thresholds: tuple[float, ...] = ()
    """The threshold each fold's selection chose, when the result came from
    `choose_threshold_out_of_fold`. The spread is the stability evidence: fold
    thresholds that agree mean the optimum is a property of the problem; fold
    thresholds that scatter mean the sweep curve is flat and the chosen point
    is substantially noise. Empty for a single-pass `choose_threshold`."""
    in_sample: bool = True
    """Whether `threshold` was selected on the same rows the metrics below
    describe.

    `True` — the default, because it is what `choose_threshold` does — means
    `precision`, `recall`, and `expected_cost` are optimistic: the threshold was
    fitted to minimise cost on these exact rows, so it has absorbed their noise
    and a fresh sample will score worse. The size of the gap depends on how flat
    the `sweep` curve is around the optimum.

    Set `False` only when the threshold came from rows disjoint from the ones
    being scored — chosen on a validation fold and measured on a held-out one.
    Carried as a field rather than left to the docstring so a report can state
    the caveat without its author having had to know to add it."""

    @property
    def selection_caveat(self) -> str | None:
        """The sentence a report should print next to `precision`/`recall`, or
        `None` when the threshold was chosen out-of-sample and needs no caveat."""
        if not self.in_sample:
            return None
        return (
            "Threshold chosen on the same rows these metrics describe, so precision "
            "and recall are optimistic — the operating point is fitted to this "
            "sample's noise. Expect a fresh sample to score lower."
        )

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
    in_sample: bool = True,
) -> ThresholdResult:
    """Pick the threshold minimising expected cost. Pure function.

    The candidate grid defaults to the unique predicted probabilities, which is
    exact rather than approximate: the confusion matrix only changes as the
    threshold crosses an observed score, so every distinct operating point the
    data admits is in that set and a finer grid buys nothing. Ties break toward
    the **lower** threshold, which flags more rows — under an asymmetric cost
    matrix where `cost_fn > cost_fp`, that is the conservative side.

    **The returned metrics are in-sample by default.** The threshold is fitted to
    these rows, so the `precision` and `recall` measured at it are optimistic in
    the same way any fitted quantity scored on its own training data is. The
    result carries `in_sample=True` and a `selection_caveat` saying so, so a
    report states it without the caller having to know. Pass `in_sample=False`
    when the rows scored here are disjoint from the rows the threshold was chosen
    on — that is the arrangement that makes these numbers an honest estimate.

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
        in_sample=in_sample,
    )


def choose_threshold_out_of_fold(
    y_true,
    y_prob,
    folds,
    *,
    cost_fp: float,
    cost_fn: float,
    positive_label: Any = 1,
) -> ThresholdResult:
    """Select the threshold out-of-fold, so the operating-point metrics are honest.

    `choose_threshold` fits the threshold to the rows it then scores, so its
    precision/recall/`expected_cost` are optimistic — the operating point has
    absorbed those rows' noise. This variant closes that gap with the same move
    cross-validation applies to the model itself: for each fold, the threshold
    is chosen on every *other* fold's rows and evaluated on this fold's, so no
    row is ever scored at a threshold that saw it. The reported confusion
    counts, precision, recall, `n_flagged`, and `expected_cost` are pooled over
    those held-out evaluations.

    The returned `threshold` is the deployable one — chosen over all rows,
    exactly what `choose_threshold` would pick — while the metrics beside it
    estimate what *deploying a threshold chosen this way* costs on rows the
    selection never saw. The two are deliberately not the same computation:
    the reported cost is the honest estimate for the procedure, not the
    in-sample cost of the reported point. `fold_thresholds` carries the
    per-fold choices so a report can show whether the optimum is stable or a
    coin-flip across resamples.

    `folds` is a sequence of `(train_idx, test_idx)` pairs — the same list
    handed to `cross_val_predict`, so `y_prob` should be that call's
    out-of-fold probabilities. Only the test indices are used. They must
    partition the rows: an overlap would score a row at a threshold that saw
    it, and a gap would leave rows silently unevaluated.
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

    test_folds = [np.asarray(test_idx, dtype=int) for _, test_idx in folds]
    if len(test_folds) < 2:
        raise ValueError(
            f"out-of-fold selection needs at least 2 folds, got {len(test_folds)}. "
            "With one fold there are no other rows to choose the threshold on."
        )
    covered = np.concatenate(test_folds)
    if len(covered) != len(np.unique(covered)):
        raise ValueError(
            "test folds overlap — a row appearing in two folds would be scored "
            "at a threshold selected on rows that include it."
        )
    if len(covered) != len(y_true):
        raise ValueError(
            f"test folds cover {len(covered)} of {len(y_true)} rows. Every row "
            "needs exactly one held-out evaluation; a gap would silently drop "
            "rows from the reported metrics."
        )

    actual = (y_true == positive_label).astype(int)

    fold_thresholds: list[float] = []
    tp = fp = fn = tn = 0
    for test_idx in test_folds:
        selection = np.setdiff1d(covered, test_idx)
        fold_choice = choose_threshold(
            y_true[selection],
            y_prob[selection],
            cost_fp=cost_fp,
            cost_fn=cost_fn,
            positive_label=positive_label,
        )
        fold_thresholds.append(fold_choice.threshold)

        flagged = y_prob[test_idx] >= fold_choice.threshold
        fold_actual = actual[test_idx]
        tp += int(np.sum(flagged & (fold_actual == 1)))
        fp += int(np.sum(flagged & (fold_actual == 0)))
        fn += int(np.sum(~flagged & (fold_actual == 1)))
        tn += int(np.sum(~flagged & (fold_actual == 0)))

    # The deployable point: selected over all rows, same as choose_threshold
    # would return. Its sweep is kept for the report's curve; its in-sample
    # metrics are discarded in favour of the pooled held-out ones above.
    deployable = choose_threshold(
        y_true, y_prob, cost_fp=cost_fp, cost_fn=cost_fn, positive_label=positive_label
    )

    return ThresholdResult(
        threshold=deployable.threshold,
        expected_cost=float(cost_fp * fp + cost_fn * fn),
        cost_at_default=deployable.cost_at_default,
        cost_fp=float(cost_fp),
        cost_fn=float(cost_fn),
        n_flagged=tp + fp,
        precision=tp / (tp + fp) if (tp + fp) else 0.0,
        recall=tp / (tp + fn) if (tp + fn) else 0.0,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        sweep=deployable.sweep,
        in_sample=False,
        fold_thresholds=tuple(fold_thresholds),
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
