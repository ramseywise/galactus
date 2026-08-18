"""In-memory RunRecord assembly for the fraud run.

Named `fraud_record` (not `record`) to avoid shadowing `experiments.record`.
Every field is concrete — `NotApplicable` is not used because fraud always has
a seed, always has folds, and the refusal (when it occurs) is carried in
`resolved_config` as the withheld-costs fact, not as a missing field.
"""

from __future__ import annotations

from experiments.fingerprint import fingerprint_frame
from experiments.provenance import capture_code_state
from experiments.record import ExecutionConfig, RunRecord

from runs._shared.parity import GALACTUS_ROOT, toolkit_code_state


def assemble_fraud_record(result, fitted_df, *, seed, n_splits, verdict, dry_run) -> RunRecord:
    """Build the in-memory record from a finished fraud run."""
    resolved_config: dict[str, object] = {
        "target": "default",
        "output": "binary",
        "sampling": "class_weight",
        "calibrate": True,
        "n_splits": n_splits,
        "dry_run": dry_run,
        "models_run": [m.name for m in result.models],
        "toolkit": toolkit_code_state(),
        "sufficiency": {
            "sufficient": verdict.sufficient,
            "min_positives_in_fold": verdict.min_positives_in_fold,
            "n_positives": verdict.n_positives,
            "reason": verdict.reason,
        },
    }

    metrics: dict[str, float] = {"prevalence_floor": verdict.prevalence}
    for model in result.models:
        pr_auc = getattr(model.metrics, "average_precision", None)
        if pr_auc is not None:
            metrics[f"{model.name}_pr_auc"] = float(pr_auc)
        roc_auc = getattr(model.metrics, "roc_auc", None)
        if roc_auc is not None:
            metrics[f"{model.name}_roc_auc"] = float(roc_auc)

    plan = result.split_plan
    folds = (
        f"kind={plan.kind} n_splits={plan.n_splits} "
        f"reason={getattr(plan, 'reason', '<none recorded>')}"
    )

    return RunRecord(
        code=capture_code_state(repo=GALACTUS_ROOT),
        data=fingerprint_frame(fitted_df),
        execution=ExecutionConfig(seed=seed, resolved_config=resolved_config, folds=folds),
        metrics=metrics,
        headline_metric=f"{result.baseline.name}_pr_auc",
        run_kind="classification",
    )
