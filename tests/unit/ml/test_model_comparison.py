from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.datasets import load_breast_cancer

from ml.model_comparison.compare import (
    TabularPreprocessor,
    compare_classifiers,
    default_baseline_models,
)


def test_tabular_preprocessor_handles_missing_and_categorical():
    df = pd.DataFrame(
        {
            "age": [25, np.nan, 40, 30],
            "income": [50000, 60000, np.nan, 45000],
            "segment": ["a", "b", np.nan, "a"],
        }
    )
    pre = TabularPreprocessor(numeric_features=["age", "income"], categorical_features=["segment"])
    out = pre.fit_transform(df)

    assert out["age"].isna().sum() == 0
    assert out["income"].isna().sum() == 0
    assert any(col.startswith("segment_") for col in out.columns)


def test_tabular_preprocessor_ignores_unknown_category_at_transform():
    train = pd.DataFrame({"x": [1, 2], "cat": ["a", "b"]})
    test = pd.DataFrame({"x": [3], "cat": ["never_seen"]})
    pre = TabularPreprocessor(numeric_features=["x"], categorical_features=["cat"])
    pre.fit(train)
    out = pre.transform(test)  # must not raise on the unseen category
    assert len(out) == 1


def test_compare_classifiers_real_dataset():
    data = load_breast_cancer(as_frame=True)
    x = data.frame.drop(columns=["target"])
    y = data.frame["target"]

    result = compare_classifiers(x, y, cv=3)
    df = result.as_dataframe()

    assert "logistic_regression" in df["model_name"].values
    assert "random_forest" in df["model_name"].values
    # A real, well-separated dataset should score well above chance for every model.
    assert (df["mean_roc_auc"] > 0.9).all()


def test_default_baseline_models_includes_logistic_and_forest():
    models = default_baseline_models()
    assert "logistic_regression" in models
    assert "random_forest" in models
