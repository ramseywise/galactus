from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

from ml.transform import (
    ColumnPlan,
    TabularPreprocessor,
    TargetEncoder,
    build_transformer,
    infer_column_types,
)

RANDOM_STATE = 42


@pytest.fixture
def mixed_frame() -> pd.DataFrame:
    """Mixed-type frame with NaNs, a 200-category column, a constant, and a
    datetime — one planted problem per bucket."""
    rng = np.random.default_rng(RANDOM_STATE)
    n = 400

    age = rng.normal(45, 12, n)
    age[rng.choice(n, 40, replace=False)] = np.nan

    return pd.DataFrame(
        {
            "age": age,
            "balance": rng.gamma(2.0, 500.0, n),
            "segment": rng.choice(["a", "b", "c"], n),
            "account_id": [f"acct_{i % 200}" for i in range(n)],
            "opened_at": pd.to_datetime("2024-01-01")
            + pd.to_timedelta(rng.integers(0, 700, n), "D"),
            "is_active": rng.random(n) > 0.3,
            "constant_col": ["same"] * n,
            "target": rng.integers(0, 2, n),
        }
    )


def test_infer_column_types_buckets_every_column(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target")

    assert set(plan.numeric) == {"age", "balance"}
    assert set(plan.categorical) == {"segment"}
    assert set(plan.high_cardinality) == {"account_id"}, "200 levels exceeds the one-hot threshold"
    assert set(plan.datetime) == {"opened_at"}
    assert set(plan.boolean) == {"is_active"}
    assert set(plan.unused) == {"constant_col"}
    assert plan.target == "target"


def test_target_is_never_a_feature(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target")

    assert "target" not in plan.features, "leaving the label in X is leakage by construction"


def test_infer_records_cardinality_and_missingness(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target")

    assert plan.cardinality["account_id"] == 200
    assert plan.missing_fraction["age"] == pytest.approx(0.1, abs=0.01)
    assert plan.missing_fraction["balance"] == 0.0
    assert "constant" in plan.reasons["constant_col"]


def test_unknown_target_raises(mixed_frame):
    with pytest.raises(KeyError, match="not_a_column"):
        infer_column_types(mixed_frame, target="not_a_column")


def test_excluded_columns_are_kept_out_of_every_feature_bucket(mixed_frame):
    """`account_id` is the shape a group column has — 200 near-unique levels. Left
    to inference it lands in `high_cardinality` and gets target-encoded, which
    encodes account identity against the label. Excluding it is the fix."""
    plan = infer_column_types(mixed_frame, target="target", exclude=["account_id"])

    assert "account_id" not in plan.features
    assert "account_id" not in plan.high_cardinality
    assert plan.excluded == ("account_id",)


def test_excluded_is_distinct_from_unused(mixed_frame):
    """A bookkeeping column and a useless one are different facts about a column,
    and a report that conflates them tells the reader the wrong thing."""
    plan = infer_column_types(mixed_frame, target="target", exclude=["account_id"])

    assert "account_id" not in plan.unused
    assert "constant_col" in plan.unused
    assert "excluded by the caller" in plan.reasons["account_id"]


def test_excluding_an_absent_column_raises(mixed_frame):
    """A typo in a group column name would otherwise silently exclude nothing and
    leave the leak in place."""
    with pytest.raises(KeyError, match="not_a_column"):
        infer_column_types(mixed_frame, target="target", exclude=["not_a_column"])


def test_describe_reports_excluded_columns(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target", exclude=["account_id"])
    described = plan.describe()

    row = described[described["column"] == "account_id"].iloc[0]
    assert row["bucket"] == "excluded"


def test_all_null_column_is_unused():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "empty": [np.nan] * 3, "y": [0, 1, 0]})
    plan = infer_column_types(df, target="y")

    assert "empty" in plan.unused
    assert "missing" in plan.reasons["empty"]


def test_describe_returns_one_row_per_column(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target")
    described = plan.describe()

    assert len(described) == len(mixed_frame.columns) - 1  # target excluded
    assert set(described.columns) == {
        "column",
        "bucket",
        "n_unique",
        "missing_fraction",
        "reason",
    }


def test_build_transformer_handles_the_whole_mixed_frame(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target")
    transformer = build_transformer(plan)

    x = mixed_frame.drop(columns=["target"])
    y = mixed_frame["target"]
    out = transformer.fit_transform(x, y)

    assert out.shape[0] == len(mixed_frame)
    assert np.isfinite(out).all(), "no NaNs may survive the transformer"


def test_missing_indicators_preserve_not_missing_at_random_signal():
    """A column that is missing exactly when the label is 1 carries the whole
    signal in its missingness. Median imputation alone destroys it; the missing
    indicator keeps it."""
    n = 200
    y = np.array([0, 1] * (n // 2))
    x_col = np.where(y == 1, np.nan, 5.0)
    df = pd.DataFrame({"nmar": x_col, "noise": np.zeros(n) + 1.0})
    plan = ColumnPlan(numeric=("nmar", "noise"))

    with_indicator = build_transformer(plan, add_missing_indicators=True).fit_transform(df, y)
    without = build_transformer(plan, add_missing_indicators=False).fit_transform(df, y)

    assert with_indicator.shape[1] > without.shape[1], "the indicator column must be added"
    # The indicator column reproduces y exactly; without it the frame is constant.
    correlations = [
        abs(np.corrcoef(with_indicator[:, i], y)[0, 1])
        for i in range(with_indicator.shape[1])
        if np.std(with_indicator[:, i]) > 0
    ]
    assert max(correlations) == pytest.approx(1.0)
    assert all(np.std(without[:, i]) == 0 for i in range(without.shape[1]))


def test_high_cardinality_does_not_explode_into_one_hot(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target")
    out = build_transformer(plan).fit_transform(
        mixed_frame.drop(columns=["target"]), mixed_frame["target"]
    )

    # 200 one-hot columns would dwarf everything else; target encoding gives 1.
    assert out.shape[1] < 60


def test_target_encoding_fitted_on_a_fold_does_not_see_that_folds_rows():
    """The leakage invariant. A category whose target mean differs between train
    and validation must be encoded using the *training* mean only — if the
    encoder had seen the validation rows, the encoded value would shift toward
    them."""
    train = pd.DataFrame({"cat": ["a"] * 50 + ["b"] * 50})
    y_train = pd.Series([1] * 50 + [0] * 50)
    # In validation, 'a' flips to all-zero. A fold-safe encoder must not notice.
    validation = pd.DataFrame({"cat": ["a"] * 50})

    encoder = TargetEncoder(smoothing=0.0).fit(train, y_train)
    encoded_validation = encoder.transform(validation)

    assert encoded_validation.min() == pytest.approx(1.0), (
        "'a' must carry the training mean (1.0), not the validation mean (0.0)"
    )

    # And refitting on the union *does* move it — proving the assertion above is
    # a real constraint rather than an encoder that ignores its input.
    contaminated = TargetEncoder(smoothing=0.0).fit(
        pd.concat([train, validation], ignore_index=True),
        pd.concat([y_train, pd.Series([0] * 50)], ignore_index=True),
    )
    assert contaminated.transform(validation).min() < 1.0


def test_target_encoder_refits_per_cv_fold_inside_a_pipeline():
    """The same invariant, exercised the way production uses it: the encoder is
    a Pipeline step, so sklearn refits it on each fold's training rows."""
    rng = np.random.default_rng(RANDOM_STATE)
    n = 300
    df = pd.DataFrame({"cat": rng.choice([f"c{i}" for i in range(10)], n)})
    y = pd.Series(rng.integers(0, 2, n))

    pipeline = Pipeline(
        [
            ("encode", TargetEncoder(smoothing=5.0)),
            ("model", LogisticRegression(max_iter=1000)),
        ]
    )

    seen_mappings = []
    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    for train_idx, _ in splitter.split(df, y):
        fitted = pipeline.fit(df.iloc[train_idx], y.iloc[train_idx])
        seen_mappings.append(dict(fitted.named_steps["encode"].mappings_["cat"]))

    assert seen_mappings[0] != seen_mappings[1], (
        "a per-fold refit must produce different statistics; identical mappings "
        "would mean the encoder was fitted once on everything"
    )


def test_target_encoder_requires_a_target():
    with pytest.raises(ValueError, match="needs the target"):
        TargetEncoder().fit(pd.DataFrame({"cat": ["a", "b"]}))


def test_target_encoder_falls_back_to_global_mean_for_unseen_categories():
    train = pd.DataFrame({"cat": ["a", "a", "b", "b"]})
    y = pd.Series([1, 1, 0, 0])
    encoder = TargetEncoder(smoothing=0.0).fit(train, y)

    out = encoder.transform(pd.DataFrame({"cat": ["never_seen"]}))

    assert out[0, 0] == pytest.approx(0.5), "unseen levels get the global mean, not an error"


def test_datetime_decomposition_produces_calendar_parts(mixed_frame):
    plan = infer_column_types(mixed_frame, target="target")
    transformer = build_transformer(plan).fit(
        mixed_frame.drop(columns=["target"]), mixed_frame["target"]
    )
    names = list(transformer.get_feature_names_out())

    assert any(name.endswith("opened_at_month") for name in names)
    assert any(name.endswith("opened_at_dayofweek") for name in names)
    assert not any(name.endswith("__opened_at") for name in names), (
        "the raw timestamp must not survive as a feature"
    )


def test_build_transformer_rejects_a_plan_with_no_usable_columns():
    plan = ColumnPlan(unused=("everything",))

    with pytest.raises(ValueError, match="no usable feature columns"):
        build_transformer(plan)


def test_unknown_strategy_names_raise():
    plan = ColumnPlan(numeric=("x",), categorical=("c",))

    with pytest.raises(ValueError, match="numeric strategy"):
        build_transformer(plan, numeric="quantum")
    with pytest.raises(ValueError, match="categorical strategy"):
        build_transformer(plan, categorical="quantum")


def test_tabular_preprocessor_is_still_reachable_from_the_new_layer():
    """The existing transformer is extended, not replaced — code importing it
    from `ml.transform` and from its original module gets the same class."""
    from ml.model_comparison.compare import TabularPreprocessor as Original

    assert TabularPreprocessor is Original
