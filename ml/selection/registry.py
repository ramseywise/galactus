"""Model registry — the 2-D selection matrix keyed by (family, output).

Every candidate model is a `ModelSpec` whose `factory` returns an *unfitted*
estimator with all parameters set in the constructor, so `sklearn.clone` works
and the same spec can be refit on every CV fold independently.

The two ideas this generalises, both proven in production code:

- an estimator factory per model name, params in the constructor
  (listen-wiseer `recommend/modules/classifiers.py`), and
- a comparison harness that fits every candidate on identical folds
  (listen-wiseer `recommend/train.py`).

Registering all three families up front — even where only one entry is real —
keeps the family dimension honest: `get_models("prediction", "continuous")`
returns something, and the reserved entries fail with a pointer rather than a
`KeyError` that reads like a typo.

Optional dependencies (catboost, lightgbm) are declared per spec via
`optional_dep` and skipped cleanly when the package is absent — the comparison
still runs, one model shorter, with a logged warning. Baselines are never
optional: logistic regression and linear regression are the explainability
floor, and a run without one has nothing to be "better than".
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

Family = Literal["classification", "clustering", "prediction"]

RANDOM_STATE = 42


@dataclass(frozen=True)
class ModelSpec:
    """One registry entry: how to build an unfitted estimator, plus the metadata
    the workflows and the report need in order to describe it."""

    name: str
    family: Family
    outputs: tuple[str, ...]
    factory: Callable[..., Any]
    supports_categorical: bool = False
    """CatBoost handles raw categorical columns natively — the transform layer
    can skip one-hot encoding for these."""
    is_baseline: bool = False
    """Logistic/linear — always included in a comparison, never filtered out by
    an `include` list, and never skipped for a missing optional dep."""
    optional_dep: str | None = None
    """Import name of the package this spec needs; None means always available."""
    notes: str = ""

    @property
    def available(self) -> bool:
        """True when the spec's optional dependency is importable (or it has none).

        Uses `importlib.util.find_spec` rather than a try/except import so that
        checking availability never pays the cost of importing a heavy package
        we may not end up using.
        """
        if self.optional_dep is None:
            return True
        try:
            return importlib.util.find_spec(self.optional_dep) is not None
        except (ImportError, ValueError):
            return False

    def build(self, **overrides: Any) -> Any:
        """Instantiate the estimator. Raises the underlying ImportError if the
        optional dependency is missing — callers that want the skip-quietly
        behaviour should go through `get_models`."""
        return self.factory(**overrides)


class ReservedModelError(NotImplementedError):
    """Raised by a registered-but-unimplemented spec, with a pointer to why."""


# ── factories ────────────────────────────────────────────────────────────────
# Each returns an unfitted estimator. Kept as module-level functions rather than
# lambdas so the optional imports stay lazy and the tracebacks name something.


def _logistic(**kw: Any) -> Any:
    from sklearn.linear_model import LogisticRegression

    params: dict[str, Any] = {"max_iter": 2000, "random_state": RANDOM_STATE}
    params.update(kw)
    return LogisticRegression(**params)


def _random_forest_clf(**kw: Any) -> Any:
    from sklearn.ensemble import RandomForestClassifier

    params: dict[str, Any] = {"n_estimators": 200, "random_state": RANDOM_STATE}
    params.update(kw)
    return RandomForestClassifier(**params)


def _catboost_clf(**kw: Any) -> Any:
    from catboost import CatBoostClassifier

    params: dict[str, Any] = {
        "iterations": 200,
        "depth": 6,
        "random_seed": RANDOM_STATE,
        "verbose": False,
        "allow_writing_files": False,
    }
    params.update(kw)
    return CatBoostClassifier(**params)


def _lightgbm_clf(**kw: Any) -> Any:
    from lightgbm import LGBMClassifier

    params: dict[str, Any] = {"random_state": RANDOM_STATE, "verbosity": -1}
    params.update(kw)
    return LGBMClassifier(**params)


def _kmeans(**kw: Any) -> Any:
    from sklearn.cluster import KMeans

    params: dict[str, Any] = {"n_clusters": 8, "random_state": RANDOM_STATE, "n_init": 10}
    params.update(kw)
    return KMeans(**params)


def _dbscan(**kw: Any) -> Any:
    from sklearn.cluster import DBSCAN

    params: dict[str, Any] = {"eps": 0.5, "min_samples": 5}
    params.update(kw)
    return DBSCAN(**params)


def _gmm(**kw: Any) -> Any:
    from sklearn.mixture import GaussianMixture

    params: dict[str, Any] = {"n_components": 8, "random_state": RANDOM_STATE}
    params.update(kw)
    return GaussianMixture(**params)


def _agglomerative(**kw: Any) -> Any:
    from sklearn.cluster import AgglomerativeClustering

    params: dict[str, Any] = {"n_clusters": 8}
    params.update(kw)
    return AgglomerativeClustering(**params)


def _linear_reg(**kw: Any) -> Any:
    from sklearn.linear_model import LinearRegression

    return LinearRegression(**kw)


def _hierarchical_reg(**kw: Any) -> Any:
    """Ridge with an L2 prior — the shrinkage-toward-the-mean shape of a
    hierarchical/partial-pooling model, without a Bayesian dependency. Named
    `hierarchical` because that is the modelling intent it stands in for."""
    from sklearn.linear_model import Ridge

    params: dict[str, Any] = {"alpha": 1.0, "random_state": RANDOM_STATE}
    params.update(kw)
    return Ridge(**params)


def _lightgbm_reg(**kw: Any) -> Any:
    from lightgbm import LGBMRegressor

    params: dict[str, Any] = {"random_state": RANDOM_STATE, "verbosity": -1}
    params.update(kw)
    return LGBMRegressor(**params)


def _bandit_reserved(**_kw: Any) -> Any:
    raise ReservedModelError(
        "The contextual bandit is registered but not implemented. It allocates "
        "actions, not predictions, and only becomes tractable once a calibrated "
        "propensity score exists and outcomes are logged — reaching for it first "
        "solves the policy problem before the prediction problem. See research "
        "Finding 3 in the ML capability parity plan. Prior art: atlas "
        "src/agents/learner/rl_interface.py."
    )


# ── the matrix ───────────────────────────────────────────────────────────────

_SPECS: tuple[ModelSpec, ...] = (
    # classification — the deep family
    ModelSpec(
        name="logistic",
        family="classification",
        outputs=("binary", "multiclass"),
        factory=_logistic,
        is_baseline=True,
        notes="Explainability floor. If boosting cannot beat it meaningfully, "
        "that is a finding about feature quality, not a failed run.",
    ),
    ModelSpec(
        name="random_forest",
        family="classification",
        outputs=("binary", "multiclass"),
        factory=_random_forest_clf,
    ),
    ModelSpec(
        name="catboost",
        family="classification",
        outputs=("binary", "multiclass"),
        factory=_catboost_clf,
        supports_categorical=True,
        optional_dep="catboost",
        notes="Native categorical handling and ordered boosting — strongest on "
        "mixed-type, categorical-heavy tabular data.",
    ),
    ModelSpec(
        name="lightgbm",
        family="classification",
        outputs=("binary", "multiclass"),
        factory=_lightgbm_clf,
        optional_dep="lightgbm",
    ),
    # clustering
    ModelSpec(
        name="kmeans",
        family="clustering",
        outputs=("unsupervised",),
        factory=_kmeans,
        is_baseline=True,
    ),
    ModelSpec(
        name="dbscan",
        family="clustering",
        outputs=("unsupervised",),
        factory=_dbscan,
        notes="Density-based — finds non-spherical clusters and labels noise -1. "
        "Has no predict() for new points.",
    ),
    ModelSpec(
        name="gmm",
        family="clustering",
        outputs=("unsupervised",),
        factory=_gmm,
        notes="Soft assignment — gives per-cluster probabilities.",
    ),
    ModelSpec(
        name="agglomerative",
        family="clustering",
        outputs=("unsupervised",),
        factory=_agglomerative,
    ),
    # prediction (regression)
    ModelSpec(
        name="linear",
        family="prediction",
        outputs=("continuous",),
        factory=_linear_reg,
        is_baseline=True,
    ),
    ModelSpec(
        name="hierarchical",
        family="prediction",
        outputs=("continuous",),
        factory=_hierarchical_reg,
        notes="Ridge as a partial-pooling stand-in.",
    ),
    ModelSpec(
        name="lightgbm_reg",
        family="prediction",
        outputs=("continuous",),
        factory=_lightgbm_reg,
        optional_dep="lightgbm",
    ),
    ModelSpec(
        name="bandit",
        family="prediction",
        outputs=("continuous",),
        factory=_bandit_reserved,
        notes="Reserved — raises ReservedModelError.",
    ),
)


@dataclass(frozen=True)
class _Registry:
    specs: tuple[ModelSpec, ...] = field(default=_SPECS)

    def pairs(self) -> list[tuple[str, str]]:
        """Every valid (family, output) pair, in registration order."""
        seen: list[tuple[str, str]] = []
        for spec in self.specs:
            for output in spec.outputs:
                pair = (spec.family, output)
                if pair not in seen:
                    seen.append(pair)
        return seen


REGISTRY = _Registry()


def valid_pairs() -> list[tuple[str, str]]:
    """Every (family, output) pair the registry can serve."""
    return REGISTRY.pairs()


def get_specs(family: str, output: str) -> list[ModelSpec]:
    """Specs registered for a family/output pair, available or not.

    Raises `KeyError` naming every valid pair when the requested one is unknown —
    a typo in `output` is otherwise indistinguishable from an empty family.
    """
    matches = [s for s in REGISTRY.specs if s.family == family and output in s.outputs]
    if not matches:
        raise KeyError(
            f"No models registered for (family={family!r}, output={output!r}). "
            f"Valid pairs: {valid_pairs()}"
        )
    return matches


def get_models(
    family: str,
    output: str,
    include: list[str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Return unfitted estimators for a family/output pair, keyed by model name.

    `include` filters to the named models; baselines are appended regardless, so
    a comparison always has a floor to beat. Specs whose optional dependency is
    missing are skipped with a warning rather than raising — one fewer candidate
    is a degraded run, not a broken one.

    `overrides` are passed to every factory (e.g. `n_clusters=4`); each factory
    merges them over its defaults.
    """
    specs = get_specs(family, output)

    if include is not None:
        requested = set(include)
        unknown = requested - {s.name for s in specs}
        if unknown:
            raise KeyError(
                f"Unknown model(s) {sorted(unknown)} for "
                f"(family={family!r}, output={output!r}). "
                f"Available: {sorted(s.name for s in specs)}"
            )
        specs = [s for s in specs if s.name in requested or s.is_baseline]

    models: dict[str, Any] = {}
    for spec in specs:
        if not spec.available:
            logger.warning(
                "skipping model %r — optional dependency %r is not installed",
                spec.name,
                spec.optional_dep,
            )
            continue
        try:
            models[spec.name] = spec.build(**overrides)
        except ReservedModelError:
            # Reserved entries are registered so the family dimension is honest,
            # but they must not break a run that asked for the whole family.
            logger.info("skipping reserved model %r — not implemented", spec.name)
            continue
    return models


def get_spec(name: str) -> ModelSpec:
    """Look a spec up by name. Raises `KeyError` listing every registered name."""
    for spec in REGISTRY.specs:
        if spec.name == name:
            return spec
    raise KeyError(f"Unknown model {name!r}. Registered: {sorted(s.name for s in REGISTRY.specs)}")
