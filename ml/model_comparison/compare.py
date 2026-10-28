"""Baseline model comparison: fit N classifiers on the same cross-validation
folds and produce a side-by-side accuracy/ROC-AUC/fit-time table — the
"instantaneously compare a boosting model and random forest for initial
baseline" workflow.

`TabularPreprocessor` is adapted from a real, deployed LightGBM credit-scoring
pipeline's `PreprocessData` transformer (missing-value treatment + one-hot
encoding) — genericized to take feature-type lists as constructor params
instead of importing them from a dataset-specific `features.py` module.
The comparison-table structure is inspired by a real production forecasting
project's model-comparison harness (same idea — same CV folds, side-by-side
metrics — applied here to classifiers instead of forecasters).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class TabularPreprocessor(BaseEstimator, TransformerMixin):
    """Imputation + scaling + one-hot encoding for mixed numeric/categorical
    tabular data. sklearn-compatible (fit/transform), so it drops straight into
    a `Pipeline` — which is where it must go, so that every fitted statistic is
    learned inside the fold (naming.md §3 rule 3).

    Numeric columns: median imputation then standardization. Both are *fitted*,
    which is the reason this class must never be fitted on a full frame before
    splitting — doing so leaks the median and the column moments across folds.
    Categorical columns: missing values filled with a "{column}_missing"
    category, then one-hot encoded (unknown categories at transform time are
    ignored, not errored on).

    This replaces a `-9999` sentinel fill (2026-08-12). The sentinel was
    harvested from a deployed LightGBM pipeline where it was correct — a tree can
    split around it, and "missing" carries signal. It is wrong for every
    distance- or coefficient-based model: -9999 sits ~10^4 away from the real
    support, so a linear model spends its coefficient on the sentinel and a
    scaled model has its variance dominated by it. The class's own docstring
    recommended `SimpleImputer` for linear models, and logistic regression
    emitted `ConvergenceWarning` on the template's own test data.

    Set `numeric_strategy="sentinel"` to restore the old behaviour for a
    tree-only comparison where encoding missingness as a splittable value is
    genuinely wanted.
    """

    def __init__(
        self,
        numeric_features: list[str],
        categorical_features: list[str],
        missing_value: int = -9999,
        numeric_strategy: str = "median",
        scale: bool = True,
    ):
        self.numeric_features = numeric_features
        self.categorical_features = categorical_features
        self.missing_value = missing_value
        self.numeric_strategy = numeric_strategy
        self.scale = scale
        self.ohe = OneHotEncoder(handle_unknown="ignore", dtype=np.float64)
        self.imputer: SimpleImputer | None = None
        self.scaler: StandardScaler | None = None

    def fit(self, x: pd.DataFrame, y=None):
        if self.numeric_features:
            numeric = x[self.numeric_features]
            if self.numeric_strategy != "sentinel":
                self.imputer = SimpleImputer(strategy=self.numeric_strategy)
                numeric = pd.DataFrame(
                    self.imputer.fit_transform(numeric),
                    columns=self.numeric_features,
                )
            else:
                numeric = numeric.fillna(self.missing_value)
            if self.scale:
                self.scaler = StandardScaler().fit(numeric)
        if self.categorical_features:
            self.ohe.fit(self._treat_categorical(x)[self.categorical_features])
        return self

    def transform(self, x: pd.DataFrame) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []

        if self.numeric_features:
            numeric = x[self.numeric_features]
            if self.imputer is not None:
                numeric = pd.DataFrame(
                    self.imputer.transform(numeric),
                    columns=self.numeric_features,
                )
            else:
                numeric = numeric.fillna(self.missing_value)
            if self.scaler is not None:
                numeric = pd.DataFrame(
                    self.scaler.transform(numeric),
                    columns=self.numeric_features,
                )
            frames.append(numeric.reset_index(drop=True))

        if self.categorical_features:
            categorical = self._treat_categorical(x)
            encoded = self.ohe.transform(categorical[self.categorical_features]).toarray()
            cols = self.ohe.get_feature_names_out(self.categorical_features)
            frames.append(pd.DataFrame(encoded, columns=cols))

        out = pd.concat(frames, axis=1) if frames else pd.DataFrame(index=range(len(x)))
        # Sanitize column names — LightGBM/XGBoost reject special characters.
        out.columns = ["".join(c if c.isalnum() else "_" for c in str(col)) for col in out.columns]
        return out

    def _treat_categorical(self, x: pd.DataFrame) -> pd.DataFrame:
        x = x.copy()
        for col in self.categorical_features:
            x[col] = x[col].fillna(f"{col}_missing").astype(str)
        return x


@dataclass
class ModelCVResult:
    model_name: str
    mean_accuracy: float
    std_accuracy: float
    mean_roc_auc: float
    std_roc_auc: float
    mean_fit_seconds: float


@dataclass
class ModelComparisonResult:
    results: list[ModelCVResult] = field(default_factory=list)

    def as_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([r.__dict__ for r in self.results]).sort_values(
            "mean_roc_auc", ascending=False
        )

    def print_table(self) -> None:
        print(self.as_dataframe().to_string(index=False))


def default_baseline_models() -> dict[str, BaseEstimator]:
    """Logistic regression (linear baseline), random forest (bagged trees),
    and LightGBM (boosting) — the three model families worth comparing before
    investing in feature engineering or hyperparameter tuning.

    The logistic baseline is wrapped in a `StandardScaler` pipeline rather than
    handed the raw frame. lbfgs on unscaled features hit its iteration limit and
    emitted `ConvergenceWarning` on the template's own test data, which makes the
    explainability floor look worse than it is — and the floor is the number every
    other model is judged against. The scaler is fitted inside whatever CV split
    wraps the pipeline, so this does not leak (naming.md §3 rule 3).
    """
    models: dict[str, BaseEstimator] = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=42),
    }
    try:
        from lightgbm import LGBMClassifier

        # LGBMClassifier genuinely inherits sklearn's BaseEstimator at runtime;
        # lightgbm's bundled stub just doesn't declare it — stub gap.
        models["lightgbm"] = LGBMClassifier(random_state=42, verbosity=-1)  # type: ignore[assignment]
    except ImportError:
        pass  # lightgbm is an optional dependency; comparison still runs without it
    return models


def compare_classifiers(
    x: pd.DataFrame,
    y: pd.Series,
    models: dict[str, BaseEstimator] | None = None,
    preprocessor: TransformerMixin | None = None,
    cv: int = 5,
    random_state: int = 42,
) -> ModelComparisonResult:
    """Fit each model on the same stratified CV folds, return accuracy/ROC-AUC/
    fit-time for each — the fast, cheap first step before deciding where to
    spend real tuning effort."""
    models = models or default_baseline_models()
    cv_splitter = StratifiedKFold(n_splits=cv, shuffle=True, random_state=random_state)

    results: list[ModelCVResult] = []
    for name, estimator in models.items():
        pipeline = make_pipeline(preprocessor, estimator) if preprocessor is not None else estimator
        start = time.perf_counter()
        scores = cross_validate(
            pipeline,
            x,
            y,
            cv=cv_splitter,
            scoring=["accuracy", "roc_auc"],
            return_train_score=False,
        )
        elapsed = time.perf_counter() - start

        results.append(
            ModelCVResult(
                model_name=name,
                mean_accuracy=float(np.mean(scores["test_accuracy"])),
                std_accuracy=float(np.std(scores["test_accuracy"])),
                mean_roc_auc=float(np.mean(scores["test_roc_auc"])),
                std_roc_auc=float(np.std(scores["test_roc_auc"])),
                mean_fit_seconds=elapsed / cv,
            )
        )

    return ModelComparisonResult(results=results)
