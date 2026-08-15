"""pocs/ml/lending proving run — logistic baseline → registry candidates → calibration → threshold.

Plan: `.claude/docs/plans/2026-08-10-ml-capability-parity.md` Phase D, Step 15.
Profile and leakage evidence: `pocs/ml/lending/docs/DESIGN.md`.

This script is the *harness*, not the modelling. Every decision it makes was taken in
Step 14 and is recorded in DESIGN.md; the constants below are that document expressed as
code, so the two can be diffed. Nothing here infers a treatment at runtime — an inferred
default is an undocumented decision, and the point of the profiling step was to have none.

WHAT THIS RUN IS
    A test of the Phase A–C toolkit against a real frame with organic leakage. The data
    is a public US peer-lending extract standing in for collections data that has not
    arrived. **No number this produces is a statement about the client.** See the
    "What this document is, and what it is not" section of DESIGN.md.

DATA HANDLING
    `pocs/ml/lending/data/` is gitignored and never read into anything that gets committed. This
    script prints aggregates only — metrics, counts, column names. It never prints a row,
    a row index, or an identifier value. The generated HTML report is written to
    `pocs/ml/lending/docs/report.html`, which is gitignored for the same reason: it embeds
    distributional detail derived from real records.

RUNNING IT
    The toolkit lives in `ai-project-template` (Phases A/B target that repo), and galactus
    deliberately declares no ML dependencies — it is not a distributable package. So this
    script is run against an external interpreter that has `ml` importable:

        ML_PACKAGE_ROOT=/path/containing/ml python pocs/ml/lending/src/run.py

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

POC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = POC_ROOT / "data" / "lending_club_2015Q4.csv"
DEFAULT_REPORT = POC_ROOT / "docs" / "report.html"

# --- toolkit import ---------------------------------------------------------------
# Done before the `ml.*` imports so the failure is a sentence, not a stack trace.
_ml_root = os.environ.get("ML_PACKAGE_ROOT")
if _ml_root:
    sys.path.insert(0, _ml_root)

try:
    import pandas as pd
    from ml.evaluation.splitting import SplitPlan, assert_no_group_leakage, make_splitter
    from ml.reporting.html import write_report
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


logger = logging.getLogger("ml_lending.run")

SEED = 42
TARGET = "charged_off"
GROUP_COL = "group_key"

# --- decisions from Step 14 -------------------------------------------------------
# Each constant below is a finding in DESIGN.md, not a runtime inference.

#: `loan_status` values that resolve to a positive label (the loan went bad).
POSITIVE_STATUSES = {"Charged Off", "Default"}
#: `loan_status` values that resolve to a negative label.
NEGATIVE_STATUSES = {"Fully Paid"}
# Everything else ("Current", "Late …", "In Grace Period") is *unresolved* — the outcome
# has not happened yet. Those rows are dropped. DESIGN.md records this as a survivorship
# filter rather than a neutral cleaning step, because that is what it is.

#: Post-outcome columns. Available at scoring time in the extract, absent at decision
#: time in production. Including any of them takes ROC-AUC to 0.9993 — see the A/B in
#: DESIGN.md. This list is the single reason the run is honest.
LEAKAGE_COLUMNS = [
    # payment history — accrues after origination
    "recoveries",
    "collection_recovery_fee",
    "total_rec_prncp",
    "total_rec_int",
    "total_rec_late_fee",
    "total_pymnt",
    "total_pymnt_inv",
    "out_prncp",
    "out_prncp_inv",
    "last_pymnt_d",
    "last_pymnt_amnt",
    "next_pymnt_d",
    # credit state at the *most recent* pull, which for a bad loan is after the default
    # already damaged the score. AUC 0.9511 with no post-outcome name pattern — the leak
    # a name-based rule does not catch. See DESIGN.md.
    "last_credit_pull_d",
    "last_fico_range_high",
    "last_fico_range_low",
    # settlement — by definition only populated for borrowers who charged off
    "debt_settlement_flag",
    "debt_settlement_flag_date",
    "settlement_status",
    "settlement_date",
    "settlement_amount",
    "settlement_percentage",
    "settlement_term",
    # hardship — post-outcome; all 13 columns share an identical 99.39% missing rate,
    # which is one fact about the population, not thirteen about the columns
    "hardship_flag",
    "hardship_type",
    "hardship_reason",
    "hardship_status",
    "hardship_amount",
    "hardship_start_date",
    "hardship_end_date",
    "hardship_length",
    "hardship_dpd",
    "hardship_loan_status",
    "hardship_payoff_balance_amount",
    "hardship_last_payment_amount",
    "orig_projected_additional_accrued_interest",
    "deferral_term",
    "payment_plan_start_date",
    "pymnt_plan",
    # origination-time, but tracks investor fill and so correlates with loan quality in a
    # way unavailable for a genuinely new application. Excluded as the conservative call;
    # DESIGN.md open item 6 says to measure the delta rather than argue about it.
    "funded_amnt_inv",
]

#: Row identifiers. High-cardinality integers that a numeric scaler would happily consume.
IDENTIFIER_COLUMNS = ["id", "member_id", "url"]

#: Free text. Out of scope this phase (no text features), so dropped rather than
#: silently one-hot-encoded into thousands of columns.
FREE_TEXT_COLUMNS = ["desc", "title"]

#: Source of the constructed label. Must not survive into the feature matrix.
LABEL_SOURCE_COLUMNS = ["loan_status"]

#: Consumed to build `group_key`, then dropped: `emp_title` is 44.1% distinct and
#: `zip_code` is a protected-characteristic proxy (DESIGN.md open item 4).
GROUP_SOURCE_COLUMNS = ["emp_title", "zip_code"]

# --- cost matrix ------------------------------------------------------------------
# STIPULATED, NOT DISCOVERED. Unknown #3 in pocs/ml/lending/README.md is unanswered, and no public
# dataset can answer it. These numbers exist so `choose_threshold` has something to
# minimise and the code path is exercised end to end.
#
# Every threshold number in the report inherits this assumption. The 4:1 ratio encodes
# "missing a loan that goes bad costs about four times an unnecessary review" — a
# plausible shape for lending, and a guess. DESIGN.md open item 5.
COST_FP = 1.0
COST_FN = 4.0


def build_frame(csv_path: Path) -> pd.DataFrame:
    """Load the extract and apply the Step 14 decisions. Returns a modelling frame.

    Order matters and is the point: the label is constructed, unresolved rows are
    dropped, the group key is derived, and only then are the leakage columns removed.
    Nothing is fitted here — every transform that learns from data happens inside the
    cross-validation pipeline, which is what `assert_no_transform_outside_pipeline`
    exists to enforce.
    """
    if not csv_path.exists():
        raise SystemExit(
            f"no data at {csv_path}.\n"
            "pocs/ml/lending/data/ is gitignored and holds real records; it is not part of the "
            "repository. See pocs/ml/lending/docs/DESIGN.md for the source and licence."
        )

    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("loaded extract: %d rows x %d columns", len(df), df.shape[1])

    # --- label ---------------------------------------------------------------
    status = df["loan_status"]
    resolved = status.isin(POSITIVE_STATUSES | NEGATIVE_STATUSES)
    n_unresolved = int((~resolved).sum())
    df = df[resolved].copy()
    df[TARGET] = status[resolved].isin(POSITIVE_STATUSES).astype(int)
    logger.info(
        "resolved %d rows, dropped %d unresolved (outcome has not happened yet)",
        len(df),
        n_unresolved,
    )

    # --- group key -----------------------------------------------------------
    # `member_id` is 100% null in every public LC file, so borrower identity has to be
    # approximated. This key is weak — 1.03% of rows land in a multi-row group, max group
    # size 3 — and DESIGN.md open item 2 records that group leakage is therefore not
    # really stressed by this run. It is built anyway so the grouped split executes.
    df[GROUP_COL] = (
        df["emp_title"].fillna("<NA>").str.strip().str.lower()
        + "|"
        + df["zip_code"].fillna("<NA>").astype(str)
        + "|"
        + df["annual_inc"].fillna(-1).astype(str)
    )

    # --- drops ---------------------------------------------------------------
    to_drop = [
        c
        for c in (
            LEAKAGE_COLUMNS
            + IDENTIFIER_COLUMNS
            + FREE_TEXT_COLUMNS
            + LABEL_SOURCE_COLUMNS
            + GROUP_SOURCE_COLUMNS
        )
        if c in df.columns
    ]
    df = df.drop(columns=to_drop)

    n_leak = len([c for c in LEAKAGE_COLUMNS if c in to_drop])
    logger.info("dropped %d columns (%d of them post-outcome)", len(to_drop), n_leak)
    logger.info("modelling frame: %d rows x %d columns", len(df), df.shape[1])
    return df


class _PrecomputedFolds:
    """A splitter that replays folds computed elsewhere.

    Exists only to carry grouped folds into `run_classification` without the group
    column having to live in the feature matrix. See `build_split_plan`.
    """

    def __init__(self, folds: list[tuple], n_rows: int) -> None:
        self.folds = folds
        self.n_rows = n_rows

    def split(self, x=None, y=None, groups=None):
        # LK-002. These folds are positional indices into the frame as it stood when
        # `assert_no_group_leakage` checked them. Replaying them against a frame that has
        # since been reordered or filtered would index the wrong rows, and the group
        # check has already run and cannot catch it. A row count is a weak proof of
        # identity but it catches the realistic accident, and failing loudly here beats
        # a silently-degraded split — which is the failure this whole script exists to
        # detect.
        if x is not None and len(x) != self.n_rows:
            raise ValueError(
                f"folds were computed against {self.n_rows} rows but the frame being "
                f"split has {len(x)}. The precomputed indices no longer identify the "
                "rows they were verified against; recompute the split plan."
            )
        return iter(self.folds)

    def get_n_splits(self, x=None, y=None, groups=None) -> int:
        return len(self.folds)


def build_split_plan(df: pd.DataFrame, n_splits: int) -> SplitPlan:
    """Grouped folds, computed here, verified here, and passed in pre-computed.

    TOOLKIT GAP — the reason this is not just `group_col=GROUP_COL`.

    `SplitPlan.split` resolves its groups with `x[self.group_col]`, and `x` inside
    `run_classification` is the *feature* frame (`df[plan.features]`). So the group
    column has to be a feature for the split to work — but `infer_column_types` then
    buckets it by cardinality like any other column. At 39,561 distinct values over
    39,770 rows it lands in `high_cardinality` and is **target-encoded**: the borrower's
    near-unique identity, encoded against the label. That is a leak the toolkit creates
    while honouring its own grouping contract, and it would inflate every score below.

    Passing a `SplitPlan` whose splitter ignores `x` breaks the coupling: the folds are
    computed here against groups held outside the frame, `GROUP_COL` is dropped before
    fitting, and the model never sees it. Reported as a finding against Phase A/B rather
    than patched in the toolkit from here — see the run notes.

    The folds are checked with `assert_no_group_leakage` before being handed over. That
    is the toolkit's own assertion, used as intended: a silently-degraded grouped split
    is invisible in the metrics, which is precisely the failure this run exists to catch.
    """
    base = make_splitter(n_splits=n_splits, group_col=GROUP_COL, stratify=True, random_state=SEED)
    groups = df[GROUP_COL].to_numpy()
    y = df[TARGET].to_numpy()
    features = df.drop(columns=[GROUP_COL, TARGET])

    folds = []
    for train_idx, test_idx in base.splitter.split(features, y, groups=groups):
        assert_no_group_leakage(train_idx, test_idx, groups)
        folds.append((train_idx, test_idx))

    logger.info("group split verified across %d folds (%s)", len(folds), base.kind)
    return SplitPlan(
        splitter=_PrecomputedFolds(folds, n_rows=len(df)),
        kind=base.kind,
        reason=(
            f"{base.reason} Folds pre-computed against {GROUP_COL!r}, which is held "
            "outside the feature matrix so it cannot be encoded as a feature."
        ),
        n_splits=len(folds),
        group_col=None,  # deliberately not set: nothing may look this up on `x`
    )


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
    split_plan = build_split_plan(df, args.n_splits)

    result = run_classification(
        # GROUP_COL is dropped here: the folds already encode the grouping, and leaving
        # the column in would let it be target-encoded as a feature. See build_split_plan.
        df.drop(columns=[GROUP_COL]),
        target=TARGET,
        output="binary",
        models=args.models,
        # 20.56% minority sits just above the toolkit's 20% strong-imbalance line, so the
        # cheapest correct option applies: reweight, do not synthesise. DESIGN.md notes
        # it is close enough to the boundary to re-check on real data.
        sampling="class_weight",
        # Grouping arrives via `splitter`, not `group_col` — passing both is the coupling
        # build_split_plan exists to avoid. `time_col` is moot for the same reason: the
        # extract spans two months (Nov–Dec 2015). DESIGN.md open item 1.
        splitter=split_plan,
        calibrate=True,
        cost_fp=COST_FP,
        cost_fn=COST_FN,
        seed=SEED,
    )

    # Structural guarantee, asserted rather than trusted: if any model fitted a
    # transformer outside its pipeline, every CV score above is inflated.
    result.assert_no_transform_outside_pipeline()

    out = write_report(result, args.report, title="lending proving run — Lending Club proxy")
    summary = summarise(result, out=out)

    if args.summary_json:
        args.summary_json.write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")

    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
