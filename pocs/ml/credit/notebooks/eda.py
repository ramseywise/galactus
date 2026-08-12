"""Credit default — EDA functions the notebook calls.

The notebook is the *narrative*: a markdown cell states what a step is for, a code
cell calls one function here, and the output appears under it. The analysis itself
lives in this module, where it is diffable, importable, and testable — a notebook
that carries its own logic can only be reviewed by re-running it.

Nothing here reimplements `ml/` at the repo root. `column_plan` wraps
`ml.transform.columns.infer_column_types` rather than re-deriving dtypes, so the
notebook's view of what each column *is* matches what the pipeline will actually do
with it in `src/run.py`. A second, drifting inference is how a notebook comes to
disagree with the model it is supposed to be describing.

Structure is bivariate-first — every function that takes a target compares a feature
*against* it rather than cataloguing columns in isolation. That is the ordering that
makes an hour of looking productive: you are hunting for signal, not producing a
data dictionary.

Import from a notebook in `notebooks/`:

    import sys; sys.path.insert(0, "../src")
    import eda
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure

# Same sys.path dance as `run.py`, and load-bearing for the same reason: `pocs/ml/`
# has no __init__.py, so it is a *namespace* package named `ml` that satisfies
# `import ml` while containing none of the real modules. Prepending the repo root
# without removing this directory's parent gets a ModuleNotFoundError on
# `ml.transform` that reads like a missing dependency.
_ROOT = Path(__file__).resolve().parents[4]
if not (_ROOT / "ml" / "__init__.py").exists():
    raise RuntimeError(f"expected the vendored ml/ package at {_ROOT}/ml — not found")
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.transform.columns import ColumnPlan, infer_column_types  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "credit_default.csv"
SEP = ";"
TARGET = "default"
ID_COLS = ["uuid"]

# Above this, a categorical has too many levels to read as a bar chart; the levels
# get listed instead. Distinct from `ml`'s one-hot threshold (50), which answers a
# different question — this one is about what a human can see on an axis.
PLOT_CARDINALITY_LIMIT = 20

# |corr| above this between two features means redundancy: keep the more
# interpretable member of the pair rather than both.
REDUNDANT_CORR = 0.85

# Below this many positives per fold, cross-validated metrics carry fold-to-fold
# variance larger than any model difference you are likely to see.
MIN_POSITIVES_PER_FOLD = 10


def set_plot_theme() -> None:
    """Notebook display defaults. Called once at the top of the notebook."""
    pd.set_option("display.max_columns", 200)
    sns.set_theme(style="whitegrid")


# --- Loading ----------------------------------------------------------------


def load(path: Path = DATA, sep: str = SEP, target: str = TARGET) -> pd.DataFrame:
    """Read the frame and drop unlabelled rows.

    Rows with a missing target are dropped, not imputed. An unlabelled row is not a
    training example, and filling the label invents outcomes.

    Identifier columns are kept here (unlike `run.py`, which drops them) — the EDA
    may need `uuid` to answer whether subjects recur, which is the open gate-1b
    question. They are excluded from the feature list by `features()` instead.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — it is gitignored (*.csv). Restore it with:\n"
            "  cp ~/workspace/lebanese-blonde/src/data/dataset.csv "
            "pocs/ml/credit/data/credit_default.csv"
        )

    df = pd.read_csv(path, sep=sep)
    raw_rows = len(df)
    labelled = df[~df[target].isna()].copy()
    dropped = raw_rows - len(labelled)

    print(f"raw:       {raw_rows} rows x {df.shape[1]} cols")
    print(f"labelled:  {len(labelled)} rows ({dropped} unlabelled row(s) dropped)")
    return labelled


def features(df: pd.DataFrame, target: str = TARGET, drop: list[str] | None = None) -> list[str]:
    """Column names that are candidate features — everything but the target and IDs."""
    excluded = {target, *(drop if drop is not None else ID_COLS)}
    return [c for c in df.columns if c not in excluded]


# --- Target balance ---------------------------------------------------------


@dataclass(frozen=True)
class TargetBalance:
    """The first number that changes the modelling plan."""

    counts: pd.Series
    positives: int
    n_rows: int
    rate: float
    per_fold: dict[int, float]

    @property
    def is_severely_imbalanced(self) -> bool:
        return self.rate < 0.05


