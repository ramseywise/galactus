"""Record-assembly tests — a dry-run result becomes a validated in-memory `RunRecord`.

Toolkit-coupled (imports `experiments.*` and `run.py`): skips with the reason naming
`ML_PACKAGE_ROOT` when the toolkit is absent, same posture as `test_dry_run.py`.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest
from test_dry_run import TOOLKIT_SKIP_REASON, _load_run_module, _toolkit_available

_POC = Path(__file__).resolve().parents[1]

requires_toolkit = pytest.mark.skipif(not _toolkit_available(), reason=TOOLKIT_SKIP_REASON)


def _dry_run_args() -> argparse.Namespace:
    return argparse.Namespace(
        data=_POC / "data" / "never-read.csv",
        report=None,
        n_splits=5,
        dry_run=True,
        models=None,
        summary_json=None,
    )


@pytest.fixture(scope="module")
def dry_run_record(tmp_path_factory):
    """One dry run, one record — shared across the assertions below."""
    if not _toolkit_available():  # pragma: no cover - guarded by requires_toolkit
        pytest.skip(TOOLKIT_SKIP_REASON)
    import synthetic
    from frame import GROUP_COL, SEED, prepare_frame
    from run_record import assemble_run_record

    run_mod = _load_run_module()
    df = prepare_frame(synthetic.clean_frame(SEED))
    _, result = run_mod.run_pipeline(
        df,
        n_splits=5,
        models=run_mod.DRY_RUN_MODELS,
        report_path=tmp_path_factory.mktemp("record") / "report.html",
        summary_json=None,
    )
    return assemble_run_record(result, df.drop(columns=[GROUP_COL]), _dry_run_args())


@requires_toolkit
def test_record_builds_and_headline_is_in_metrics(dry_run_record):
    # `__post_init__` already enforced this at construction; assert it anyway so a
    # future relaxation of the registry contract fails here, not silently.
    assert dry_run_record.headline_metric in dry_run_record.metrics
    assert dry_run_record.headline_metric == "logistic_pr_auc"
    assert dry_run_record.run_kind == "classification"


def _is_real_sha(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


@requires_toolkit
def test_code_state_carries_a_real_sha(dry_run_record):
    assert _is_real_sha(dry_run_record.code.git_sha)


@requires_toolkit
def test_resolved_config_carries_the_toolkit_state(dry_run_record):
    from experiments.record import NotApplicable

    toolkit = dry_run_record.execution.resolved_config["toolkit"]
    assert toolkit["root"], "the toolkit root must be recorded when ML_PACKAGE_ROOT is set"
    # A rendered tree inside a git repo records its SHA; a tree outside version control
    # records a reasoned NotApplicable. Either is a recordable answer; None never is.
    assert _is_real_sha(toolkit["git_sha"]) or isinstance(toolkit["git_sha"], NotApplicable)
    assert toolkit["git_sha"] is not None


@requires_toolkit
def test_seed_and_folds_are_concrete_for_classification(dry_run_record):
    """Key Decision 2: NotApplicable in seed/folds is a bug for this run kind."""
    from frame import SEED

    assert dry_run_record.execution.seed == SEED
    folds = dry_run_record.execution.folds
    assert isinstance(folds, str) and "n_splits=5" in folds
    # A plan description, never indices: nothing in it should look like a row list.
    assert "[" not in folds.split("reason=")[0]


@requires_toolkit
def test_metrics_are_flat_floats_with_prevalence_floor(dry_run_record):
    import synthetic

    assert dry_run_record.metrics["prevalence_floor"] == pytest.approx(
        synthetic.SYNTHETIC_PREVALENCE
    )
    assert all(isinstance(v, float) for v in dry_run_record.metrics.values())


@requires_toolkit
def test_bare_none_seed_still_raises():
    """Regression pin on the registry contract (F2): if AIT ever relaxes the
    `__post_init__` rejection, this run's record loses its validation for free —
    fail here, loudly."""
    from experiments.record import ExecutionConfig

    with pytest.raises(ValueError, match="seed=None"):
        ExecutionConfig(seed=None, resolved_config={}, folds="kind=grouped n_splits=5")


@requires_toolkit
def test_frame_hash_covers_the_fitted_frame_not_the_source(dry_run_record):
    """Two different fitted frames must not share a hash; the same frame must."""
    from experiments.fingerprint import fingerprint_frame

    import synthetic
    from frame import GROUP_COL, SEED, prepare_frame

    fitted = prepare_frame(synthetic.clean_frame(SEED)).drop(columns=[GROUP_COL])
    assert fingerprint_frame(fitted).frame_hash == dry_run_record.data.frame_hash
    other = prepare_frame(synthetic.clean_frame(SEED + 1)).drop(columns=[GROUP_COL])
    assert fingerprint_frame(other).frame_hash != dry_run_record.data.frame_hash
