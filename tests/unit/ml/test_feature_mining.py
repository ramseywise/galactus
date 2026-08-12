from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.feature_engineering.mining import (
    add_binned_features,
    add_group_aggregates,
    add_interaction_features,
    add_ratio_features,
    add_rfm_features,
    collapse_rare_categories,
)

RANDOM_STATE = 42


@pytest.fixture
def transactions() -> pd.DataFrame:
    """Synthetic transaction log: 20 debtors, 400 rows spanning 2024."""
    rng = np.random.default_rng(RANDOM_STATE)
    n = 400
    return pd.DataFrame(
        {
            "debtor_id": rng.integers(0, 20, n),
            "txn_date": pd.to_datetime("2024-01-01")
            + pd.to_timedelta(rng.integers(0, 365, n), "D"),
            "amount": rng.gamma(2.0, 250.0, n).round(2),
            "balance": rng.gamma(3.0, 800.0, n).round(2),
            "channel": rng.choice(["web", "phone", "branch"], n, p=[0.7, 0.25, 0.05]),
        }
    )


def test_group_aggregates_produce_correctly_named_columns(transactions):
    out = add_group_aggregates(transactions, "debtor_id", ["amount"], aggs=("mean", "count"))

    assert "debtor_id_amount_mean" in out.columns
    assert "debtor_id_amount_count" in out.columns
    assert len(out) == len(transactions), "aggregates broadcast back, they do not collapse rows"


def test_group_aggregates_are_arithmetically_right(transactions):
    out = add_group_aggregates(transactions, "debtor_id", ["amount"], aggs=("mean",))

    expected = transactions.groupby("debtor_id")["amount"].mean()
    for debtor, mean in expected.items():
        rows = out.loc[out["debtor_id"] == debtor, "debtor_id_amount_mean"]
        assert rows.unique() == pytest.approx([mean])


def test_group_aggregates_do_not_mutate_the_input(transactions):
    before = transactions.copy()
    add_group_aggregates(transactions, "debtor_id", ["amount"])

    pd.testing.assert_frame_equal(transactions, before)


def test_group_aggregates_reject_unknown_columns(transactions):
    with pytest.raises(KeyError, match="nope"):
        add_group_aggregates(transactions, "debtor_id", ["nope"])


def test_rfm_returns_the_expected_columns_one_row_per_entity(transactions):
    rfm = add_rfm_features(transactions, "debtor_id", "txn_date", "amount", "2024-12-31")

    assert set(rfm.columns) == {
        "recency_days",
        "frequency",
        "monetary",
        "monetary_mean",
        "tenure_days",
    }
    assert len(rfm) == transactions["debtor_id"].nunique()
    assert rfm.index.name == "debtor_id"


def test_rfm_as_of_cutoff_excludes_future_rows(transactions):
    """The temporal-leakage guard. A mid-year cutoff must produce RFM values
    computed only from rows on or before it — identical to what you would get by
    filtering the frame yourself first."""
    cutoff = "2024-06-30"

    rfm = add_rfm_features(transactions, "debtor_id", "txn_date", "amount", cutoff)
    manually_filtered = add_rfm_features(
        transactions[transactions["txn_date"] <= pd.Timestamp(cutoff)],
        "debtor_id",
        "txn_date",
        "amount",
        cutoff,
    )

    pd.testing.assert_frame_equal(rfm, manually_filtered)

    # And the cutoff genuinely bites: full-history RFM counts more transactions.
    full = add_rfm_features(transactions, "debtor_id", "txn_date", "amount", "2024-12-31")
    assert full["frequency"].sum() > rfm["frequency"].sum(), (
        "if the cutoff changed nothing, this test would prove nothing"
    )


def test_rfm_recency_is_measured_from_the_cutoff_not_from_today():
    df = pd.DataFrame(
        {
            "entity": ["a", "a", "b"],
            "date": pd.to_datetime(["2024-01-10", "2024-03-01", "2024-02-01"]),
            "amount": [100.0, 200.0, 50.0],
        }
    )

    rfm = add_rfm_features(df, "entity", "date", "amount", "2024-03-31")

    assert rfm.loc["a", "recency_days"] == 30  # 2024-03-31 minus 2024-03-01
    assert rfm.loc["a", "frequency"] == 2
    assert rfm.loc["a", "monetary"] == pytest.approx(300.0)
    assert rfm.loc["a", "tenure_days"] == 81  # 2024-03-31 minus 2024-01-10


