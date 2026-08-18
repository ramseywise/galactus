"""Credit default — the gate-3 run script.

Written from `ml/workflows/classification.py`; nothing here reimplements the
pipeline. The workflow already fits every transformer inside the fold, scores
each row with a model that did not train on it, calibrates on those out-of-fold
probabilities, and asserts the no-leakage claim. This file supplies the
*decisions* from the gate-1a/gate-2 interview and nothing else.

Gate-1a config (confirmed with the operator):

    family/output   classification / binary — P(default) per account
    calibrate       true — the score feeds a decision, not a ranking, so the
                    probability has to mean what it says
    models          logistic (baseline, always) + random_forest + catboost
    cost posture    FN > FP — approving someone who then defaults is the
                    expensive error

Still open, and deliberately not defaulted:

    label horizon   `default` has no stated window. BLOCKING for the threshold.
    splitter        gate 1b — needs the EDA answer on recurrence/time structure
    cost ratio      a *direction* was given, not a ratio; see COST_FN/COST_FP

Run:  uv run python runs/ml/credit/src/run.py [--models logistic,catboost]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# `pythonpath` in pyproject.toml is pytest-only, so a plain `python run.py` cannot see
# `ml/` at the repo root. Same convention as the other runs here
# (marketing-comms/evals/run.py, ml/lending/src/run.py): prepend the root.
#
# The `remove` is load-bearing, not tidying. Python puts the script's own directory
# on sys.path first, and `runs/ml/` — having no __init__.py — is a *namespace*
# package named `ml`. It therefore satisfies `import ml` while containing none of
# the real modules, so `ml.evaluation` fails with a ModuleNotFoundError that reads
# like a missing dependency rather than a shadowed package.
# parents[4], not [3]: src → credit → ml → runs → <root>. Getting this wrong lands on
# `runs/`, whose `ml/` subdirectory then satisfies `import ml` as a namespace package
# while containing none of the real modules.
_ROOT = Path(__file__).resolve().parents[4]
if not (_ROOT / "ml" / "__init__.py").exists():
    raise RuntimeError(f"expected the vendored ml/ package at {_ROOT}/ml — not found")

_HERE = str(Path(__file__).resolve().parent)
if _HERE in sys.path:
    sys.path.remove(_HERE)
sys.path.insert(0, str(_ROOT))

from ml.evaluation.splitting import make_splitter  # noqa: E402
from ml.workflows.classification import run_classification  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("credit")

DATA = Path(__file__).resolve().parents[1] / "data" / "uci_default_of_credit_card_clients.csv"
SEP = ","
TARGET = "default"

# UCI header is `ID, X1..X23, Y` — renamed at load to match the variables table.
# The real column names from UCI's variables table, used after renaming.
UCI_COLUMN_MAP = {
    "ID": "ID", "X1": "LIMIT_BAL", "X2": "SEX", "X3": "EDUCATION", "X4": "MARRIAGE",
    "X5": "AGE", "X6": "PAY_0", "X7": "PAY_2", "X8": "PAY_3", "X9": "PAY_4",
    "X10": "PAY_5", "X11": "PAY_6", "X12": "BILL_AMT1", "X13": "BILL_AMT2",
    "X14": "BILL_AMT3", "X15": "BILL_AMT4", "X16": "BILL_AMT5", "X17": "BILL_AMT6",
    "X18": "PAY_AMT1", "X19": "PAY_AMT2", "X20": "PAY_AMT3", "X21": "PAY_AMT4",
    "X22": "PAY_AMT5", "X23": "PAY_AMT6", "Y": "default",
}

# Identifier, not a feature. UCI's `ID` is a sequential integer.
ID_COLS = ["ID"]

# Leakage exclusion list — September 2005 payment/billing columns are the leak
# candidates against an October label. Authored fresh for UCI's schema.
LEAKAGE_CANDIDATES = ["BILL_AMT1", "PAY_AMT1", "PAY_0"]

MODELS = ["logistic", "random_forest", "catboost"]

# --- Gate 1b: unresolved, and the run says so ------------------------------
# The operator flagged that a subject may recur — pay off one loan, then take
# another — which would make prior history legitimate signal and demand a
# group-aware or temporal split. Neither a group key nor a date column has been
# confirmed in this frame yet, so the split stays stratified k-fold and the run
# is marked provisional. Set these once the notebook answers gate 1b.
GROUP_COL: str | None = None
TIME_COL: str | None = None

# --- Gate 1a: cost direction is known, the ratio is not --------------------
# "Approving someone who then defaults" is the expensive error → FN costs more
# than FP. A *direction* is not a ratio, and 1:1 would be a strong claim nobody
# made, so both stay None: `run_classification` then reports no threshold at
# all rather than presenting 0.5 as a decision. Fill these in and the pipeline
# chooses a cost-minimising operating point.
COST_FP: float | None = None
COST_FN: float | None = None


def load(path: Path = DATA) -> pd.DataFrame:
    """Read the UCI frame, rename columns, drop ID and unlabelled rows.

    The UCI file uses `X1..X23, Y` as headers — renamed to the real names from
    the variables table so downstream code reads `LIMIT_BAL`, not `X1`.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — it is gitignored (*.csv). Download from:\n"
            "  https://archive.ics.uci.edu/static/public/350/data.csv\n"
            "  and save as runs/ml/credit/data/uci_default_of_credit_card_clients.csv"
        )

    df = pd.read_csv(path, sep=SEP)

    # Rename UCI's cryptic headers to real column names
    rename = {k: v for k, v in UCI_COLUMN_MAP.items() if k in df.columns and k != v}
    if rename:
        df = df.rename(columns=rename)
        logger.info("renamed %d UCI columns to real names", len(rename))

    # Drop duplicates (35 known in UCI frame)
    n_before = len(df)
    df = df.drop_duplicates(subset=[c for c in df.columns if c not in ID_COLS])
    n_dupes = n_before - len(df)
    if n_dupes:
        logger.info("dropped %d duplicate row(s)", n_dupes)

    labelled = df[~df[TARGET].isna()].copy()
    dropped = len(df) - len(labelled)
    if dropped:
        logger.info("dropped %d unlabelled row(s) of %d", dropped, len(df))

    return labelled.drop(columns=[c for c in ID_COLS if c in labelled.columns])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        default=",".join(MODELS),
        help=f"comma-separated candidate list (default: {','.join(MODELS)})",
    )
    parser.add_argument("--n-splits", type=int, default=5)
    args = parser.parse_args()

    df = load()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    positives = int(df[TARGET].sum())
    per_fold = positives / args.n_splits
    logger.info("frame: %d rows x %d cols", *df.shape)
    logger.info("positives: %d (%.2f%%)", positives, 100 * df[TARGET].mean())
    logger.info("~%.1f positives per fold at n_splits=%d", per_fold, args.n_splits)

    if per_fold < 10:
        logger.warning(
            "FEW POSITIVES PER FOLD (~%.1f). Cross-validated metrics carry "
            "fold-to-fold variance far larger than any model difference you are "
            "likely to see here. Read the spread, not the mean.",
            per_fold,
        )

    split_plan = make_splitter(
        n_splits=args.n_splits,
        group_col=GROUP_COL,
        time_col=TIME_COL,
    )
    logger.info("split: %s — %s", split_plan.kind, split_plan.reason)
    if GROUP_COL is None and TIME_COL is None:
        logger.warning(
            "PROVISIONAL SPLIT: gate 1b (recurrence / time structure) is unresolved, "
            "so this is a plain stratified k-fold. If subjects recur, this split puts "
            "the same subject on both sides and every score below is optimistic."
        )

    result = run_classification(
        df,
        target=TARGET,
        output="binary",
        models=models,
        splitter=split_plan,
        calibrate=True,
        cost_fp=COST_FP,
        cost_fn=COST_FN,
    )

    report(result)


