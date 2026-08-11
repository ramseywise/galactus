"""ml/fraud proving run — a refusal, not a metric.

Plan: `.claude/docs/plans/2026-08-11-gal-4-phase2-ml-fraud-poc.md`.

This script demonstrates a specific failure and then fixes it, in that order. Run the
existing toolkit against this frame unguarded and it completes with no warning at all,
reporting PR-AUC within 0.003 of the prevalence floor and a cost-minimising threshold with
zero true positives (`docs/before-guard.json` — captured before any guard existed). The
guard added here does not make the toolkit raise on a thin frame. **A refusing run is a
successful run**: when the positive count per fold is insufficient, the run still exits 0
and still produces a report — it just declines to report an operating point, and says so.

WHAT THIS RUN IS
    A test of the toolkit's `run_classification` against a real, thin, imbalanced frame
    (800 rows, 14 positives). The data is a client's fraud sample from `lebanese-blonde`.
    **No number this produces is a statement about the client's actual fraud rate** — the
    frame is 800 rows, not the full population, and the point of this poc is the toolkit's
    behaviour under thinness, not a fraud-detection result.

DATA HANDLING
    `pocs/ml/fraud/data/` is gitignored and never read into anything that gets committed.
    This script prints aggregates only — metrics, counts, column names. It never prints a
    row, a row index, or an identifier value (`uuid` is dropped before it is ever loaded
    into a feature matrix; see `IDENTIFIER_COLUMNS`). The generated HTML report is written
    to `pocs/ml/fraud/docs/report.html`, which is gitignored for the same reason: it embeds
    distributional detail derived from real records.

RUNNING IT
    The toolkit lives in `ai-project-template` (branch `AIT-67-ml-workflows-classification`,
    pinned at commit `0f8b2cf` — see plan F8), and galactus deliberately declares no ML
    dependencies. This script is run against an external interpreter that has `ml`
    importable:

        ML_PACKAGE_ROOT=/path/containing/ml python pocs/ml/fraud/src/run.py

    `ML_PACKAGE_ROOT` is prepended to `sys.path`. Without it the import fails with a
    message saying so, rather than a bare ImportError.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA = REPO_ROOT / "pocs" / "ml" / "fraud" / "data" / "dataset.csv"
DEFAULT_REPORT = REPO_ROOT / "pocs" / "ml" / "fraud" / "docs" / "report.html"

# --- toolkit import ---------------------------------------------------------------
# Done before the `ml.*` imports so the failure is a sentence, not a stack trace.
_ml_root = os.environ.get("ML_PACKAGE_ROOT")
if _ml_root:
    sys.path.insert(0, _ml_root)

try:
    import pandas as pd
    from ml.evaluation.splitting import make_splitter
    from ml.workflows.classification import run_classification
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        f"could not import the ML toolkit ({exc}).\n"
        "The toolkit lives in ai-project-template under\n"
        "  template/_scaffold/{{ py_project_root }}/{{ ml_source_root }}/\n"
        "and galactus declares no ML dependencies by design. Point ML_PACKAGE_ROOT at a\n"
        "directory containing an importable `ml` package, in an environment with\n"
        "pandas, scikit-learn, catboost and lightgbm installed."
    ) from exc

from report import write_fraud_report  # noqa: E402
from sufficiency import MIN_POSITIVES_PER_FOLD, assess_sufficiency  # noqa: E402

logger = logging.getLogger("ml_fraud.run")

SEED = 42
TARGET = "default"

# --- decisions from the plan's research phase --------------------------------------
# Each constant below is a finding recorded in the plan doc, not a runtime inference.

#: Row identifiers. `uuid` is 800/800 distinct, so `infer_column_types` buckets it as
#: high-cardinality and `TabularPreprocessor` TARGET-ENCODES it — a per-row key encoded
#: against 14 positives, i.e. near-perfect memorisation. Same defect class the lending
#: poc routed around (`ml-lending/src/run.py:266-283`, the "TOOLKIT GAP" docstring —
#: this is the second real frame the toolkit has created this hazard on). Dropped before
#: inference.
IDENTIFIER_COLUMNS = ["uuid"]

#: RECORDED, NOT CORRECTED. The reference implementation uses `age` raw (18-74, median 46,
#: 36 missing) as a numeric feature — `lebanese-blonde/src/features.py:28`. Age is a
#: protected characteristic in most credit/fraud jurisdictions. Kept raw here to reproduce
#: the reference, and surfaced in the summary and report so it is a recorded decision
#: rather than a silent one. Precedent: `ml-lending/src/run.py:154` (zip_code, dropped as
#: a protected-characteristic proxy) — this poc records instead of dropping because the
#: brief is to reproduce the reference frame, not to fix it.
AGE_FAIRNESS_NOTE = (
    "`age` is used raw as a numeric feature (18-74, median 46, 36 missing), reproducing "
    "the reference implementation. Age is a protected characteristic; this run records "
    "its use rather than endorsing it. Not derived, not binned, not dropped."
)

# --- cost matrix --------------------------------------------------------------------
# STIPULATED, NOT DISCOVERED. No cost matrix is discoverable for this frame — these
# numbers exist so `choose_threshold` has something to minimise *when the sufficiency
# guard allows a threshold to be chosen at all*. On this frame (14 positives, 2-3 per
# fold) the guard refuses and these costs are never passed to `run_classification` — see
# `main()`. They are retained as constants so the run is reproducible if a future, larger
# extract of the same frame arrives and the guard passes.
COST_FP = 1.0
COST_FN = 10.0


def build_frame(csv_path: Path) -> pd.DataFrame:
    """Load the frame and apply the recorded decisions. Returns a modelling frame.

    Unlike the lending frame, the target has zero missing values and there is no
    survivorship filter to apply — every row is resolved. The only structural change is
    dropping `uuid` before the frame ever reaches `infer_column_types`. Nothing is fitted
    here — every transform that learns from data happens inside the cross-validation
    pipeline, which is what `assert_no_transform_outside_pipeline` exists to enforce.
    """
    if not csv_path.exists():
        raise SystemExit(
            f"no data at {csv_path}.\n"
            "pocs/ml/fraud/data/ is gitignored and holds real records; it is not part of "
            "the repository. See pocs/ml/fraud/README.md for how to obtain a copy."
        )

    df = pd.read_csv(csv_path, sep=";", low_memory=False)
    logger.info("loaded frame: %d rows x %d columns", len(df), df.shape[1])

    to_drop = [c for c in IDENTIFIER_COLUMNS if c in df.columns]
    df = df.drop(columns=to_drop)
    logger.info("dropped %d identifier column(s): %s", len(to_drop), to_drop)
    logger.info(
        "modelling frame: %d rows x %d columns, %d positives (%.4f prevalence)",
        len(df),
        df.shape[1],
        int(df[TARGET].sum()),
        float(df[TARGET].mean()),
    )
    return df


def summarise(result, verdict, *, out: Path) -> dict:
    """Aggregates only — never a row, an index, or an identifier.

    Shaped for a later Phase 1 registry lift (plan F10): a flat `metrics`-shaped model
    list, a `headline_metric` naming which one is load-bearing, and a `refusal` block that
    is the machine-readable form of "no threshold was chosen because the frame was too
    thin" — present whether or not the run refused, so a consumer never has to infer
    absence-of-refusal from a missing key.
    """
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
        "headline_metric": "average_precision",
        "prevalence_floor": verdict.prevalence,
        "refusal": {
            "operating_point_reported": verdict.threshold_reportable,
            "reason": verdict.reason,
            "min_positives_in_fold": verdict.min_positives_in_fold,
            "n_positives": verdict.n_positives,
        },
        "fairness_notes": [AGE_FAIRNESS_NOTE],
    }

    for model in result.models:
        entry = {
            "name": model.name,
            "is_baseline": model.is_baseline,
            "pr_auc": getattr(model.metrics, "average_precision", None),
            "roc_auc": getattr(model.metrics, "roc_auc", None),
            "prevalence": getattr(model.metrics, "prevalence", None),
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
                "true_positives": model.threshold.true_positives,
                "expected_cost": model.threshold.expected_cost,
                "cost_at_default": model.threshold.cost_at_default,
                "savings_vs_default": model.threshold.savings_vs_default,
                "STIPULATED_COSTS": {"cost_fp": COST_FP, "cost_fn": COST_FN},
                "SELECTED_IN_SAMPLE": True,
            }
        else:
            entry["threshold"] = None
        summary["models"].append(entry)

    if baseline is not None and best is not None:
        summary["verdict"] = {
            "baseline": baseline.name,
            "best": best.name,
            "baseline_pr_auc": getattr(baseline.metrics, "average_precision", None),
            "best_pr_auc": getattr(best.metrics, "average_precision", None),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="registry names to run; default is every available binary classifier",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="write the aggregate summary here (metrics only, no row data)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    df = build_frame(args.data)
    split_plan = make_splitter(n_splits=args.n_splits, random_state=SEED)
    y = df[TARGET].to_numpy()

    verdict = assess_sufficiency(y, split_plan, min_per_fold=MIN_POSITIVES_PER_FOLD)
    logger.info(
        "sufficiency: sufficient=%s min_positives_in_fold=%d reason=%s",
        verdict.sufficient,
        verdict.min_positives_in_fold,
        verdict.reason,
    )

    result = run_classification(
        df,
        target=TARGET,
        output="binary",
        models=args.models,
        sampling="class_weight",
        splitter=split_plan,
        calibrate=True,
        # Costs are withheld on an insufficient frame. `run_classification` reports no
        # threshold without them — so the refusal is expressed by not asking the
        # question, rather than by discarding an answer after the fact.
        cost_fp=COST_FP if verdict.threshold_reportable else None,
        cost_fn=COST_FN if verdict.threshold_reportable else None,
        seed=SEED,
    )

    # Structural guarantee, asserted rather than trusted: if any model fitted a
    # transformer outside its pipeline, every CV score above is inflated.
    result.assert_no_transform_outside_pipeline()

    summary = summarise(result, verdict, out=args.report)
    write_fraud_report(result, summary, args.report, title="ml/fraud proving run — lebanese-blonde sample")

    if args.summary_json:
        args.summary_json.write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")

    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
