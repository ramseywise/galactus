"""Aggregate summary of a classification result — never a row, an index, or an identifier.

Toolkit-free: consumes the result object structurally (`getattr` over metric fields), so
it imports nothing from `ml.*` and is unit-testable without `ML_PACKAGE_ROOT`.
"""

from __future__ import annotations

from pathlib import Path

from frame import COST_FN, COST_FP


def summarise(result, *, out: Path) -> dict:
    """Aggregates only — never a row, an index, or an identifier."""
    baseline = result.baseline
    best = result.best

    summary = {
        "n_rows": result.n_rows,
        "n_features": result.n_features,
        "sampling": result.sampling,
        "class_balance": result.class_balance,
        "split": {
            "kind": result.split_plan.kind if result.split_plan else None,
            "n_splits": result.split_plan.n_splits if result.split_plan else None,
        },
        "skipped": result.skipped,
        "beats_baseline": result.beats_baseline,
        "models": [],
        "report": str(out),
    }

    for model in result.models:
        entry = {
            "name": model.name,
            "is_baseline": model.is_baseline,
            "pr_auc": getattr(model.metrics, "average_precision", None),
            "roc_auc": getattr(model.metrics, "roc_auc", None),
            "brier": getattr(model.metrics, "brier_score", None),
            "fit_seconds": round(model.fit_seconds, 1),
        }
        if model.calibration is not None:
            entry["calibration"] = {
                "method": getattr(model.calibration, "method", None),
                "brier_before": getattr(model.calibration, "brier_before", None),
                "brier_after": getattr(model.calibration, "brier_after", None),
                "ece_before": getattr(model.calibration, "ece_before", None),
                "ece_after": getattr(model.calibration, "ece_after", None),
            }
        if model.threshold is not None:
            entry["threshold"] = {
                "value": round(model.threshold.threshold, 4),
                "precision": round(model.threshold.precision, 4),
                "recall": round(model.threshold.recall, 4),
                "n_flagged": model.threshold.n_flagged,
                "expected_cost": model.threshold.expected_cost,
                "cost_at_default": model.threshold.cost_at_default,
                "savings_vs_default": model.threshold.savings_vs_default,
                "STIPULATED_COSTS": {"cost_fp": COST_FP, "cost_fn": COST_FN},
                # LK-001. `choose_threshold` sweeps every observed probability and keeps
                # the cost-minimising one, then reports precision/recall at that point on
                # the same vector. The operating point is fitted on the rows it is scored
                # against, so these four numbers are optimistic. The headline PR-AUC and
                # ROC-AUC are unaffected — they are out-of-fold.
                "SELECTED_IN_SAMPLE": True,
            }
        summary["models"].append(entry)

    # The question the plan's Done-when actually asks. Recorded either way: "the honest
    # finding is recorded that it does not" is a pass, not a failure.
    if baseline is not None and best is not None:
        summary["verdict"] = {
            "baseline": baseline.name,
            "best": best.name,
            "baseline_pr_auc": getattr(baseline.metrics, "average_precision", None),
            "best_pr_auc": getattr(best.metrics, "average_precision", None),
        }
    return summary
