"""Config — the knobs that used to be module constants.

The point of this stage is swappability: every value here was previously a
literal in source, so the tests that matter are the ones proving an env var
actually overrides and that the derived helpers agree with the settings they
read from.
"""

from __future__ import annotations

from pathlib import Path

from ml.config import MLSettings


def test_defaults_match_the_constants_they_replaced():
    """These numbers were `RANDOM_STATE = 42`, `BASELINE_TOLERANCE = 0.01`, and
    `DEFAULT_ISOTONIC_MIN_SAMPLES = 1000` in three separate modules. Changing a
    default here is a behaviour change for every consumer, so it is pinned."""
    settings = MLSettings()

    assert settings.random_seed == 42
    assert settings.baseline_tolerance == 0.01
    assert settings.isotonic_min_samples == 1000
    assert settings.n_splits == 5


def test_env_overrides_a_setting(monkeypatch):
    monkeypatch.setenv("ML_RANDOM_SEED", "7")
    monkeypatch.setenv("ML_N_SPLITS", "10")

    settings = MLSettings()

    assert settings.random_seed == 7
    assert settings.n_splits == 10


def test_cost_ratio_is_env_overridable(monkeypatch):
    """Costs are a business input and change per engagement — hardcoding them is
    what made threshold choice un-reviewable."""
    monkeypatch.setenv("ML_COST_FN", "5.0")

    settings = MLSettings()

    assert settings.cost_fn == 5.0
    assert settings.cost_fp == 1.0


def test_version_dir_combines_artifact_dir_and_version(monkeypatch):
    monkeypatch.setenv("ML_ARTIFACT_DIR", "data/models")
    monkeypatch.setenv("ML_MODEL_VERSION", "v3")

    settings = MLSettings()

    assert settings.version_dir == Path("data/models/v3")


def test_auto_calibration_picks_by_sample_size():
    """Isotonic needs data; below the floor it overfits the reliability curve."""
    settings = MLSettings()

    assert settings.resolve_calibration(10_000) == "isotonic"
    assert settings.resolve_calibration(100) == "sigmoid"


def test_an_explicit_calibration_method_is_not_overridden(monkeypatch):
    monkeypatch.setenv("ML_CALIBRATION_METHOD", "sigmoid")

    settings = MLSettings()

    assert settings.resolve_calibration(10_000) == "sigmoid", (
        "an explicit choice must win over the sample-size heuristic"
    )


def test_unknown_env_vars_are_ignored(monkeypatch):
    """`extra="ignore"`: an unrelated ML_-prefixed var in a shared .env must not
    crash a run."""
    monkeypatch.setenv("ML_SOMETHING_UNRELATED", "x")

    assert MLSettings().random_seed == 42
