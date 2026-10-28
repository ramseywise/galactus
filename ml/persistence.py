"""Saving a fitted pipeline so that loading it is safe.

A bare `joblib.dump` of an estimator is a loaded gun. It records the weights and
nothing about the world the weights were fitted in — not the feature names, not
their order, not the library versions, not the threshold the decision was
calibrated to. Six months later someone loads it, passes a frame whose columns
drifted by one rename, and gets predictions that are wrong in a way that never
raises. Train/serve skew is the most expensive ML bug precisely because it is
silent.

So every save writes a metadata sidecar, and every load checks it. The check
raises. A pipeline that cannot verify the frame it is being handed is a pipeline
that should refuse to score it.
"""

from __future__ import annotations

import json
import platform
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

METADATA_SUFFIX = ".metadata.json"
SCHEMA_VERSION = 1


class SchemaMismatchError(ValueError):
    """The frame handed to a loaded model does not match the frame it was fitted on.

    Raised loudly and early rather than letting the pipeline produce numbers.
    A missing column, a renamed column, or a reordered column all mean the
    weights are being applied to the wrong thing.
    """


@dataclass
class ModelMetadata:
    """Everything needed to know whether a loaded model can be trusted on new data."""

    feature_names: list[str]
    target: str | None = None
    family: str = ""
    output: str = ""
    model_name: str = ""
    seed: int = 42
    threshold: float | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    class_labels: list[str] = field(default_factory=list)
    trained_at: str = ""
    versions: dict[str, str] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, default=str)

    @classmethod
    def from_json(cls, text: str) -> ModelMetadata:
        data = json.loads(text)
        known = set(cls.__dataclass_fields__)
        # Unknown keys are dropped rather than raising: a sidecar written by a
        # newer version should still load into an older one, minus the new field.
        return cls(**{k: v for k, v in data.items() if k in known})


def current_versions() -> dict[str, str]:
    """Library versions at save time — the first thing to check when a load misbehaves."""
    versions = {"python": platform.python_version()}
    for module in ("sklearn", "numpy", "pandas", "joblib"):
        try:
            versions[module] = __import__(module).__version__
        except Exception:
            continue
    return versions


def build_metadata(
    result: Any,
    model: Any = None,
    *,
    notes: str = "",
) -> ModelMetadata:
    """Derive metadata from a `RunResult` — the ordinary path, so nobody hand-writes it.

    Defaults to the best model. Feature names come from the column plan, which is
    the frame's contract, not from the fitted transformer's expanded output.
    """
    model = model or result.best
    if model is None:
        raise ValueError("cannot build metadata from a run with no fitted models.")

    metrics: dict[str, float] = {}
    for key in ("average_precision", "roc_auc", "brier", "f1", "rmse", "r2", "silhouette"):
        value = getattr(model.metrics, key, None)
        if isinstance(value, (int, float)):
            metrics[key] = float(value)

    return ModelMetadata(
        feature_names=list(result.column_plan.features),
        target=result.target,
        family=result.family,
        output=result.output,
        model_name=model.name,
        seed=result.seed,
        threshold=model.threshold.threshold if model.threshold is not None else None,
        metrics=metrics,
        class_labels=[str(c) for c in result.class_balance],
        trained_at=datetime.now(UTC).isoformat(timespec="seconds"),
        versions=current_versions(),
        notes=notes,
    )


def metadata_path(path: Path | str) -> Path:
    """The sidecar path for a model file. `model.joblib` → `model.metadata.json`."""
    path = Path(path)
    return path.with_suffix("").with_name(path.stem + METADATA_SUFFIX)