def target_balance(
    df: pd.DataFrame, target: str = TARGET, folds: tuple[int, ...] = (5, 10)
) -> TargetBalance:
    """Class counts, positive rate, and positives-per-fold at each CV setting.

    Severe imbalance decides the metric (PR-AUC, not ROC-AUC), the sampling
    strategy, and whether a threshold can be chosen at all. Positives-per-fold
    decides whether any cross-validated number means anything — read it before
    trusting a metric below.
    """
    balance = TargetBalance(
        counts=df[target].value_counts(dropna=False),
        positives=int(df[target].sum()),
        n_rows=len(df),
        rate=float(df[target].mean()),
        per_fold={k: float(df[target].sum()) / k for k in folds},
    )

    print(balance.counts.to_string())
    print(f"\npositive rate: {balance.rate:.2%}  ({balance.positives} positives)")
    for k, n in balance.per_fold.items():
        print(f"{k}-fold → ~{n:.1f} positives per fold")

    thin = [k for k, n in balance.per_fold.items() if n < MIN_POSITIVES_PER_FOLD]
    if thin:
        print(
            f"\nFEW POSITIVES PER FOLD at n_splits={thin}. Cross-validated scores carry "
            "fold-to-fold variance far larger than any model difference you are likely "
            "to see. Report the spread, not just the mean."
        )
    return balance


# --- Leakage ----------------------------------------------------------------


def leak_scan(df: pd.DataFrame, target: str = TARGET, top: int = 15) -> pd.Series:
    """Rank numeric columns by |correlation| with the target.

    The highest-value step in the notebook, and the one most often skipped. A leaked
    feature does not raise an error: it returns a great score and reads as success.

    A high correlation here is a leak *candidate*, not a win. For each one at the top
    of this list, ask: **was this value knowable at the moment the prediction would be
    made?** Anything recorded *because* the outcome happened is leakage, however
    predictive it looks.
    """
    numeric_all = df.select_dtypes(include=np.number).columns.drop(target, errors="ignore")
    ranked = (
        df[numeric_all]
        .corrwith(df[target])
        .abs()
        .sort_values(ascending=False)
        .head(top)
        .rename("abs_corr_with_target")
    )
    print(ranked.round(3).to_string())
    print("\nHigh correlation here is a leak candidate, not a win. Inspect by hand.")
    return ranked


# --- Missingness ------------------------------------------------------------


def missingness(df: pd.DataFrame, top: int = 25) -> pd.Series:
    """Per-column missing rate (%), descending, non-zero only.

    Per-column rates decide impute-vs-drop.
    """
    miss = (df.isna().mean() * 100).sort_values(ascending=False)
    present = miss[miss > 0]
    print(f"{len(present)} of {df.shape[1]} columns have missing values\n")
    print(present.round(1).head(top).to_string())
    return present


def plot_missingness_pattern(df: pd.DataFrame, threshold: float = 20.0) -> Figure | None:
    """Heatmap of whether high-missing columns go missing *together*.

    Co-occurrence decides whether missingness is itself a signal: columns that go
    missing together usually mean a whole record type is absent, and an indicator
    captures that where a fill value destroys it.

    Returns None when fewer than two columns clear the threshold — there is no
    pattern to plot, which is itself the answer.
    """
    miss = df.isna().mean() * 100
    high = miss[miss > threshold].index.tolist()
    if len(high) < 2:
        print(f"fewer than two columns above {threshold:.0f}% missing — no pattern to plot")
        return None

    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(df[high].isna().corr(), cmap="mako", center=0, ax=ax)
    ax.set_title(f"Missingness co-occurrence (>{threshold:.0f}% missing)")
    fig.tight_layout()
    plt.show()
    return fig


# --- Feature types ----------------------------------------------------------


