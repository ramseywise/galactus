from __future__ import annotations

import pytest
from sklearn.base import clone

from ml.selection.registry import (
    RANDOM_STATE,
    ModelSpec,
    ReservedModelError,
    get_models,
    get_spec,
    get_specs,
    valid_pairs,
)


def test_classification_binary_returns_baseline_and_candidates():
    models = get_models("classification", "binary")

    assert "logistic" in models, "the baseline must always be present"
    assert "random_forest" in models
    # catboost and lightgbm are declared in the ML dependency block, so they are
    # installed in the rendered tree — but skip rather than fail if a stripped
    # install is being tested.
    for optional in ("catboost", "lightgbm"):
        if get_spec(optional).available:
            assert optional in models


def test_unknown_pair_raises_and_lists_valid_pairs():
    with pytest.raises(KeyError) as excinfo:
        get_models("classification", "continuous")

    message = str(excinfo.value)
    assert "classification" in message
    assert "binary" in message, "the error must name the valid pairs"


def test_unknown_model_name_in_include_raises():
    with pytest.raises(KeyError) as excinfo:
        get_models("classification", "binary", include=["xgboost"])

    assert "xgboost" in str(excinfo.value)


def test_missing_optional_dep_is_skipped_not_fatal(monkeypatch, caplog):
    # Force catboost to look absent without uninstalling it.
    monkeypatch.setattr(ModelSpec, "available", property(lambda self: self.optional_dep is None))

    with caplog.at_level("WARNING"):
        models = get_models("classification", "binary")

    assert "catboost" not in models
    assert "lightgbm" not in models
    assert "logistic" in models, "baselines survive a missing optional dep"
    assert any("catboost" in record.getMessage() for record in caplog.records)


def test_every_available_spec_is_clonable():
    for family, output in valid_pairs():
        for name, estimator in get_models(family, output).items():
            cloned = clone(estimator)
            assert type(cloned) is type(estimator), f"{name} did not clone to the same type"


def test_reserved_bandit_raises_with_a_pointer():
    spec = get_spec("bandit")
    with pytest.raises(ReservedModelError) as excinfo:
        spec.build()

    assert "Finding 3" in str(excinfo.value), "the reservation must point at the reason"


def test_reserved_entry_does_not_break_a_whole_family_request():
    models = get_models("prediction", "continuous")

    assert "linear" in models
    assert "bandit" not in models, "reserved entries are skipped, not raised, in get_models"


def test_include_always_appends_baselines():
    models = get_models("classification", "binary", include=["random_forest"])

    assert set(models) == {"random_forest", "logistic"}


def test_all_three_families_are_registered():
    families = {family for family, _ in valid_pairs()}

    assert families == {"classification", "clustering", "prediction"}


def test_clustering_and_prediction_are_real_not_empty():
    assert set(get_models("clustering", "unsupervised")) >= {"kmeans", "dbscan", "gmm"}
    assert set(get_models("prediction", "continuous")) >= {"linear", "hierarchical"}


def test_overrides_reach_the_factory():
    models = get_models("clustering", "unsupervised", include=["kmeans"], n_clusters=3)

    assert models["kmeans"].n_clusters == 3


def test_specs_carry_the_metadata_the_workflows_read():
    catboost = get_spec("catboost")
    assert catboost.supports_categorical is True
    assert catboost.optional_dep == "catboost"
    assert get_spec("logistic").is_baseline is True


def test_get_specs_returns_unavailable_specs_too():
    names = {s.name for s in get_specs("classification", "binary")}

    assert names == {"logistic", "random_forest", "catboost", "lightgbm"}


def test_seeded_estimators_are_deterministic():
    first = get_models("classification", "binary", include=["random_forest"])["random_forest"]
    second = get_models("classification", "binary", include=["random_forest"])["random_forest"]

    assert first.random_state == second.random_state == RANDOM_STATE
