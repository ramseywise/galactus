"""Seeded synthetic fixture twins — a clean frame and its planted-leak sibling.

FIXTURE SPEC — named before the first run (plan Key Unknown 1). The reproduction
target for the *real* frame is the frozen Step 15 table (logistic PR-AUC 0.4213 over a
prevalence floor of 0.2056). None of that transfers here: on a synthetic frame the
baseline is recomputed on the frame itself. **The synthetic prevalence — 103/500 =
0.206 among resolved rows, fixed by construction, exposed as `SYNTHETIC_PREVALENCE` —
is the PR-AUC floor every dry-run assertion compares against. Nothing synthetic is ever
compared against 0.4213.** A synthetic frame that accidentally makes the tiny model
look strong is the graded-on-its-own-curve failure; `beats_baseline` on this frame is a
statement about the harness path, not about any model.

Shape: extract-schema-shaped (~600 rows) — `loan_status` mixing resolved and unresolved
values, `emp_title`/`zip_code`/`annual_inc` for the group key (with missing values and
collisions, so multi-row groups exist), an `id` identifier, and a numeric feature block
whose per-column signal is deliberately weak (single-feature AUC well under the 0.95
alarm). Prevalence sits near the real 20.56% so `sampling="class_weight"` stays on the
same code path.

The twins follow `review/tests/fixtures/leaky_pipeline.py` / `clean_pipeline.py`:
`clean_frame(seed)` passes every guard after `prepare_frame`; `planted_leak_frame(seed)`
is byte-identical except for two planted leaks —

    (i)  `recoveries` — a `LEAKAGE_COLUMNS` member, label-correlated. An intact
         `prepare_frame` drops it (asserted in tests); a regressed drop lets it
         through, and guard (a) is what catches exactly that.
    (ii) `post_outcome_score` — a near-copy of the label under a name no drop list
         knows, so it *survives* `prepare_frame` and guard (b) must catch it.

Toolkit-free: numpy + pandas only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Resolved-row label counts, fixed by construction — not sampled, so the prevalence
#: is exact for every seed. 103/500 = 0.206 ≈ the real frame's 20.56%.
N_RESOLVED = 500
N_POSITIVE = 103
N_UNRESOLVED = 100

#: The dry-run's baseline: PR-AUC of a no-skill classifier on this frame IS this number.
SYNTHETIC_PREVALENCE = N_POSITIVE / N_RESOLVED

_UNRESOLVED_STATUSES = ["Current", "Late (31-120 days)", "In Grace Period"]

_EMP_TITLES = [f"title {i}" for i in range(40)]
_ZIP_CODES = [f"{100 + i:03d}xx" for i in range(30)]


def clean_frame(seed: int) -> pd.DataFrame:
    """A raw, extract-schema-shaped frame that passes every guard after `prepare_frame`."""
    rng = np.random.default_rng(seed)
    n = N_RESOLVED + N_UNRESOLVED

    # Label vector for resolved rows, exact counts, shuffled deterministically.
    y_resolved = np.zeros(N_RESOLVED, dtype=int)
    y_resolved[:N_POSITIVE] = 1
    rng.shuffle(y_resolved)

    statuses = np.empty(n, dtype=object)
    for i, label in enumerate(y_resolved):
        if label == 1:
            # Mix both positive statuses so both set members are exercised.
            statuses[i] = "Default" if i % 7 == 0 else "Charged Off"
        else:
            statuses[i] = "Fully Paid"
    for i in range(N_RESOLVED, n):
        statuses[i] = _UNRESOLVED_STATUSES[i % len(_UNRESOLVED_STATUSES)]

    # Latent risk: label signal + noise. Feature coefficients are kept small so no
    # single column approaches the 0.95 single-feature-AUC alarm.
    y_all = np.concatenate([y_resolved, np.zeros(N_UNRESOLVED, dtype=int)])
    z = 0.8 * y_all + rng.normal(size=n)

    df = pd.DataFrame(
        {
            "id": np.arange(1, n + 1),
            "loan_status": statuses,
            "emp_title": rng.choice(_EMP_TITLES, size=n),
            "zip_code": rng.choice(_ZIP_CODES, size=n),
            "annual_inc": rng.choice([30_000.0, 45_000.0, 60_000.0, 85_000.0, 120_000.0], size=n),
            "loan_amnt": np.round(rng.uniform(1_000, 35_000, size=n), -2),
            "int_rate": 12.0 + 3.0 * z + rng.normal(scale=2.0, size=n),
            "dti": 18.0 + 2.0 * z + rng.normal(scale=6.0, size=n),
            "fico_range_low": 690.0 - 15.0 * z + rng.normal(scale=25.0, size=n),
            "revol_util": np.clip(50.0 + 5.0 * z + rng.normal(scale=20.0, size=n), 0.0, 150.0),
            "open_acc": rng.integers(1, 30, size=n).astype(float),
            "installment": np.round(rng.uniform(30, 1200, size=n), 2),
        }
    )

    # Missingness where the real frame has it: the group-key sources.
    df.loc[rng.random(n) < 0.10, "emp_title"] = None
    df.loc[rng.random(n) < 0.05, "zip_code"] = None
    df.loc[rng.random(n) < 0.05, "annual_inc"] = None
    return df


def planted_leak_frame(seed: int) -> pd.DataFrame:
    """`clean_frame(seed)` plus the two planted leaks. Identical everywhere else."""
    df = clean_frame(seed)
    rng = np.random.default_rng(seed + 1)  # independent stream: the twin part stays identical
    y = df["loan_status"].isin({"Charged Off", "Default"}).astype(int).to_numpy()

    # (i) A LEAKAGE_COLUMNS member: recoveries accrue only on loans that went bad.
    df["recoveries"] = y * np.abs(rng.normal(scale=500.0, size=len(df)))
    # (ii) A near-copy of the label under a name no drop list knows.
    df["post_outcome_score"] = y + 0.01 * rng.random(len(df))
    return df
