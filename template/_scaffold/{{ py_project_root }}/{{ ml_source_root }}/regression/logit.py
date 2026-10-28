"""Logistic regression with recursive feature elimination (RFE) and
coefficient-significance analysis.

Adapted from a real production nutrition/symptom-tracking study — genericized
(the original had domain-specific food/menstrual-cycle logic mixed in; this
keeps only the reusable statistical core: RFE-based feature selection,
coefficient/p-value extraction, and cross-model significance comparison).

Usage:
    model = fit_rfe_logit(df, features=["age", "income", "tenure"], target="churned")
    coefs = coefficient_table(model)
    sig = significant_features(coefs, alpha=0.05)
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.feature_selection import RFE
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


def fit_rfe_logit(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    n_features: int | None = None,
):
    """Fit a logistic regression on the top-`n_features` features selected by RFE.

    Falls back to fewer features if RFE/statsmodels fails to converge (e.g. due
    to perfect separation or collinearity) — retries with one fewer feature
    until it succeeds or runs out of features, matching the "best effort, don't
    crash the whole run over one bad feature set" pattern used elsewhere in
    this template's eval/W&B code.

    Returns the fitted `statsmodels.Logit` result, or None if no feature subset
    could be fit.
    """
    if n_features is None:
        n_features = len(features)

    x = df[features]
    y = df[target]
    x_scaled = StandardScaler().fit_transform(x)

    while n_features > 0 and len(x.columns) > 0:
        try:
            estimator = LogisticRegression(random_state=42)
            selector = RFE(estimator, n_features_to_select=min(n_features, len(x.columns)), step=1)
            selector = selector.fit(x_scaled, y)

            selected = x.columns[selector.support_].tolist()
            x_selected = df[selected]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = sm.Logit(y, sm.add_constant(x_selected)).fit(disp=0)
            return fitted
        except (TypeError, np.linalg.LinAlgError):
            n_features -= 1

    return None


def coefficient_table(fitted_model) -> pd.DataFrame:
    """Coefficients and p-values for every non-intercept feature in the model."""
    features = fitted_model.model.exog_names[1:]
    return pd.DataFrame(
        {"coef": fitted_model.params[1:], "p": fitted_model.pvalues[1:]},
        index=features,
    )


def significant_features(coef_df: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """Rows of `coef_df` with p-value below `alpha`, sorted by |coefficient|."""
    sig = coef_df[coef_df["p"] < alpha].copy()
    # pandas-stubs types DataFrame.__getitem__ loosely (a real, known stub
    # limitation, not a real type error) — a single string key always returns
    # a Series here, coef_df is never built with duplicate column names.
    coef_col: pd.Series = sig["coef"]  # type: ignore[assignment]
    return sig.reindex(coef_col.abs().sort_values(ascending=False).index)  # type: ignore[return-value]


def split_by_direction(coef_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split coefficients into (negative, positive) sub-tables, each sorted by
    |coefficient| descending — the shape `plot_feature_importance` expects."""
    neg = coef_df[coef_df["coef"] <= 0].copy()
    pos = coef_df[coef_df["coef"] > 0].copy()
    neg_coef: pd.Series = neg["coef"]  # type: ignore[assignment]
    pos_coef: pd.Series = pos["coef"]  # type: ignore[assignment]
    neg = neg.reindex(neg_coef.abs().sort_values(ascending=False).index)
    pos = pos.reindex(pos_coef.abs().sort_values(ascending=False).index)
    return neg, pos  # type: ignore[return-value]


def compare_coefficients(*fitted_models, alpha: float | None = None) -> pd.DataFrame:
    """Combine multiple models' (e.g. one per subgroup/fold) significant
    coefficients into one comparison table, one column per model.

    Only coefficients with p <= alpha are shown (others are NaN) — set
    alpha=1.0 to show every coefficient regardless of significance.
    """
    alpha = 1.0 if alpha is None else alpha
    all_features: set[str] = set()
    for result in fitted_models:
        all_features.update(result.model.exog_names)

    table = pd.DataFrame({"Features": sorted(all_features, reverse=True)})

    for i, result in enumerate(fitted_models, 1):
        coef_series = pd.Series(index=result.model.exog_names, data=result.params)
        pvalue_series = pd.Series(index=result.model.exog_names, data=result.pvalues)
        significant: pd.Series = coef_series[pvalue_series <= alpha]  # type: ignore[assignment]
        table[f"Model {i}"] = table["Features"].map(significant)  # type: ignore[arg-type]

    return table