def column_plan(
    df: pd.DataFrame, target: str = TARGET, drop: list[str] | None = None
) -> ColumnPlan:
    """Infer what each column *is*, using the same code the pipeline uses.

    This wraps `ml.transform.columns.infer_column_types` deliberately: the notebook's
    view of the columns and `run.py`'s view come from one implementation, so they
    cannot drift apart.

    Identifier columns are dropped before inference, matching `run.py`. A subject key
    is a near-perfect predictor of its own rows, and left in it lands in
    `high_cardinality` where it pollutes every categorical listing downstream.

    Inference is a **starting point, corrected by hand**. An ID read as int64 becomes
    a numeric feature silently, and a 0–4 status code read as a float becomes a
    magnitude when it is really a rank. That correction is the notebook's job — it
    lands in the `ORDINAL` list at the handoff.
    """
    ids = [c for c in (drop if drop is not None else ID_COLS) if c in df.columns]
    plan = infer_column_types(df.drop(columns=ids), target=target)
    if ids:
        print(f"identifier columns excluded before inference: {ids}\n")

    print(f"numeric          ({len(plan.numeric)}): {list(plan.numeric)}")
    print(f"\ncategorical      ({len(plan.categorical)}): {list(plan.categorical)}")
    print(f"\nhigh-cardinality ({len(plan.high_cardinality)}): {list(plan.high_cardinality)}")
    print(f"\nboolean          ({len(plan.boolean)}): {list(plan.boolean)}")
    print(f"\ndatetime         ({len(plan.datetime)}): {list(plan.datetime)}")
    print(f"\nunused           ({len(plan.unused)}): {list(plan.unused)}")
    if plan.unused:
        print("  ^ constant or all-null — dropped as a recorded decision, with reasons:")
        for col in plan.unused:
            print(f"    {col}: {plan.reasons.get(col, '—')}")
    return plan


def cardinality(df: pd.DataFrame, plan: ColumnPlan) -> pd.Series:
    """Distinct-value counts for categorical columns, descending.

    Cardinality decides the encoder: low → one-hot, high → target encoding or
    rare-level collapsing.
    """
    cols = [*plan.categorical, *plan.high_cardinality]
    if not cols:
        print("no categorical columns")
        return pd.Series(dtype="int64")
    card = df[cols].nunique().sort_values(ascending=False)
    print(card.to_string())
    return card


# --- Bivariate: categorical vs target ---------------------------------------


def plot_categorical_vs_target(
    df: pd.DataFrame,
    plan: ColumnPlan,
    target: str = TARGET,
    max_levels: int = PLOT_CARDINALITY_LIMIT,
) -> Figure | None:
    """Default rate by level, per categorical feature, against the base rate.

    Rate-by-level is more readable than two overlaid histograms when the classes are
    this imbalanced — at a ~1.75% positive rate the default group is invisible on a
    shared count axis. The dashed line is the base rate: a level whose bar sits far
    from it is where the signal is.
    """
    to_plot = [c for c in plan.categorical if df[c].nunique() <= max_levels]
    if not to_plot:
        print(f"no categoricals with <= {max_levels} levels to plot")
        return None

    rate = float(df[target].mean())
    fig, axes = plt.subplots(len(to_plot), 1, figsize=(11, 3.2 * len(to_plot)), squeeze=False)
    for col, ax in zip(to_plot, axes.flatten(), strict=False):
        share = df.groupby(col, dropna=False)[target].mean().sort_values(ascending=False) * 100
        share.plot(kind="barh", ax=ax, color="#4c72b0")
        ax.axvline(rate * 100, color="crimson", ls="--", lw=1, label=f"base rate {rate:.1%}")
        ax.set_xlabel("default rate (%)")
        ax.set_title(f"{col} — default rate by level")
        ax.legend(loc="lower right")
    fig.tight_layout()
    plt.show()
    return fig


def high_cardinality_levels(
    df: pd.DataFrame, plan: ColumnPlan, top: int = 10, max_levels: int = PLOT_CARDINALITY_LIMIT
) -> None:
    """List the common levels of columns too wide to plot."""
    wide = [c for c in [*plan.categorical, *plan.high_cardinality] if df[c].nunique() > max_levels]
    if not wide:
        print(f"no categoricals above {max_levels} levels")
        return
    for col in wide:
        print(f"\n--- {col}: {df[col].nunique()} levels, top {top}")
        print(df[col].value_counts().head(top).to_string())


# --- Univariate + bivariate: numeric ----------------------------------------


def _grid(n: int, ncols: int, height: float) -> tuple[Figure, np.ndarray]:
    """Subplot grid sized to `n` panels, with the trailing empties hidden."""
    nrows = max(1, int(np.ceil(n / ncols)))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, height * nrows), squeeze=False)
    flat = axes.flatten()
    for ax in flat[n:]:
        ax.set_visible(False)
    return fig, flat


def numeric_features(plan: ColumnPlan, exclude: list[str] | None = None) -> list[str]:
    """Numeric columns minus anything ruled out (leaks, redundant pairs)."""
    ruled_out = set(exclude or [])
    return [c for c in plan.numeric if c not in ruled_out]


