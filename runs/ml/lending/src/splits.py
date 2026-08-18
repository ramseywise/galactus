"""Grouped split plan — computed here, verified here, and passed in pre-computed.

Toolkit-coupled: imports `ml.evaluation.splitting`, so this module is importable only
when `ML_PACKAGE_ROOT` (or the test environment) makes the `ml` package resolvable.
`run.py` inserts that path and runs its import guard before importing this module;
tests that need it skip with a reason naming the env var when it is unset.
"""

from __future__ import annotations

import logging

import pandas as pd

from frame import GROUP_COL, SEED, TARGET
from ml.evaluation.splitting import SplitPlan, assert_no_group_leakage, make_splitter

logger = logging.getLogger("ml_lending.splits")


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
    This call is guard (c) of the MVP guard set — it lives here, not in `guards.py`,
    because it must run against the folds at the moment they are computed.
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
