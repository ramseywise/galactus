"""Class-imbalance strategies, as pipeline-safe components.

The invariant this module exists to enforce: **resampling happens inside the CV
fold, on training rows only.** Oversampling before the split copies minority rows
across the train/validation boundary, so the model is scored on rows it has
already memorised — a synthetic minority point and its neighbours land on
opposite sides. The resulting score is inflated by an amount nobody can estimate
after the fact, and the model degrades the moment it meets real data.

That rule is enforced at runtime, not documented and hoped for: `mark_validation`
stamps a frame, and any sampler handed a stamped frame raises
`SamplingLeakageError`.

`imbalanced-learn` is optional. Absent, the samplers degrade to class weights
with a logged warning rather than an ImportError — a stripped install still
trains, it just trains the way listen-wiseer already does.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any, Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RANDOM_STATE = 42

Strategy = Literal[
    "none",
    "class_weight",
    "smote",
    "smotenc",
    "under",
    "over",
    "smote_tomek",
]

_STRATEGIES: tuple[str, ...] = (
    "none",
    "class_weight",
    "smote",
    "smotenc",
    "under",
    "over",
    "smote_tomek",
)

_VALIDATION_FLAG = "_ml_split_role"
"""Attribute name stamped onto a frame by `mark_validation`. Lives in
`DataFrame.attrs`, which pandas propagates through slicing, so a marked frame
stays marked when a fold indexes into it."""


class SamplingLeakageError(RuntimeError):
    """Raised when a sampler is handed data marked as validation or test.

    Resampling validation rows is not a degraded result, it is an invalid one:
    the score it produces measures nothing. This is a hard failure rather than a
    warning for that reason.
    """


def mark_validation(df: pd.DataFrame, role: str = "validation") -> pd.DataFrame:
    """Stamp a frame as held-out so samplers refuse to touch it.

    Returns a shallow copy — marking is not a mutation of the caller's frame.
    """
    marked = df.copy(deep=False)
    marked.attrs = {**df.attrs, _VALIDATION_FLAG: role}
    return marked


def is_validation(df: Any) -> bool:
    """True if `df` carries a held-out marker from `mark_validation`."""
    attrs = getattr(df, "attrs", None)
    if not attrs:
        return False
    return attrs.get(_VALIDATION_FLAG) in {"validation", "test", "holdout"}


def _imblearn_available() -> bool:
    return importlib.util.find_spec("imblearn") is not None


def compute_class_weights(y) -> dict[Any, float]:
    """Balanced class weights: `n_samples / (n_classes * class_count)`.

    The fallback for every strategy when `imbalanced-learn` is absent, and the
    default strategy in its own right — it reweights the loss without inventing
    rows, which is the conservative choice on a 95/5 frame.
    """
    values = pd.Series(np.asarray(y))
    counts = values.value_counts()
    n_samples = len(values)
    n_classes = len(counts)
    return {label: n_samples / (n_classes * count) for label, count in counts.items()}


class ClassWeightSampler:
    """A no-op resampler that carries class weights instead of copying rows.

    Exposes the `fit_resample` interface so callers can treat every strategy
    uniformly, but returns the data untouched — the rebalancing happens in the
    estimator's loss via `class_weight_`, not in the sample.
    """

    def __init__(self):
        self.class_weight_: dict[Any, float] | None = None

    def fit_resample(self, x, y):
        _reject_validation(x, y)
        self.class_weight_ = compute_class_weights(y)
        return x, y


class PassthroughSampler:
    """`strategy="none"` — returns the data unchanged, with no weights.

    Present so that "do nothing about imbalance" is an explicit, selectable
    choice rather than the absence of one.
    """

    def fit_resample(self, x, y):
        _reject_validation(x, y)
        return x, y


def _reject_validation(x, y=None) -> None:
    for frame in (x, y):
        if is_validation(frame):
            raise SamplingLeakageError(
                "refusing to resample data marked as held-out. Resampling must "
                "happen inside the CV fold on training rows only — oversampling "
                "before the split leaks minority rows across the boundary and "
                "inflates the score. Fit on the training slice, then score the "
                "marked frame untouched."
            )


class _GuardedSampler:
    """Wraps an imbalanced-learn sampler with the held-out guard.

    Delegates everything else, so the wrapped object stays usable anywhere an
    imbalanced-learn sampler is expected.
    """

    def __init__(self, inner: Any):
        self.inner = inner

    def fit_resample(self, x, y):
        _reject_validation(x, y)
        return self.inner.fit_resample(x, y)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def __repr__(self) -> str:
        return f"_GuardedSampler({self.inner!r})"


def build_sampler(
    strategy: Strategy = "class_weight",
    *,
    categorical_indices: list[int] | None = None,
    random_state: int = RANDOM_STATE,
    **kwargs: Any,
) -> Any:
    """Return a sampler exposing `fit_resample(X, y)`.

    `class_weight` (the default) is listen-wiseer's proven choice: it reweights
    rather than synthesising, which is the safer starting point. Synthetic
    strategies are available when a baseline shows the minority class is being
    ignored outright.

    `smotenc` requires `categorical_indices` — SMOTE interpolates between
    neighbours, and interpolating a one-hot column produces a category that does
    not exist. SMOTENC takes the mode of the neighbourhood for those columns
    instead.

    Every returned sampler raises `SamplingLeakageError` when handed a frame
    marked by `mark_validation`.
    """
    if strategy not in _STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; valid: {list(_STRATEGIES)}")

    if strategy == "none":
        return PassthroughSampler()
    if strategy == "class_weight":
        return ClassWeightSampler()

    if strategy == "smotenc" and not categorical_indices:
        raise ValueError(
            "smotenc needs categorical_indices — it exists precisely to treat "
            "those columns as categorical rather than interpolating them. Use "
            "strategy='smote' for an all-numeric frame."
        )

    if not _imblearn_available():
        logger.warning(
            "imbalanced-learn is not installed; strategy %r degrades to class "
            "weights. Install it with `uv add imbalanced-learn` to enable "
            "synthetic and under/over sampling.",
            strategy,
        )
        return ClassWeightSampler()

    from imblearn.combine import SMOTETomek
    from imblearn.over_sampling import SMOTE, SMOTENC, RandomOverSampler
    from imblearn.under_sampling import RandomUnderSampler

    builders = {
        "smote": lambda: SMOTE(random_state=random_state, **kwargs),
        "smotenc": lambda: SMOTENC(
            categorical_features=categorical_indices, random_state=random_state, **kwargs
        ),
        "under": lambda: RandomUnderSampler(random_state=random_state, **kwargs),
        "over": lambda: RandomOverSampler(random_state=random_state, **kwargs),
        "smote_tomek": lambda: SMOTETomek(random_state=random_state, **kwargs),
    }
    return _GuardedSampler(builders[strategy]())


def resample_fold(x, y, strategy: Strategy = "class_weight", **kwargs: Any):
    """Resample one fold's training rows. Returns `(x_resampled, y_resampled, class_weight)`.

    `class_weight` is `None` for strategies that rebalance by resampling, and a
    dict for `class_weight` — pass it to the estimator's `class_weight` argument.
    """
    sampler = build_sampler(strategy, **kwargs)
    x_out, y_out = sampler.fit_resample(x, y)
    return x_out, y_out, getattr(sampler, "class_weight_", None)
