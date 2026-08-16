"""Deterministic leakage guards — abort, never warn.

The four guards of the MVP set (Key Decision 6 semantics: a violation raises
`GuardError` naming the offending columns; a warning in a long log is silent failure):

    (a) `assert_excluded_absent`     — no excluded column survives into the fitted frame
    (b) `single_feature_auc_alarm`   — a lone near-perfect predictor is a leak until argued
    (c) `assert_no_group_leakage`    — the toolkit's own check, called in `splits.py`
                                       at the moment the folds are computed
    (d) `final_metric_alarm`         — a near-perfect *model* after the fit is a leak too

Toolkit-free: pandas + scikit-learn only, importable without `ML_PACKAGE_ROOT`, so every
guard has unit tests that always run.
"""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import roc_auc_score

from frame import (
    FREE_TEXT_COLUMNS,
    GROUP_SOURCE_COLUMNS,
    IDENTIFIER_COLUMNS,
    LABEL_SOURCE_COLUMNS,
    LEAKAGE_COLUMNS,
    TARGET,
)

#: Every column that must not reach the fit. `TARGET` and `GROUP_COL` are handled
#: mechanically by the harness (label and fold plan), so they are not in this list —
#: the guards run on the frame *before* those two are stripped.
EXCLUDED_FOR_FIT = (
    LEAKAGE_COLUMNS
    + IDENTIFIER_COLUMNS
    + FREE_TEXT_COLUMNS
    + LABEL_SOURCE_COLUMNS
    + GROUP_SOURCE_COLUMNS
)


class GuardError(SystemExit):
    """Abort, not warn — a warning in a long log is silent failure."""


def assert_excluded_absent(df: pd.DataFrame) -> None:
    """Guard (a): no member of the exclusion lists survives into the fitted frame.

    `prepare_frame` drops these columns; this guard asserts the drop actually held, so a
    refactor that reorders the pipeline (or a fixture that sneaks a column back in)
    fails loudly instead of inflating every score downstream.
    """
    present = [c for c in EXCLUDED_FOR_FIT if c in df.columns]
    if present:
        raise GuardError(f"excluded columns present in fitted frame: {present}")


def single_feature_auc_alarm(
    df: pd.DataFrame,
    target: str = TARGET,
    threshold: float = 0.95,
    allowlist: tuple[str, ...] = (),
) -> None:
    """Guard (b): a single numeric column that nearly separates the label is a leak.

    Per-column ROC-AUC over rank-comparable (numeric, non-constant) columns. A column
    over `threshold` that is not allowlisted aborts — the allowlist friction is the
    feature: overriding the alarm requires naming the column and arguing it in review.
    """
    y = df[target]
    offenders = []
    numeric = df.select_dtypes(include="number").drop(
        columns=[c for c in (target,) if c in df.columns], errors="ignore"
    )
    for col in numeric.columns:
        series = numeric[col]
        mask = series.notna()
        # AUC needs both classes and at least two distinct values to rank.
        if mask.sum() == 0 or y[mask].nunique() < 2 or series[mask].nunique() < 2:
            continue
        auc = roc_auc_score(y[mask], series[mask])
        # Direction-free: a perfect *negative* ranker separates just as well.
        auc = max(auc, 1.0 - auc)
        if auc >= threshold and col not in allowlist:
            offenders.append((col, round(float(auc), 4)))
    if offenders:
        raise GuardError(
            f"single-feature AUC alarm (threshold {threshold}): {offenders}. "
            "A lone near-perfect predictor is post-outcome information until argued "
            "otherwise; allowlist it explicitly if it is genuinely legitimate."
        )


def final_metric_alarm(metrics: dict[str, float], threshold: float = 0.95) -> None:
    """Guard (d): a near-perfect model after the fit means a leak got through.

    Takes a flat `{model_name: roc_auc}` map. The lending frame's honest ceiling is far
    below 0.95 (DESIGN.md: including post-outcome columns takes ROC-AUC to 0.9993) —
    any model up there is running on information the borrower's future provided.
    """
    offenders = {
        name: round(float(auc), 4)
        for name, auc in metrics.items()
        if auc is not None and auc >= threshold
    }
    if offenders:
        raise GuardError(
            f"final-metric alarm (threshold {threshold}): {offenders}. "
            "A score this high on this frame means post-outcome information reached "
            "the fit; find the leak before trusting any number in the run."
        )
