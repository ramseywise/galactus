"""Cluster tests — three known blobs must be found, and found reproducibly."""

from __future__ import annotations

import numpy as np
import pytest
from cluster import IMPLAUSIBLE_SILHOUETTE, best, evaluate, k2_baseline, random_baseline, sweep


@pytest.fixture
def three_blobs() -> np.ndarray:
    """Three well-separated Gaussian blobs in 4D — ground truth k is 3."""
    rng = np.random.default_rng(42)
    centers = np.array([[0.0, 0, 0, 0], [10, 10, 0, 0], [0, 0, 10, 10]])
    return np.vstack([c + rng.normal(0, 0.5, size=(100, 4)) for c in centers])


@pytest.fixture
def structureless() -> np.ndarray:
    """Uniform noise — no k should look good here."""
    return np.random.default_rng(7).uniform(size=(300, 4))


class TestSweep:
    def test_peaks_at_the_true_k(self, three_blobs):
        results = sweep(three_blobs, k_range=range(2, 7))
        assert best(results).k == 3

    def test_winner_beats_both_baselines(self, three_blobs):
        winner = best(sweep(three_blobs, k_range=range(2, 7)))
        assert winner.silhouette > winner.baseline_random
        assert winner.silhouette > winner.baseline_k2
        assert winner.beats_baselines

    def test_sizes_sum_to_n(self, three_blobs):
        for result in sweep(three_blobs, k_range=range(2, 7)):
            assert sum(result.sizes) == len(three_blobs)
            assert len(result.sizes) == result.k

    def test_reproducible_under_fixed_seed(self, three_blobs):
        first = [r.silhouette for r in sweep(three_blobs, k_range=range(2, 6))]
        second = [r.silhouette for r in sweep(three_blobs, k_range=range(2, 6))]
        assert first == second


class TestBaselines:
    def test_random_partition_scores_near_zero(self, three_blobs):
        """A random split of well-separated blobs has no structure to find."""
        assert random_baseline(three_blobs, 3) < 0.05

    def test_k2_baseline_is_computed_on_real_clustering(self, three_blobs):
        assert 0.0 < k2_baseline(three_blobs) < 1.0

    def test_every_result_carries_its_baselines(self, three_blobs):
        """No code path produces a score without its comparator."""
        result = evaluate(three_blobs, 3)
        assert result.baseline_random is not None
        assert result.baseline_k2 is not None


class TestStructurelessData:
    def test_noise_does_not_beat_baselines_impressively(self, structureless):
        """On uniform noise the winner should be weak — the honest 'no structure' case."""
        winner = best(sweep(structureless, k_range=range(2, 7)))
        assert winner.silhouette < 0.5

    def test_best_falls_back_rather_than_raising(self, structureless):
        """'Nothing beat the baseline' is a finding the report states, not an error."""
        assert best(sweep(structureless, k_range=range(2, 5))) is not None


class TestImplausibilityFlag:
    def test_perfectly_separated_data_is_flagged(self):
        """A silhouette this high on real data means a leak, so the flag must fire."""
        matrix = np.vstack(
            [np.zeros((50, 3)) + 0.001 * np.random.default_rng(1).normal(size=(50, 3)),
             np.full((50, 3), 1000.0)]
        )
        assert evaluate(matrix, 2).implausible

    def test_threshold_is_where_the_plan_says(self):
        assert IMPLAUSIBLE_SILHOUETTE == 0.70
