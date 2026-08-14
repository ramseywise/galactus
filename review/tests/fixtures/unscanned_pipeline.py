"""Fixture: the leak that only a scan can find, and a group key the split ignores.

The third member of the `leaky_pipeline.py` / `clean_pipeline.py` pair, and the
one that motivates GAL-3. Both other fixtures are detectable by reading the
code: `leaky_pipeline` has post-outcome *names* and a visibly wrong ordering,
`clean_pipeline` has neither. This file is deliberately clean by every heuristic
in the skill's §Target leakage name list, and still leaks.

Two plants, one per rule in issue #3:

RULE 1 — `last_fico_range_high` is a post-outcome column that looks innocent.
The name matches no `*_final` / `*_actual` / `*_outcome` pattern, the column has
zero nulls, and its dtype is an ordinary float. Nothing distinguishes it from
`balance` by inspection. It is the lending POC's real finding (DESIGN.md §"The
finding the name heuristic missed", 0.9511 single-feature AUC) reproduced at
fixture scale: the values track the label because the last FICO pull happens
*after* the account resolves. Only a single-feature association scan reaches it,
and no scan is run anywhere in this file. A reviewer that returns `[]` here has
committed exactly the collapse the dimension is named after.

RULE 2 — `debtor_id` is present in the frame and excluded from the splitter.
`train_test_split` receives no `groups=` (and could not honour one), so the same
debtor lands on both sides. The key is weak — 2 of 6 rows in multi-row groups —
which per the skill is stated in the finding, not grounds to suppress it.

Not imported as a module under test. Do not "fix" either plant; the plants are
the fixture.
"""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split


def load_frame() -> pd.DataFrame:
    """Schema defined in code so the plants are verifiable rather than described.

    `last_fico_range_high` is drawn after the account resolves: paid accounts
    get a recovered score, charged-off accounts a collapsed one. That ordering
    is invisible in the column name and is the entire leak.
    """
    return pd.DataFrame(
        {
            "debtor_id": [1, 1, 2, 3, 4, 5],
            "balance": [100.0, 250.0, 80.0, 400.0, 60.0, 900.0],
            "months_on_book": [12, 18, 6, 24, 9, 36],
            # The planted leak. Tracks `paid` almost perfectly, name says nothing.
            "last_fico_range_high": [520.0, 715.0, 505.0, 730.0, 498.0, 745.0],
            "paid": [0, 1, 0, 1, 0, 1],
        }
    )


def train(df: pd.DataFrame) -> float:
    """No single-feature association scan is run anywhere in this path.

    The frame is split, a model is fitted, and a score is reported — the score
    is the `quoted_span` anchor the skill's rule calls for, since the absent
    scan has no line of its own.
    """
    y = df["paid"]
    # `debtor_id` stays out of the feature matrix, so this is not the toolkit
    # defect of forcing the key in as a feature. It is the inverse: the key is
    # available in `df` and simply never reaches the splitter.
    X = df.drop(columns=["paid", "debtor_id"])

    # Split before any fit — the ordering here is correct on purpose, so an
    # ordering-based reviewer finds nothing and the fixture isolates Rule 1.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.34, random_state=42)

    model = LogisticRegression(random_state=42)
    model.fit(X_train, y_train)
    return model.score(X_test, y_test)
