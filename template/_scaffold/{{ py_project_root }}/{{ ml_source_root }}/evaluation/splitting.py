"""Leakage-safe splitting — choosing a cross-validation strategy from the shape
of the data rather than from habit.

`StratifiedKFold` is the right default for i.i.d. rows and the wrong answer for
almost every real tabular dataset, because real rows are rarely independent:

- **Grouped rows.** One debtor holds three accounts. A random split puts two in
  train and one in validation, so the model is scored on an entity it has
  already seen. The score measures memorisation of the entity, not prediction
  for a new one.
- **Time-structured rows.** A random split trains on March and scores February.
  The model gets to see the future, which is the one thing it will never have in
  production. Nothing about the resulting number transfers.

Both failures are silent: the folds are valid, the fit succeeds, and the metric
comes back higher than an honest one. That is exactly why `make_splitter`
**refuses** rather than warns when it is asked for a random split over a
declared time column — a warning on a number that looks good is a warning nobody
reads.

The refusal is the point of this module. `make_splitter(time_col=...,
stratify=True)` raises `TemporalLeakageError` instead of quietly returning
`StratifiedKFold`, because a caller who declared a time column has told us the
rows are ordered, and honouring `stratify` would mean ignoring that.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import (
    GroupKFold,
    StratifiedGroupKFold,
    StratifiedKFold,
    TimeSeriesSplit,
)

RANDOM_STATE = 42

DEFAULT_N_SPLITS = 5


class TemporalLeakageError(ValueError):
    """Raised when a requested split would train on rows that follow the rows it
    scores.

    A `ValueError` subclass because the caller's *arguments* are contradictory —
    declaring a time column and requesting a shuffled/stratified split are two
    incompatible statements about the same data.
    """


class GroupLeakageError(ValueError):
    """Raised when a split would place one group on both sides of the boundary."""


@dataclass(frozen=True)
class SplitPlan:
    """The splitter chosen, plus why — so a run's report can state its own
    validation strategy instead of leaving the reader to infer it."""

    splitter: Any
    kind: str
    reason: str
    n_splits: int
    group_col: str | None = None
    time_col: str | None = None

    def split(self, x, y=None, groups=None, *, frame: pd.DataFrame | None = None):
        """Delegate to the underlying splitter, resolving the declared group and
        time columns from `frame` rather than from `x`.

        `x` is the *feature* matrix, and the group column must not be in it: a
        group column is entity identity, so encoding it as a feature is target
        leakage (see `infer_column_types(exclude=...)`). But the splitter still
        needs those values, so they are read from `frame` — the full source frame
        — which is why this is a separate argument instead of an index into `x`.

        Passing `groups` explicitly overrides the lookup. Falling back to `x` when
        no frame is given keeps callers who really do have the column in their
        feature matrix working, but that fallback is the leaky arrangement, not
        the intended one.
        """
        source = frame if frame is not None else x

        if groups is None and self.group_col is not None:
            if isinstance(source, pd.DataFrame) and self.group_col in source.columns:
                groups = source[self.group_col]
            else:
                raise KeyError(
                    f"the split plan declares group_col={self.group_col!r} but it was not "
                    "found. Pass the full source frame as `frame=` so the splitter can "
                    "read the group column without it having to be a feature, or pass "
                    "`groups=` directly."
                )

        if self.time_col is not None and isinstance(source, pd.DataFrame):
            # SortedTimeSeriesSplit reads the time column off the frame it is
            # handed, so hand it the source frame — the fold indices it yields are
            # positional and stay valid against `x`, which shares the row order.
            return self.splitter.split(source, y, groups)

        return self.splitter.split(x, y, groups)

    def get_n_splits(self, x=None, y=None, groups=None) -> int:
        return self.splitter.get_n_splits(x, y, groups)


class SortedTimeSeriesSplit:
    """`TimeSeriesSplit` over rows ordered by a time column.

    sklearn's `TimeSeriesSplit` splits by *position*, which is only a temporal
    split when the frame is already sorted by time. Frames arrive unsorted often
    enough — a merge or a groupby reorders them — that relying on the caller to
    have sorted is relying on a convention with no enforcement. This wrapper
    sorts by the declared column first and maps the fold indices back to the
    caller's original row positions, so the yielded indices are valid against
    the frame as passed.
    """

    def __init__(self, time_col: str, n_splits: int = DEFAULT_N_SPLITS, gap: int = 0):
        self.time_col = time_col
        self.n_splits = n_splits
        self.gap = gap
        self._inner = TimeSeriesSplit(n_splits=n_splits, gap=gap)

    def split(self, x, y=None, groups=None) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        times = _extract_time(x, self.time_col)
        # Stable sort: rows sharing a timestamp keep their original relative
        # order, so the split is reproducible rather than dependent on the
        # sort algorithm's tie-breaking.
        order = np.argsort(times, kind="stable")
        for train_pos, test_pos in self._inner.split(order):
            yield order[train_pos], order[test_pos]

    def get_n_splits(self, x=None, y=None, groups=None) -> int:
        return self.n_splits

    def __repr__(self) -> str:
        return (
            f"SortedTimeSeriesSplit(time_col={self.time_col!r}, "
            f"n_splits={self.n_splits}, gap={self.gap})"
        )


def _extract_time(x, time_col: str) -> np.ndarray:
    """Pull the time column out of a frame and return it as sortable values."""
    if not isinstance(x, pd.DataFrame):
        raise TypeError(
            f"a time-based split needs a DataFrame to read {time_col!r} from; "
            f"got {type(x).__name__}. Pass the frame itself, not a numpy array."
        )
    if time_col not in x.columns:
        raise KeyError(f"time column {time_col!r} is not in the frame: {list(x.columns)}")

    series = x[time_col]
    if pd.api.types.is_numeric_dtype(series):
        values = series.to_numpy()
    else:
        values = pd.to_datetime(series, errors="coerce").to_numpy()
        if pd.isna(values).any():
            raise ValueError(
                f"time column {time_col!r} has values that do not parse as datetimes. "
                "An unparseable timestamp sorts unpredictably, which would silently "
                "produce a non-temporal split."
            )
    return values


def make_splitter(
    *,
    n_splits: int = DEFAULT_N_SPLITS,
    group_col: str | None = None,
    time_col: str | None = None,
    stratify: bool = True,
    gap: int = 0,
    random_state: int = RANDOM_STATE,
) -> SplitPlan:
    """Choose a cross-validation splitter from the declared structure of the data.

    The decision table, in precedence order:

    | declared            | splitter                  |
    |---------------------|---------------------------|
    | `time_col`          | `SortedTimeSeriesSplit`   |
    | `group_col` + strat | `StratifiedGroupKFold`    |
    | `group_col`         | `GroupKFold`              |
    | stratify            | `StratifiedKFold`         |
    | neither             | `StratifiedKFold` (no-op stratify is still safe) |

    Time wins over grouping because temporal leakage is the harder of the two to
    detect after the fact: a grouped leak inflates the score, while a temporal
    leak can invert the sign of a feature's usefulness entirely.

    Raises `TemporalLeakageError` when `time_col` is declared alongside
    `stratify=True` **and** no group column — stratifying reorders rows by class,
    which is precisely what destroys the temporal ordering the caller declared.
    Pass `stratify=False` to confirm the temporal split is what you want.
    """
    if n_splits < 2:
        raise ValueError(f"n_splits must be at least 2, got {n_splits}")

    if time_col is not None:
        if stratify:
            raise TemporalLeakageError(
                f"a time column ({time_col!r}) was declared and stratify=True was "
                "requested. A stratified split shuffles rows by class, which places "
                "later rows in train relative to test — the model trains on the "
                "future and the resulting score does not transfer to production. "
                "Pass stratify=False for a temporal split, or drop time_col if the "
                "rows really are exchangeable."
            )
        if group_col is not None:
            # Both declared: the honest answer is that this needs a grouped
            # temporal split, which sklearn does not ship. Say so rather than
            # silently honouring one and dropping the other.
            raise TemporalLeakageError(
                f"both time_col={time_col!r} and group_col={group_col!r} were "
                "declared. sklearn has no grouped temporal splitter; honouring one "
                "would silently drop the other's guarantee. Split by time and check "
                "group overlap explicitly with `assert_no_group_leakage`, or "
                "aggregate to one row per group first."
            )
        return SplitPlan(
            splitter=SortedTimeSeriesSplit(time_col=time_col, n_splits=n_splits, gap=gap),
            kind="time_series",
            reason=(
                f"time column {time_col!r} declared — expanding-window split over "
                "time-sorted rows; every training fold precedes its test fold."
            ),
            n_splits=n_splits,
            time_col=time_col,
        )

    if group_col is not None:
        if stratify:
            return SplitPlan(
                splitter=StratifiedGroupKFold(
                    n_splits=n_splits, shuffle=True, random_state=random_state
                ),
                kind="stratified_group",
                reason=(
                    f"group column {group_col!r} declared with stratification — "
                    "no group spans the boundary, and class balance is preserved "
                    "per fold as far as the grouping allows."
                ),
                n_splits=n_splits,
                group_col=group_col,
            )
        return SplitPlan(
            splitter=GroupKFold(n_splits=n_splits),
            kind="group",
            reason=(
                f"group column {group_col!r} declared — no group appears on both "
                "sides of a fold boundary."
            ),
            n_splits=n_splits,
            group_col=group_col,
        )

    return SplitPlan(
        splitter=StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state),
        kind="stratified",
        reason=(
            "no group or time structure declared — rows treated as exchangeable, "
            "class balance preserved per fold."
        ),
        n_splits=n_splits,
    )


def split_columns(
    plan: SplitPlan | None,
    group_col: str | None = None,
    time_col: str | None = None,
) -> tuple[str, ...]:
    """The columns a split needs but a model must not see.

    Both sources count: the caller's `group_col`/`time_col` arguments, and the
    declarations on a pre-built `SplitPlan` passed as `splitter=`. A caller who
    hands over a ready-made plan has still told us those columns are structure
    rather than signal, and forgetting the second source is exactly how the
    column creeps back into the feature matrix.
    """
    declared = [group_col, time_col]
    if plan is not None:
        declared += [plan.group_col, plan.time_col]
    return tuple(dict.fromkeys(col for col in declared if col is not None))


def assert_no_group_leakage(
    train_idx: Sequence[int], test_idx: Sequence[int], groups: Sequence[Any]
) -> None:
    """Raise `GroupLeakageError` if any group appears on both sides of a split.

    Exposed as a public check, not just an internal one: a caller who builds a
    split by hand — or who had to split by time while a group column also
    existed — needs a way to verify the property that `GroupKFold` would have
    given them for free.
    """
    group_values = np.asarray(groups)
    overlap = set(group_values[np.asarray(train_idx, dtype=int)]) & set(
        group_values[np.asarray(test_idx, dtype=int)]
    )
    if overlap:
        sample = sorted(map(str, overlap))[:5]
        raise GroupLeakageError(
            f"{len(overlap)} group(s) appear in both train and test, e.g. {sample}. "
            "The model is being scored on entities it trained on, so the metric "
            "measures memorisation rather than generalisation."
        )


def assert_temporal_order(
    train_idx: Sequence[int], test_idx: Sequence[int], times: Sequence[Any]
) -> None:
    """Raise `TemporalLeakageError` if any training row is not strictly earlier
    than every test row."""
    time_values = np.asarray(times)
    train_times = time_values[np.asarray(train_idx, dtype=int)]
    test_times = time_values[np.asarray(test_idx, dtype=int)]
    if len(train_times) == 0 or len(test_times) == 0:
        return
    latest_train = train_times.max()
    earliest_test = test_times.min()
    if latest_train >= earliest_test:
        raise TemporalLeakageError(
            f"the latest training row ({latest_train}) is not earlier than the "
            f"earliest test row ({earliest_test}). The model is training on rows "
            "that follow what it is scored against."
        )
