"""Step 14 decisions as code, plus the frame construction they govern.

Every constant here is a finding in `runs/ml/lending/docs/DESIGN.md`, not a runtime
inference — the two can be diffed. Nothing in this module infers a treatment at runtime:
an inferred default is an undocumented decision, and the point of the profiling step was
to have none.

Toolkit-free by design: pure pandas, importable without `ML_PACKAGE_ROOT`, so the
label/group/drop logic is unit-testable inside galactus's own venv. `prepare_frame` is
the seam fixtures enter through; `load_frame` is the only file-touching path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger("ml_lending.frame")

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
# STIPULATED, NOT DISCOVERED. Unknown #3 in runs/ml/lending/README.md is unanswered, and no public
# dataset can answer it. These numbers exist so `choose_threshold` has something to
# minimise and the code path is exercised end to end.
#
# Every threshold number in the report inherits this assumption. The 4:1 ratio encodes
# "missing a loan that goes bad costs about four times an unnecessary review" — a
# plausible shape for lending, and a guess. DESIGN.md open item 5.
COST_FP = 1.0
COST_FN = 4.0


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the Step 14 decisions to a raw extract frame. Returns a modelling frame.

    Order matters and is the point: the label is constructed, unresolved rows are
    dropped, the group key is derived, and only then are the leakage columns removed.
    Nothing is fitted here — every transform that learns from data happens inside the
    cross-validation pipeline, which is what `assert_no_transform_outside_pipeline`
    exists to enforce.

    Pure pandas over the frame it is given — synthetic fixtures enter here without a
    file. `load_frame` is the CSV-reading wrapper.
    """
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


def load_frame(csv_path: Path) -> pd.DataFrame:
    """Load the extract from disk and hand it to `prepare_frame`."""
    if not csv_path.exists():
        raise SystemExit(
            f"no data at {csv_path}.\n"
            "runs/ml/lending/data/ is gitignored and holds real records; it is not part of the "
            "repository. See runs/ml/lending/docs/DESIGN.md for the source and licence."
        )

    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("loaded extract: %d rows x %d columns", len(df), df.shape[1])
    return prepare_frame(df)