def plot_numeric_distributions(df: pd.DataFrame, cols: list[str], ncols: int = 5) -> Figure | None:
    """Histogram per numeric feature. Skew and outliers decide scaling."""
    if not cols:
        print("no numeric columns to plot")
        return None
    fig, axes = _grid(len(cols), ncols, height=2.8)
    for col, ax in zip(cols, axes, strict=False):
        sns.histplot(df[col].dropna(), ax=ax, bins=30, color="#4c72b0")
        ax.set_title(col, fontsize=9)
        ax.set_xlabel("")
    fig.tight_layout()
    plt.show()
    return fig


def skewness(df: pd.DataFrame, cols: list[str], top: int = 15) -> pd.Series:
    """Most-skewed features. |skew| > 2 usually wants a log or rank transform."""
    skew = df[cols].skew(numeric_only=True).abs().sort_values(ascending=False)
    print("most skewed features (|skew| > 2 usually wants a log/rank transform):")
    print(skew.head(top).round(2).to_string())
    return skew


def plot_numeric_vs_target(
    df: pd.DataFrame, cols: list[str], target: str = TARGET, ncols: int = 5
) -> Figure | None:
    """Violin plot per numeric feature, split by target class.

    With few positives the positive-side violin is thin — read it as indicative,
    not conclusive.
    """
    if not cols:
        print("no numeric columns to plot")
        return None
    fig, axes = _grid(len(cols), ncols, height=3.0)
    for col, ax in zip(cols, axes, strict=False):
        sns.violinplot(x=target, y=col, data=df, ax=ax, hue=target, legend=False, palette="Set3")
        ax.set_title(col, fontsize=9)
        ax.set_xlabel("")
        ax.set_ylabel("")
    fig.tight_layout()
    plt.show()
    return fig


# --- Feature correlation ----------------------------------------------------


def plot_correlation(df: pd.DataFrame, cols: list[str]) -> Figure | None:
    """Feature-vs-feature correlation heatmap.

    Clusters mean redundancy: keep the most interpretable member of each cluster
    rather than all of them.
    """
    if len(cols) < 2:
        print("need at least two numeric columns to correlate")
        return None
    fig, ax = plt.subplots(figsize=(14, 12))
    sns.heatmap(
        df[cols].corr(), cmap="RdBu_r", center=0, square=True, ax=ax, cbar_kws={"shrink": 0.6}
    )
    ax.set_title("Feature correlation")
    fig.tight_layout()
    plt.show()
    return fig


def redundant_pairs(
    df: pd.DataFrame, cols: list[str], threshold: float = REDUNDANT_CORR, top: int = 25
) -> pd.DataFrame:
    """Name the redundant feature pairs instead of eyeballing the heatmap."""
    if len(cols) < 2:
        print("need at least two numeric columns to correlate")
        return pd.DataFrame(columns=["level_0", "level_1", "corr"])

    corr = df[cols].corr()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    pairs = (
        upper.stack()
        .rename("corr")
        .reset_index()
        .query(f"abs(corr) > {threshold}")
        .sort_values("corr", key=abs, ascending=False)
    )
    print(f"{len(pairs)} feature pairs correlated above |{threshold}|:")
    if len(pairs):
        print(pairs.head(top).to_string(index=False))
    return pairs


# --- Handoff ----------------------------------------------------------------


def reconcile(
    all_features: list[str],
    categorical: list[str],
    numeric: list[str],
    ordinal: list[str],
    excluded: dict[str, str],
) -> set[str]:
    """Check that every feature got a decision, and name the ones that did not.

    A column that appears in none of these lists is silently dropped at training
    time. This turns that silence into a printed list. On a fresh run the
    unaccounted count equals the feature total — that is the gate working, not a bug.
    """
    claimed = set(categorical) | set(numeric) | set(ordinal) | set(excluded)
    unaccounted = set(all_features) - claimed

    print(f"features total:  {len(all_features)}")
    print(f"categorical:     {len(categorical)}")
    print(f"numeric:         {len(numeric)}")
    print(f"ordinal:         {len(ordinal)}")
    print(f"excluded:        {len(excluded)}")
    print(f"\nUNACCOUNTED ({len(unaccounted)}): {sorted(unaccounted)}")
    if unaccounted:
        print("\n^ these would be dropped without a decision. Assign each one.")

    overclaimed = claimed - set(all_features)
    if overclaimed:
        print(f"\nNOT IN THE FRAME ({len(overclaimed)}): {sorted(overclaimed)}")
        print("^ named in a list above but not a column — typo or stale name.")
    return unaccounted