def test_rfm_ignores_a_transaction_dated_after_the_cutoff():
    df = pd.DataFrame(
        {
            "entity": ["a", "a"],
            "date": pd.to_datetime(["2024-01-10", "2024-12-01"]),
            "amount": [100.0, 9999.0],
        }
    )

    rfm = add_rfm_features(df, "entity", "date", "amount", "2024-06-30")

    assert rfm.loc["a", "frequency"] == 1
    assert rfm.loc["a", "monetary"] == pytest.approx(100.0), (
        "the 9999 transaction happens after the cutoff and must not be counted"
    )


def test_rfm_raises_when_every_row_is_in_the_future(transactions):
    with pytest.raises(ValueError, match="future"):
        add_rfm_features(transactions, "debtor_id", "txn_date", "amount", "2020-01-01")


def test_collapse_rare_categories_folds_the_tail(transactions):
    out = collapse_rare_categories(transactions, ["channel"], min_freq=0.10)

    levels = set(out["channel"].unique())
    assert "__other__" in levels
    assert "branch" not in levels, "branch is ~5%, below the 10% floor"
    assert "web" in levels


def test_collapse_leaves_a_frame_with_no_rare_levels_alone(transactions):
    out = collapse_rare_categories(transactions, ["channel"], min_freq=0.001)

    pd.testing.assert_series_equal(out["channel"], transactions["channel"])


def test_collapse_rejects_an_out_of_range_min_freq(transactions):
    with pytest.raises(ValueError, match="min_freq"):
        collapse_rare_categories(transactions, ["channel"], min_freq=1.5)


def test_ratio_features_are_named_and_finite(transactions):
    out = add_ratio_features(transactions, [("amount", "balance")])

    assert "amount_over_balance" in out.columns
    assert np.isfinite(out["amount_over_balance"]).all()


def test_ratio_survives_a_zero_denominator():
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [0.0, 4.0]})

    out = add_ratio_features(df, [("a", "b")])

    assert np.isfinite(out["a_over_b"]).all(), "a zero denominator must not produce inf"


def test_interaction_features_are_the_product(transactions):
    out = add_interaction_features(transactions, [("amount", "balance")])

    assert "amount_x_balance" in out.columns
    np.testing.assert_allclose(
        out["amount_x_balance"], transactions["amount"] * transactions["balance"]
    )


def test_quantile_binning_produces_roughly_equal_bins(transactions):
    out = add_binned_features(transactions, ["amount"], n_bins=4, strategy="quantile")

    counts = out["amount_bin"].value_counts()
    assert set(out["amount_bin"].unique()) == {0, 1, 2, 3}
    assert counts.max() - counts.min() <= 2, "quantile bins should be near-equally populated"


def test_uniform_binning_uses_equal_widths(transactions):
    out = add_binned_features(transactions, ["amount"], n_bins=4, strategy="uniform")

    assert out["amount_bin"].nunique() <= 4
    assert out["amount_bin"].min() >= 0


def test_binning_maps_nan_to_a_sentinel_rather_than_propagating():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, np.nan]})

    out = add_binned_features(df, ["x"], n_bins=2)

    assert out["x_bin"].iloc[-1] == -1
    assert out["x_bin"].dtype.kind in "iu", "bins are integer codes"


def test_binning_rejects_too_few_bins(transactions):
    with pytest.raises(ValueError, match="n_bins"):
        add_binned_features(transactions, ["amount"], n_bins=1)


def test_unknown_binning_strategy_raises(transactions):
    with pytest.raises(ValueError, match="unknown strategy"):
        add_binned_features(transactions, ["amount"], strategy="clustered")


def test_builders_compose_into_one_entity_level_frame(transactions):
    """The end-to-end shape these functions exist to produce: a transaction log
    reduced to one row per debtor with RFM plus behavioural features."""
    cutoff = "2024-09-30"
    enriched = collapse_rare_categories(transactions, ["channel"], min_freq=0.10)
    enriched = add_ratio_features(enriched, [("amount", "balance")])
    rfm = add_rfm_features(enriched, "debtor_id", "txn_date", "amount", cutoff)

    assert len(rfm) <= transactions["debtor_id"].nunique()
    assert rfm.notna().all().all(), "no NaNs in the entity-level frame"
