"""Unsupervised clustering.

Clustering has no ground truth, which changes what a "run" can honestly claim.
There is no held-out score, so there is no cross-validation and no leakage in
the supervised sense — but there is a subtler trap: internal metrics like
silhouette measure *geometric* separation, not usefulness. A high silhouette on
a badly scaled frame means the clusters follow whichever column had the largest
units, which is why the transformer is not optional here.

`n_clusters` sweeping is deliberately not automated into a single "best k".
Silhouette peaks at k=2 on most real data, so an automatic argmax would return
"two clusters" almost always and hide the structure the analyst was looking for.
The sweep is reported; the choice stays with the reader.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone

from ml.evaluation.metrics import clustering_metrics
from ml.evaluation.splitting import RANDOM_STATE
from ml.selection.registry import get_models, get_spec
from ml.transform.columns import infer_column_types
from ml.transform.encoders import build_transformer
from ml.workflows.base import ModelResult, RunResult, _score, build_pipeline

logger = logging.getLogger(__name__)


def run_clustering(
    df: pd.DataFrame,
    *,
    models: list[str] | None = None,
    n_clusters: int = 3,
    seed: int = RANDOM_STATE,
    **overrides: Any,
) -> RunResult:
    """Fit and compare every available clustering model on `df`.

    `n_clusters` is passed to the algorithms that take it; DBSCAN ignores it and
    finds its own count, which is the reason it is worth running alongside.
    Models are ranked by silhouette.
    """
    plan = infer_column_types(df, target=None)
    features = list(plan.features)
    if not features:
        raise ValueError(
            "no usable feature columns were inferred — every column was classified "
            "as unused. Clustering needs at least one numeric or categorical column."
        )

    x = df[features]
    transformer = build_transformer(plan)

    specs = get_models(
        family="clustering",
        output="unsupervised",
        include=models,
        **overrides,
    )

    results: list[ModelResult] = []
    skipped: dict[str, str] = {}

    for name, estimator in specs.items():
        try:
            results.append(
                _fit_one(
                    name=name,
                    estimator=estimator,
                    transformer=transformer,
                    x=x,
                    n_clusters=n_clusters,
                )
            )
        except Exception as exc:
            logger.warning("model %s failed and was skipped: %s", name, exc)
            skipped[name] = f"{type(exc).__name__}: {exc}"

    results.sort(key=_score, reverse=True)

    return RunResult(
        family="clustering",
        output="unsupervised",
        target=None,
        models=results,
        column_plan=plan,
        split_plan=None,
        n_rows=len(df),
        n_features=len(features),
        seed=seed,
        skipped=skipped,
    )


def _fit_one(
    *, name: str, estimator: Any, transformer: Any, x: pd.DataFrame, n_clusters: int
) -> ModelResult:
    spec = get_spec(name)
    started = time.perf_counter()

    model = clone(estimator)
    # DBSCAN has no n_clusters — setting it blindly would raise, and catching that
    # would swallow real errors, so ask the estimator what it accepts.
    if "n_clusters" in model.get_params():
        model.set_params(n_clusters=n_clusters)
    elif "n_components" in model.get_params():  # GaussianMixture spells it differently
        model.set_params(n_components=n_clusters)

    pipeline = build_pipeline(clone(transformer), model)
    labels = _fit_labels(pipeline, x)

    # Metrics are computed in the *transformed* space, because that is the space
    # the algorithm partitioned. Silhouette over raw columns would measure
    # distances the model never saw.
    transformed = pipeline.named_steps["preprocess"].transform(x)
    transformed = np.asarray(
        transformed.todense() if hasattr(transformed, "todense") else transformed
    )
    metrics = clustering_metrics(transformed, labels)

    return ModelResult(
        name=name,
        estimator=pipeline,
        metrics=metrics,
        is_baseline=spec.is_baseline,
        fit_seconds=time.perf_counter() - started,
        notes=spec.notes,
    )


def _fit_labels(pipeline: Any, x: pd.DataFrame) -> np.ndarray:
    """Fit and return cluster assignments.

    `fit_predict` is the only interface DBSCAN and AgglomerativeClustering
    expose — they have no `predict`, because they cannot assign a new point
    without refitting. Pipeline forwards `fit_predict` to the final step.
    """
    return np.asarray(pipeline.fit_predict(x))
