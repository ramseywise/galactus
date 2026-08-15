"""Guard tests — including the escape hatch a one-directional guard would leave open."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from features import FEATURE_COLUMNS
from prepare import LOG_COLUMNS, check_leakage, prepare_matrix


def _healthy_frame(n: int = 50) -> pd.DataFrame:
    """A frame that is clean on every rule — varied, no NaN, no forbidden name."""
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {col: rng.uniform(1.0, 100.0, size=n) for col in FEATURE_COLUMNS}
    )


def _verdicts(findings) -> dict[str, bool]:
    return {f.rule: f.passed for f in findings}


class TestRuleA:
    def test_cohort_fails_and_is_named(self):
        df = _healthy_frame()
        df["cohort"] = 3
        findings = check_leakage(df)
        rule = next(f for f in findings if f.rule == "a_no_first_trade_derived_column")
        assert not rule.passed
        assert "cohort" in rule.detail

    def test_clean_frame_passes(self):
        assert _verdicts(check_leakage(_healthy_frame()))["a_no_first_trade_derived_column"]


class TestRuleC:
    def test_sum_and_its_parts_fails(self):
        df = _healthy_frame()
        for month in range(1, 13):
            df[f"n_trades_{month}"] = 1.0 * month
        findings = check_leakage(df)
        rule = next(f for f in findings if f.rule == "c_no_sum_and_parts_double_count")
        assert not rule.passed
        assert "n_trades" in rule.detail


class TestRuleD:
    """The escape hatch: clean on (a)-(c), degenerate anyway."""

    def test_constant_column_and_nan_fails_rule_d(self):
        df = _healthy_frame()
        df["n_sectors"] = 1.0  # all-constant: the FA-001 signature
        df.loc[df.index[:20], "virtual_pnl"] = np.nan  # 40% NaN

        findings = check_leakage(df)
        verdicts = _verdicts(findings)

        # The point of the test: the name-based rules see nothing wrong.
        assert verdicts["a_no_first_trade_derived_column"]
        assert verdicts["c_no_sum_and_parts_double_count"]
        # Only rule (d) catches it.
        assert not verdicts["d_matrix_health"]

        detail = next(f for f in findings if f.rule == "d_matrix_health").detail
        assert "n_sectors" in detail
        assert "virtual_pnl" in detail

    def test_row_count_mismatch_fails(self):
        df = _healthy_frame(n=50)
        assert not _verdicts(check_leakage(df, expected_rows=29096))["d_matrix_health"]

    def test_healthy_frame_passes_all_four(self):
        verdicts = _verdicts(check_leakage(_healthy_frame(), expected_rows=50))
        assert all(verdicts.values()), verdicts


class TestCheckLeakageContract:
    def test_always_returns_one_finding_per_rule(self):
        """An empty list is not a pass. Four rules in, four findings out, always."""
        assert len(check_leakage(_healthy_frame())) == 4
        assert len(check_leakage(pd.DataFrame({"n_trades": [1.0, 2.0]}))) == 4


class TestPrepareMatrix:
    def test_shape_and_standardization(self):
        features = _healthy_frame(n=100)
        matrix, cols = prepare_matrix(features)
        assert matrix.shape == (100, len(FEATURE_COLUMNS))
        assert cols == list(FEATURE_COLUMNS)
        assert np.allclose(matrix.mean(axis=0), 0.0, atol=1e-9)
        assert np.allclose(matrix.std(axis=0), 1.0, atol=1e-9)

    def test_log_columns_are_declared_features(self):
        assert set(LOG_COLUMNS) <= set(FEATURE_COLUMNS)

    def test_negative_values_survive_log_scaling(self):
        """`realized_pnl` is legitimately negative; a bare log1p would yield NaN."""
        features = _healthy_frame(n=20)
        features["mean_trade_size"] = -50.0
        matrix, _ = prepare_matrix(features)
        assert not np.isnan(matrix).any()

    @pytest.mark.parametrize("col", LOG_COLUMNS)
    def test_log_scaling_compresses_the_declared_columns(self, col):
        """A whale must not remain a whale after scaling."""
        features = _healthy_frame(n=100)
        features.loc[features.index[0], col] = 1e9
        matrix, cols = prepare_matrix(features)
        position = cols.index(col)
        assert abs(matrix[0, position]) < 20.0
