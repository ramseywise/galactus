"""In-memory `RunRecord` assembly for the lending run.

Named `run_record`, not `record`: the tests put this run's `src/` on `sys.path`, and a
module called `record` would shadow `experiments.record` the moment anything imported
it flat. Toolkit-coupled — imports `experiments.*`, so it rides `ML_PACKAGE_ROOT` like
`splits.py`.

Per Key Decision 2 the registry shape is consumed as-is: a `NotApplicable` for seed or
folds in *this* record is a bug — a classification run has both — and the dataclasses'
own `__post_init__` validation fires on every construction (F2). Persistence is
deliberately absent here: writing records is `experiments/io.py`'s job (AIT#83), and a
local writer would de-facto define the format (Key Decision 3).
"""

from __future__ import annotations

import os
from pathlib import Path

from experiments.fingerprint import fingerprint_frame
from experiments.provenance import capture_code_state
from experiments.record import ExecutionConfig, NotApplicable, RunRecord

from frame import (
    COST_FN,
    COST_FP,
    FREE_TEXT_COLUMNS,
    GROUP_COL,
    GROUP_SOURCE_COLUMNS,
    IDENTIFIER_COLUMNS,
    LABEL_SOURCE_COLUMNS,
    LEAKAGE_COLUMNS,
    NEGATIVE_STATUSES,
    POSITIVE_STATUSES,
    SEED,
    TARGET,
)

#: .../galactus/runs/ml/lending/src/run_record.py → parents[4] is the repo root.
GALACTUS_ROOT = Path(__file__).resolve().parents[4]

_METRIC_FIELDS = (("pr_auc", "average_precision"), ("roc_auc", "roc_auc"), ("brier", "brier_score"))


def _toolkit_code_state() -> dict[str, object]:
    """The What-Breaks-First mitigation (F7): a second `capture_code_state` call pointed
    at the toolkit tree, so the record carries what fraud had to write by hand in prose.
    `capture_code_state` already returns `NotApplicable` for a non-repo path — zero new
    registry code."""
    toolkit_root = os.environ.get("ML_PACKAGE_ROOT")
    if toolkit_root:
        state = capture_code_state(repo=Path(toolkit_root))
        return {"root": toolkit_root, "git_sha": state.git_sha, "dirty": state.dirty}
    return {
        "root": None,
        "git_sha": NotApplicable(
            "ML_PACKAGE_ROOT unset — the toolkit reached sys.path by other means "
            "(e.g. PYTHONPATH in a test env), so there is no tree to fingerprint"
        ),
        "dirty": False,
    }


def assemble_run_record(result, fitted_df, args) -> RunRecord:
    """Build the in-memory record from a finished run.

    `fitted_df` must be the frame exactly as handed to `run_classification` — post
    drops, `GROUP_COL` removed, `TARGET` still present — so `frame_hash` answers
    "which frame were these numbers scored on", never "which file was on disk".
    """
    resolved_config: dict[str, object] = {
        # The module constants: the profile-doc-as-code, recorded post-default-merge —
        # constants that never appear on a command line are exactly what diverged in
        # Step 15.
        "target": TARGET,
        "group_col": GROUP_COL,
        "output": "binary",
        "sampling": "class_weight",
        "calibrate": True,
        "cost_fp": COST_FP,
        "cost_fn": COST_FN,
        "positive_statuses": sorted(POSITIVE_STATUSES),
        "negative_statuses": sorted(NEGATIVE_STATUSES),
        "leakage_columns": list(LEAKAGE_COLUMNS),
        "identifier_columns": list(IDENTIFIER_COLUMNS),
        "free_text_columns": list(FREE_TEXT_COLUMNS),
        "label_source_columns": list(LABEL_SOURCE_COLUMNS),
        "group_source_columns": list(GROUP_SOURCE_COLUMNS),
        # The post-parse CLI values.
        "n_splits": args.n_splits,
        "dry_run": bool(args.dry_run),
        "data": "synthetic:clean_frame" if args.dry_run else str(args.data),
        "models_arg": args.models,
        "models_run": [m.name for m in result.models],
        "sampling_applied": result.sampling,
        "toolkit": _toolkit_code_state(),
    }

    metrics: dict[str, float] = {"prevalence_floor": float(fitted_df[TARGET].mean())}
    for model in result.models:
        for suffix, attr in _METRIC_FIELDS:
            value = getattr(model.metrics, attr, None)
            if value is not None:
                metrics[f"{model.name}_{suffix}"] = float(value)

    plan = result.split_plan
    folds = (
        f"kind={plan.kind} n_splits={plan.n_splits} "
        f"reason={getattr(plan, 'reason', '<none recorded>')}"
    )

    return RunRecord(
        code=capture_code_state(repo=GALACTUS_ROOT),
        data=fingerprint_frame(fitted_df),
        execution=ExecutionConfig(
            # A classification run always has both; NotApplicable here is a bug
            # (Key Decision 2), and `__post_init__` rejects a bare None outright.
            seed=SEED,
            resolved_config=resolved_config,
            folds=folds,
        ),
        metrics=metrics,
        headline_metric=f"{result.baseline.name}_pr_auc",
        run_kind="classification",
    )
