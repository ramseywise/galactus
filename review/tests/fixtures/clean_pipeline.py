"""Fixture: the same training path with the leaks removed. The `review-leakage`
twin of `leaky_pipeline.py`.

Same problem, same columns, same model — the differences are ordering and column
selection, which is what makes the pair a usable acceptance check. The reporter
must return clean on this file. If it flags something here, the finding is a
false positive against a deliberately correct path.
"""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Populated only after the outcome is known — excluded from the feature matrix
# rather than dropped later, so the exclusion is visible at the top of the file.
POST_OUTCOME_COLUMNS = ["settlement_date", "amount_recovered"]


def train(df: pd.DataFrame) -> float:
    y = df["paid"]
    groups = df["debtor_id"]
    X = df.drop(columns=["paid", "debtor_id", *POST_OUTCOME_COLUMNS])

    # Split first. Nothing is fitted before this line.
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    # Transform and estimator in one Pipeline: the scaler is fitted on training
    # folds only, by construction rather than by discipline.
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(random_state=42)),
        ]
    )
    model.fit(X_train, y_train)
    return model.score(X_test, y_test)
