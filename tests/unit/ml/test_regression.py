from __future__ import annotations

import pandas as pd
from sklearn.datasets import load_breast_cancer

from ml.regression.logit import (
    coefficient_table,
    compare_coefficients,
    fit_rfe_logit,
    significant_features,
    split_by_direction,
)
from ml.regression.plots import model_comparison_table, plot_feature_importance


def _breast_cancer_df() -> tuple[pd.DataFrame, list[str]]:
    data = load_breast_cancer(as_frame=True)
    df = data.frame
    features = [c for c in df.columns if c != "target"]
    return df, features


def test_fit_rfe_logit_produces_significant_coefficients():
    df, features = _breast_cancer_df()
    model = fit_rfe_logit(df, features=features, target="target", n_features=5)
    assert model is not None

    coefs = coefficient_table(model)
    assert len(coefs) <= 5
    assert {"coef", "p"}.issubset(coefs.columns)

    sig = significant_features(coefs, alpha=0.05)
    # A real, well-separated dataset like breast_cancer should yield at least
    # one statistically significant predictor among the RFE-selected features.
    assert len(sig) >= 1


def test_split_by_direction_and_plot():
    df, features = _breast_cancer_df()
    model = fit_rfe_logit(df, features=features, target="target", n_features=6)
    assert model is not None
    coefs = coefficient_table(model)
    neg, pos = split_by_direction(coefs)
    assert len(neg) + len(pos) == len(coefs)

    fig = plot_feature_importance(
        neg if len(neg) else coefs.iloc[:1], pos if len(pos) else coefs.iloc[:1]
    )
    assert fig is not None


def test_compare_coefficients_across_two_models():
    df, features = _breast_cancer_df()
    half = len(df) // 2
    model_a = fit_rfe_logit(df.iloc[:half], features=features, target="target", n_features=4)
    model_b = fit_rfe_logit(df.iloc[half:], features=features, target="target", n_features=4)
    assert model_a is not None and model_b is not None

    table = compare_coefficients(model_a, model_b, alpha=1.0)
    assert "Model 1" in table.columns
    assert "Model 2" in table.columns


def test_model_comparison_table():
    df, features = _breast_cancer_df()
    model = fit_rfe_logit(df, features=features, target="target", n_features=3)
    assert model is not None
    table = model_comparison_table([model], ["all_data"])
    assert table.loc[0, "label"] == "all_data"
    assert "aic" in table.columns
