"""Step 9a — save/load round-trip and the schema guard.

The guard tests dominate this file by design. A round-trip that reproduces
predictions is table stakes; the reason `persistence.py` exists at all is that
loading a model against a drifted schema must *raise* rather than return
plausible numbers. Every rejection path therefore has its own test.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression

from ml.persistence import (
    METADATA_SUFFIX,
    ModelMetadata,
    SchemaMismatchError,
    assert_schema,
    build_metadata,
    current_versions,
    describe,
    load_model,
    metadata_path,
    predict_with,
    save_model,
)
from ml.selection.registry import RANDOM_STATE
from ml.workflows import run_classification


@pytest.fixture(scope="module")
def cancer_frame() -> pd.DataFrame:
    frame = load_breast_cancer(as_frame=True).frame.copy()
    return frame.rename(columns={"target": "malignant"})


@pytest.fixture(scope="module")
def fitted(cancer_frame: pd.DataFrame):
    result = run_classification(
        cancer_frame,
        target="malignant",
        models=["logistic"],
        cost_fp=1.0,
        cost_fn=5.0,
        seed=RANDOM_STATE,
    )
    return result, result.best


# --------------------------------------------------------------------------- #
# The Done-when: round-trip reproduces identical predictions.
# --------------------------------------------------------------------------- #


def test_round_trip_reproduces_identical_predictions(fitted, cancer_frame, tmp_path):
    result, model = fitted
    metadata = build_metadata(result)
    path = save_model(model.estimator, tmp_path / "model.joblib", metadata=metadata)

    features = cancer_frame[list(metadata.feature_names)]
    before = model.estimator.predict(features)
    before_proba = model.estimator.predict_proba(features)

    loaded, loaded_meta = load_model(path)
    np.testing.assert_array_equal(loaded.predict(features), before)
    np.testing.assert_allclose(loaded.predict_proba(features), before_proba)
    assert loaded_meta.feature_names == metadata.feature_names


def test_metadata_survives_the_round_trip(fitted, tmp_path):
    result, model = fitted
    metadata = build_metadata(result, notes="phase B smoke")
    path = save_model(model.estimator, tmp_path / "m.joblib", metadata=metadata)
    _, loaded = load_model(path)

    assert loaded.model_name == "logistic"
    assert loaded.target == "malignant"
    assert loaded.seed == RANDOM_STATE
    assert loaded.notes == "phase B smoke"
    assert loaded.threshold == pytest.approx(metadata.threshold)
    assert loaded.versions["python"]
    assert "average_precision" in loaded.metrics


def test_sidecar_is_written_next_to_the_model(fitted, tmp_path):
    result, model = fitted
    path = save_model(model.estimator, tmp_path / "m.joblib", metadata=build_metadata(result))
    sidecar = metadata_path(path)
    assert sidecar.exists()
    assert sidecar.name == "m" + METADATA_SUFFIX
    assert json.loads(sidecar.read_text())["schema_version"] == 1


def test_save_creates_missing_parent_directories(fitted, tmp_path):
    result, model = fitted
    path = save_model(
        model.estimator, tmp_path / "a" / "b" / "m.joblib", metadata=build_metadata(result)
    )
    assert path.exists()


# --------------------------------------------------------------------------- #
# The Done-when: renamed / missing columns raise SchemaMismatchError.
# --------------------------------------------------------------------------- #


def test_missing_column_raises(fitted, cancer_frame, tmp_path):
    result, model = fitted
    metadata = build_metadata(result)
    save_model(model.estimator, tmp_path / "m.joblib", metadata=metadata)

    broken = cancer_frame.drop(columns=[metadata.feature_names[0]])
    with pytest.raises(SchemaMismatchError, match="missing 1 training feature"):
        assert_schema(broken, metadata)


def test_renamed_column_raises_and_says_so(fitted, cancer_frame):
    result, _ = fitted
    metadata = build_metadata(result)
    original = metadata.feature_names[0]
    renamed = cancer_frame.rename(columns={original: "mean_radius_v2"})

    with pytest.raises(SchemaMismatchError) as exc:
        assert_schema(renamed, metadata)
    assert original in str(exc.value)
    assert "mean_radius_v2" in str(exc.value), "the hint should point at the likely rename"


def test_extra_columns_are_allowed(fitted, cancer_frame):
    """Production frames carry ids and timestamps; rejecting those makes the check unusable."""
    result, _ = fitted
    metadata = build_metadata(result)
    wider = cancer_frame.copy()
    wider["record_id"] = range(len(wider))
    wider["ingested_at"] = pd.Timestamp("2026-01-01")
    assert_schema(wider, metadata)  # must not raise


def test_column_order_is_ignored_by_default_and_checked_on_request(fitted, cancer_frame):
    result, _ = fitted
    metadata = build_metadata(result)
    shuffled = cancer_frame[list(reversed(cancer_frame.columns))]

    assert_schema(shuffled, metadata)  # ColumnTransformer selects by name

    with pytest.raises(SchemaMismatchError, match="column order"):
        assert_schema(shuffled, metadata, strict_order=True)


def test_loading_without_a_sidecar_raises(fitted, tmp_path):
    result, model = fitted
    path = save_model(model.estimator, tmp_path / "m.joblib", metadata=build_metadata(result))
    metadata_path(path).unlink()

    with pytest.raises(SchemaMismatchError, match="no metadata sidecar"):
        load_model(path)


def test_loading_a_missing_model_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_model(tmp_path / "nope.joblib")


def test_saving_a_bare_estimator_is_refused(tmp_path):
    """A bare estimator loads without its preprocessing and scores raw columns silently."""
    estimator = LogisticRegression().fit([[0.0], [1.0]], [0, 1])
    with pytest.raises(TypeError, match="expected a fitted Pipeline"):
        save_model(estimator, tmp_path / "m.joblib", metadata=ModelMetadata(feature_names=["a"]))


def test_saving_without_feature_names_is_refused(fitted, tmp_path):
    _, model = fitted
    with pytest.raises(ValueError, match="feature_names is empty"):
        save_model(model.estimator, tmp_path / "m.joblib", metadata=ModelMetadata(feature_names=[]))


def test_build_metadata_refuses_a_run_with_no_models(fitted):
    result, _ = fitted
    saved = result.models
    result.models = []
    try:
        with pytest.raises(ValueError, match="no fitted models"):
            build_metadata(result)
    finally:
        result.models = saved


# --------------------------------------------------------------------------- #
# The safe inference path
# --------------------------------------------------------------------------- #


def test_predict_with_applies_the_saved_threshold(fitted, cancer_frame, tmp_path):
    """The cost analysis that chose the threshold must survive serialisation."""
    result, model = fitted
    metadata = build_metadata(result)
    assert metadata.threshold is not None and metadata.threshold != 0.5

    path = save_model(model.estimator, tmp_path / "m.joblib", metadata=metadata)
    loaded, loaded_meta = load_model(path)

    features = cancer_frame[list(metadata.feature_names)]
    expected = (loaded.predict_proba(features)[:, 1] >= metadata.threshold).astype(int)
    np.testing.assert_array_equal(predict_with(loaded, cancer_frame, loaded_meta), expected)


def test_predict_with_falls_back_to_argmax_without_a_threshold(fitted, cancer_frame):
    result, model = fitted
    metadata = build_metadata(result)
    metadata.threshold = None
    features = cancer_frame[list(metadata.feature_names)]
    np.testing.assert_array_equal(
        predict_with(model.estimator, cancer_frame, metadata),
        model.estimator.predict(features),
    )


def test_predict_with_checks_the_schema_before_scoring(fitted, cancer_frame):
    result, model = fitted
    metadata = build_metadata(result)
    broken = cancer_frame.drop(columns=[metadata.feature_names[2]])
    with pytest.raises(SchemaMismatchError):
        predict_with(model.estimator, broken, metadata)


def test_predict_with_returns_probabilities_on_request(fitted, cancer_frame):
    result, model = fitted
    metadata = build_metadata(result)
    proba = predict_with(model.estimator, cancer_frame, metadata, proba=True)
    assert proba.shape == (len(cancer_frame), 2)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)


def test_predict_with_ignores_extra_columns(fitted, cancer_frame):
    result, model = fitted
    metadata = build_metadata(result)
    wider = cancer_frame.copy()
    wider["record_id"] = range(len(wider))
    np.testing.assert_array_equal(
        predict_with(model.estimator, wider, metadata),
        predict_with(model.estimator, cancer_frame, metadata),
    )


# --------------------------------------------------------------------------- #
# Metadata plumbing
# --------------------------------------------------------------------------- #


def test_metadata_json_drops_unknown_keys_rather_than_raising():
    """A sidecar from a newer version must still load into an older one."""
    payload = json.dumps({"feature_names": ["a", "b"], "future_field": 1})
    meta = ModelMetadata.from_json(payload)
    assert meta.feature_names == ["a", "b"]


def test_current_versions_records_the_libraries_that_matter():
    versions = current_versions()
    assert "python" in versions
    assert "sklearn" in versions


def test_describe_is_human_readable(fitted):
    result, _ = fitted
    lines = "\n".join(describe(build_metadata(result)))
    assert "logistic" in lines
    assert "threshold" in lines
    assert "features: " in lines
