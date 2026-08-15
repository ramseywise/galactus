"""The sufficiency guard — refusal as a first-class result, not an exception.

The toolkit's existing refusal vocabulary — `TemporalLeakageError`, `GroupLeakageError`,
`TransformLeakageError` — guards *leakage*: a caller's arguments contradict the shape of
the data, and continuing would silently produce a number that does not mean what it
claims. This module guards a different failure: *insufficiency*. The arguments are
consistent and the data is not leaked, and the toolkit will still produce a
cost-minimising threshold over two or three positive examples, printed to four decimal
places with a `savings_vs_default` figure, as if it were a decision.

A `ValueError` subclass is the wrong shape for that. Insufficiency is not a contradiction
in the caller's request — the request ("choose a threshold") is perfectly answerable in
the arithmetic sense. It is unanswerable in the sense that matters: the answer would not
generalise past the exact rows it was fit on. That is a fact about the evidence, not a
bug in the call, so this module returns a verdict rather than raising. **A run that
refuses is not a run that failed** — it completed, inspected its own evidence, and
declined to make a claim the evidence cannot support. `assess_sufficiency` never raises,
never fits a model, and never touches the filesystem: the same `(y, split_plan)` pair
returns the same verdict forever, which is what makes a refusal reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

MIN_POSITIVES_PER_FOLD = 10
"""Below this many positives in the thinnest test fold, no operating point is reported.

A threshold is chosen by minimising expected cost over observed probabilities, and its
precision/recall are then read off the same rows. With 2-3 positives per fold that
arithmetic still returns a number to four decimal places — it is simply a number about
three events. Measured on this frame the toolkit returned threshold 0.0562, precision
0.000, recall 0.000, true_positives 0, and reported it with no warning at all. The
discrimination metrics survive (they are computed over every scored row); the operating
point does not.
"""


@dataclass(frozen=True)
class SufficiencyVerdict:
    """Whether the thinnest test fold has enough positive evidence to support a
    cost-minimising threshold, and why. Aggregates only — carries counts, never rows."""

    sufficient: bool
    reason: str
    n_positives: int
    min_positives_in_fold: int
    prevalence: float

    @property
    def threshold_reportable(self) -> bool:
        """Alias for `sufficient`, named for the call site that reads it (`main()`
        deciding whether to pass costs into `run_classification`) rather than for what
        computed it — the two questions happen to have the same answer today, and naming
        the property after its use keeps that call site readable on its own."""
        return self.sufficient


def assess_sufficiency(
    y: Any,
    split_plan: Any,
    *,
    min_per_fold: int = MIN_POSITIVES_PER_FOLD,
) -> SufficiencyVerdict:
    """Count positives in every test fold `split_plan` would produce, and verdict on the
    thinnest one — not the mean.

    A frame can average comfortably above the line while one fold sits far below it: four
    folds at 40 positives and one at 2 averages to 32, which hides the exact fold a
    cost-minimising threshold would be evaluated against. Every fold's test split is
    scored during cross-validation, so the guard has to survive its worst fold, not its
    typical one.

    Pure: does not fit a model, does not read or write anything, and never raises. An
    empty or all-negative `y` reports `sufficient=False` with `min_positives_in_fold=0`
    rather than dividing by zero or raising — insufficiency is exactly the condition this
    function exists to describe, so the zero case is a normal answer, not a failure of
    the function.
    """
    y_arr = np.asarray(y)
    n_rows = len(y_arr)
    n_positives = int(np.sum(y_arr == 1))
    prevalence = float(n_positives / n_rows) if n_rows else 0.0

    fold_counts = [
        int(np.sum(y_arr[test_idx] == 1))
        for _, test_idx in split_plan.split(np.zeros((n_rows, 1)), y_arr)
    ]
    min_positives_in_fold = min(fold_counts) if fold_counts else 0

    sufficient = min_positives_in_fold >= min_per_fold

    if sufficient:
        reason = (
            f"every test fold holds at least {min_per_fold} positives (thinnest: "
            f"{min_positives_in_fold}); a cost-minimising threshold is supported by "
            "enough evidence to be more than an artefact of which rows landed where."
        )
    else:
        reason = (
            f"the thinnest test fold holds only {min_positives_in_fold} positive "
            f"case(s), below the {min_per_fold}-positive floor ({n_positives} positives "
            f"across the frame, {prevalence:.2%} prevalence). A threshold chosen and "
            "scored over that few events is arithmetic, not evidence — no operating "
            "point is reported."
        )

    return SufficiencyVerdict(
        sufficient=sufficient,
        reason=reason,
        n_positives=n_positives,
        min_positives_in_fold=min_positives_in_fold,
        prevalence=prevalence,
    )
