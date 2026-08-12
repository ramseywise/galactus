"""Synthetic fixtures for the sufficiency guard's tests.

No real row enters a test file — every fixture here is a seeded generator, in the spirit
of `lebanese-blonde/src/synthetic.py`. The guard is tested against shapes, not against the
actual fraud sample; `pocs/ml/fraud/src/run.py` is what exercises it against the real
frame, and that is an integration concern, not a unit-test one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class _FixedFolds:
    """A minimal splitter that replays a fixed list of (train_idx, test_idx) pairs.

    Standing in for a real `SplitPlan` so these tests exercise `assess_sufficiency`'s fold
    arithmetic without depending on the external ML toolkit being importable — the guard
    module itself has no toolkit dependency, and its tests should not acquire one.
    """

    def __init__(self, folds: list[tuple[np.ndarray, np.ndarray]]) -> None:
        self.folds = folds

    def split(self, x=None, y=None, groups=None):
        return iter(self.folds)


def _folds_from_test_sizes(n_rows: int, test_slices: list[slice]) -> _FixedFolds:
    all_idx = np.arange(n_rows)
    folds = []
    for sl in test_slices:
        test_idx = all_idx[sl]
        train_idx = np.setdiff1d(all_idx, test_idx)
        folds.append((train_idx, test_idx))
    return _FixedFolds(folds)


@pytest.fixture
def thin_frame():
    """5 folds, 2 positives per test fold (mirrors the real frame's measured shape).

    Positions are placed deterministically rather than via a random shuffle: a shuffle
    can land an odd number of positives in one 160-row slice by chance, which would make
    this fixture non-reproducible across seeds. Two positives per 160-row fold, placed at
    fixed offsets, is exact.
    """
    y = np.zeros(800, dtype=int)
    for i in range(5):
        start = i * 160
        y[start] = 1
        y[start + 1] = 1
    # 5 equal test slices of 160 rows each.
    plan = _folds_from_test_sizes(800, [slice(i * 160, (i + 1) * 160) for i in range(5)])
    return y, plan


@pytest.fixture
def healthy_frame():
    """5 folds, comfortably above the floor in every fold."""
    rng = np.random.default_rng(2)
    y = np.zeros(1000, dtype=int)
    y[:200] = 1
    rng.shuffle(y)
    plan = _folds_from_test_sizes(1000, [slice(i * 200, (i + 1) * 200) for i in range(5)])
    return y, plan


@pytest.fixture
def boundary_frame():
    """Every fold has exactly MIN_POSITIVES_PER_FOLD positives — the inclusive edge."""
    from sufficiency import MIN_POSITIVES_PER_FOLD

    n_folds = 5
    per_fold = MIN_POSITIVES_PER_FOLD
    fold_size = 100
    y = np.zeros(n_folds * fold_size, dtype=int)
    for i in range(n_folds):
        start = i * fold_size
        y[start : start + per_fold] = 1
    plan = _folds_from_test_sizes(
        n_folds * fold_size, [slice(i * fold_size, (i + 1) * fold_size) for i in range(n_folds)]
    )
    return y, plan


@pytest.fixture
def healthy_and_one_thin_frame():
    """Four folds at 40 positives, one fold at 2. Averages to 32.8 — comfortably above
    any reasonable line, and completely wrong. Catches an averaging bug."""
    fold_size = 200
    healthy_pos = 40
    thin_pos = 2
    n_folds = 5
    y = np.zeros(n_folds * fold_size, dtype=int)
    for i in range(n_folds):
        start = i * fold_size
        pos = thin_pos if i == 4 else healthy_pos
        y[start : start + pos] = 1
    plan = _folds_from_test_sizes(
        n_folds * fold_size, [slice(i * fold_size, (i + 1) * fold_size) for i in range(n_folds)]
    )
    return y, plan


@pytest.fixture
def zero_positive_frame():
    """No positives at all — the guard must not divide by zero or raise."""
    y = np.zeros(500, dtype=int)
    plan = _folds_from_test_sizes(500, [slice(i * 100, (i + 1) * 100) for i in range(5)])
    return y, plan