def report(result) -> None:
    """Print the comparison, then the three things that decide whether it means
    anything: the margin against fold variance, the positives-per-fold count,
    and the leakage assertion."""
    print(f"\n{'model':<16}{'PR-AUC':>18}{'ROC-AUC':>10}{'Brier':>9}  calibration")
    print("-" * 72)
    for run in result.models:
        metrics = run.metrics
        pr = f"{run.headline:.3f}" if run.headline is not None else "—"
        spread = f" ±{run.headline_std:.3f}" if getattr(run, "headline_std", None) else ""
        roc = f"{metrics.roc_auc:.3f}" if metrics and metrics.roc_auc is not None else "—"
        brier = f"{metrics.brier:.4f}" if metrics and metrics.brier is not None else "—"
        cal = getattr(run, "calibration", None)
        if cal:
            # `improved` is the honest field: calibration is not guaranteed to help,
            # and a report that only ever says "calibrated" teaches nothing.
            arrow = "better" if cal.improved else "WORSE"
            cal_note = f"{cal.method} {cal.brier_delta:+.4f} ({arrow})"
        else:
            cal_note = "none"
        flag = "  [baseline]" if run.is_baseline else ""
        print(f"{run.name:<16}{pr + spread:>18}{roc:>10}{brier:>9}  {cal_note}{flag}")

    for name, why in result.skipped.items():
        print(f"{name:<16}{'skipped':>18}  {why}")

    baseline, best = result.baseline, result.best
    print()
    if baseline and best:
        margin = (best.headline or 0) - (baseline.headline or 0)
        print(f"best: {best.name} (PR-AUC {best.headline:.3f})")
        print(f"margin over baseline: {margin:+.4f}")
        print(
            f"beats baseline by more than noise: {result.beats_baseline}"
            "   (tolerance 0.01 — a smaller margin is a coin flip, not a finding)"
        )
    else:
        print("no baseline or no scored model — nothing to compare")

    print("\n--- caveats this run carries ---")
    print(f"class balance: {result.class_balance}")
    print(f"features used: {result.n_features}")
    if GROUP_COL is None and TIME_COL is None:
        print("split:         PROVISIONAL — gate 1b unresolved (see warning above)")
    if COST_FP is None or COST_FN is None:
        print("threshold:     NOT REPORTED — cost ratio unknown; direction is FN > FP.")
        print("               A 0.5 cutoff is a convention, not a decision.")
    print("label horizon: ONE MONTH (UCI variables table: 'default payment next month')")


if __name__ == "__main__":
    main()
