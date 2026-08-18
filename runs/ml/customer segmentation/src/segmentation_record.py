"""In-memory RunRecord assembly for the segmentation run.

The unsupervised shape: `folds=NotApplicable` (no split concept),
`seed=RANDOM_STATE` (the run IS seeded — KMeans, silhouette sample, baseline).
"""

from __future__ import annotations

from experiments.fingerprint import fingerprint_frame
from experiments.provenance import capture_code_state
from experiments.record import ExecutionConfig, NotApplicable, RunRecord
from runs._shared.parity import GALACTUS_ROOT, toolkit_code_state


def assemble_segmentation_record(
    features_df,
    results,
    winner,
    *,
    seed: int,
    dry_run: bool,
    findings: list,
) -> RunRecord:
    """Build the in-memory record from a finished segmentation run."""
    resolved_config: dict[str, object] = {
        "output": "clustering",
        "k_range": [r.k for r in results] if results else [],
        "chosen_k": winner.k if winner else None,
        "dry_run": dry_run,
        "toolkit": toolkit_code_state(),
        "leakage": [{"rule": f.rule, "passed": f.passed, "detail": f.detail} for f in findings],
        "refused": winner is None,
    }

    metrics: dict[str, float] = {}
    if winner:
        metrics["silhouette"] = float(winner.silhouette)
        metrics["davies_bouldin"] = float(winner.davies_bouldin)
        metrics["baseline_random"] = float(winner.baseline_random)
        metrics["baseline_k2"] = float(winner.baseline_k2)

    # Even a refused run carries the best silhouette across the sweep as the
    # headline, or 0.0 if no sweep ran at all.
    if results:
        best_sil = max(r.silhouette for r in results)
        metrics["best_silhouette"] = float(best_sil)
        headline = "best_silhouette"
    else:
        metrics["best_silhouette"] = 0.0
        headline = "best_silhouette"

    return RunRecord(
        code=capture_code_state(repo=GALACTUS_ROOT),
        data=fingerprint_frame(features_df),
        execution=ExecutionConfig(
            seed=seed,
            resolved_config=resolved_config,
            folds=NotApplicable(
                "unsupervised clustering — no train/test split concept; "
                "the entire frame is clustered"
            ),
        ),
        metrics=metrics,
        headline_metric=headline,
        run_kind="segmentation",
    )