def save_model(pipeline: Pipeline, path: Path | str, *, metadata: ModelMetadata) -> Path:
    """Write the pipeline and its metadata sidecar. Returns the model path.

    Rejects a non-Pipeline. A bare estimator saved here would be loaded without
    its preprocessing, and the first prediction would silently be made on raw,
    unscaled, unencoded columns.
    """
    if not isinstance(pipeline, Pipeline):
        raise TypeError(
            f"expected a fitted Pipeline, got {type(pipeline).__name__}. Saving a bare "
            "estimator loses the preprocessing, and inference would then run on raw "
            "columns without ever raising."
        )
    if not metadata.feature_names:
        raise ValueError(
            "metadata.feature_names is empty — without it, load_model cannot detect "
            "train/serve skew, which is the reason the sidecar exists."
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)
    metadata_path(path).write_text(metadata.to_json(), encoding="utf-8")
    return path


def load_model(path: Path | str) -> tuple[Pipeline, ModelMetadata]:
    """Load a pipeline and its metadata. Raises if the sidecar is missing."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no model at {path}")

    sidecar = metadata_path(path)
    if not sidecar.exists():
        raise SchemaMismatchError(
            f"model at {path} has no metadata sidecar at {sidecar}. Without it there is "
            "no way to check the incoming frame against the training schema, so the "
            "model cannot be loaded safely."
        )

    pipeline = joblib.load(path)
    metadata = ModelMetadata.from_json(sidecar.read_text(encoding="utf-8"))
    return pipeline, metadata


def assert_schema(df: pd.DataFrame, metadata: ModelMetadata, *, strict_order: bool = False) -> None:
    """Raise `SchemaMismatchError` unless `df` can be scored by this model.

    Extra columns are allowed — a production frame routinely carries ids and
    timestamps the model does not use, and rejecting those would make the check
    so annoying that someone would turn it off. Missing columns are not: they
    mean a feature the model weights is absent, and there is no honest way to
    score that.

    Column *order* is checked only under `strict_order`, because a
    `ColumnTransformer` selects by name. Positional pipelines are the exception,
    and the exception should opt in.
    """
    expected = list(metadata.feature_names)
    present = list(df.columns)

    missing = [c for c in expected if c not in present]
    if missing:
        renamed = [c for c in present if c not in expected]
        hint = f" Frame has unexpected column(s) {renamed[:5]} — a rename?" if renamed else ""
        raise SchemaMismatchError(
            f"frame is missing {len(missing)} training feature(s): {missing[:10]}.{hint}"
        )

    if strict_order:
        actual = [c for c in present if c in expected]
        if actual != expected:
            raise SchemaMismatchError(
                "column order differs from training order and strict_order=True: "
                f"expected {expected[:5]}..., got {actual[:5]}..."
            )


def predict_with(
    pipeline: Pipeline,
    df: pd.DataFrame,
    metadata: ModelMetadata,
    *,
    proba: bool = False,
    strict_order: bool = False,
) -> Any:
    """Score `df` after checking it against `metadata`. The safe inference path.

    When the metadata carries a threshold, `proba=False` applies it rather than
    falling back to 0.5 — otherwise the cost analysis that chose the threshold is
    quietly discarded at exactly the moment it matters.
    """
    assert_schema(df, metadata, strict_order=strict_order)
    features = df[list(metadata.feature_names)]

    if proba:
        return pipeline.predict_proba(features)

    if metadata.threshold is not None and hasattr(pipeline, "predict_proba"):
        scores = pipeline.predict_proba(features)[:, 1]
        return (scores >= metadata.threshold).astype(int)

    return pipeline.predict(features)


def describe(metadata: ModelMetadata) -> Sequence[str]:
    """Human-readable lines for a log or a report footer."""
    lines = [
        f"model: {metadata.model_name} ({metadata.family}/{metadata.output})",
        f"trained: {metadata.trained_at or 'unknown'} · seed {metadata.seed}",
        f"features: {len(metadata.feature_names)}",
    ]
    if metadata.threshold is not None:
        lines.append(f"threshold: {metadata.threshold:.4g}")
    if metadata.metrics:
        lines.append(
            "metrics: " + ", ".join(f"{k}={v:.4g}" for k, v in sorted(metadata.metrics.items()))
        )
    return lines
