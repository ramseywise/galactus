"""Fixture: a training path with a planted leak. The `review-leakage` twin of
`clean_pipeline.py` — the two differ only in the ordering that causes the leak.

Not imported by the suite as a module under test. It is the acceptance artifact
for Step 10: the reporter must FLAG this file, and the signal must ACTIVATE on
it. Do not "fix" the leak — the leak is the fixture.
"""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def load_frame() -> pd.DataFrame:
    """The schema is defined here rather than described in a comment, so the
    planted leaks are verifiable from code. `settlement_date` and
    `amount_recovered` are written only when an account pays; `debtor_id`
    repeats across rows; `cohort_month` is the time axis."""
    return pd.DataFrame(
        {
            "debtor_id": [1, 1, 2, 2, 3, 3],
            "cohort_month": ["2026-01", "2026-02"] * 3,
            "balance": [100.0, 250.0, 80.0, 400.0, 60.0, 900.0],
            "settlement_date": [None, "2026-03-01", None, "2026-03-04", None, None],
            "amount_recovered": [0.0, 250.0, 0.0, 400.0, 0.0, 0.0],
            "paid": [0, 1, 0, 1, 0, 0],
        }
    )


def train(df: pd.DataFrame) -> float:
    y = df["paid"]
    # LEAK 1 — target leakage. `settlement_date` and `amount_recovered` are
    # populated only once the account has paid, so they encode the label. Only
    # the label column is dropped; both post-outcome columns stay as features.
    X = df.drop(columns=["paid"])

    # LEAK 2 — fit before split. The scaler sees the test rows' mean and
    # variance, so the held-out score is optimistic. Fitting a transform on the
    # full frame before splitting is the canonical ordering error.
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # LEAK 3 — random split on grouped, time-structured data. `debtor_id`
    # repeats across rows and `cohort_month` declares a time axis, so a random
    # split puts the same debtor on both sides and trains on the future.
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

    model = LogisticRegression(random_state=42)
    model.fit(X_train, y_train)
    return model.score(X_test, y_test)
