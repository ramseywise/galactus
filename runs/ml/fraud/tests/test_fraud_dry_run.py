"""Dry-run tests — the full harness on a synthetic frame.

Two shapes exercise both guard branches:
- default (800/14): guard refuses, no threshold reported
- passing (2000/200): guard passes, threshold formatting exercised

Oracles key on the guard's contract (positives-per-fold vs floor), not on
frame-specific values — so these tests survive a frame swap unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))


def _toolkit_available() -> bool:
    try:
        import experiments.record  # noqa: F401
        import ml.workflows.classification  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


requires_toolkit = pytest.mark.skipif(
    not _toolkit_available(),
    reason="ml.workflows.classification or experiments.record not importable",
)


@requires_toolkit
class TestDryRunRefuse:
    """Default synthetic shape — guard refuses."""

    def test_dry_run_produces_summary(self, tmp_path):
        from run import SEED, build_synthetic_frame, main  # type: ignore[import]
        from sufficiency import MIN_POSITIVES_PER_FOLD, assess_sufficiency

        from ml.evaluation.splitting import make_splitter

        df = build_synthetic_frame()
        y = df["default"].to_numpy()
        plan = make_splitter(n_splits=5, random_state=SEED)
        verdict = assess_sufficiency(y, plan, min_per_fold=MIN_POSITIVES_PER_FOLD)
        assert not verdict.sufficient, "default synthetic shape should refuse"
        assert verdict.min_positives_in_fold < MIN_POSITIVES_PER_FOLD

    def test_refusal_names_the_floor(self):
        from run import SEED, build_synthetic_frame

        from ml.evaluation.splitting import make_splitter
        from sufficiency import MIN_POSITIVES_PER_FOLD, assess_sufficiency

        df = build_synthetic_frame()
        y = df["default"].to_numpy()
        plan = make_splitter(n_splits=5, random_state=SEED)
        verdict = assess_sufficiency(y, plan, min_per_fold=MIN_POSITIVES_PER_FOLD)
        assert str(MIN_POSITIVES_PER_FOLD) in verdict.reason


@requires_toolkit
class TestDryRunPass:
    """Passing synthetic shape — guard passes, threshold formatting exercised."""

    def test_passing_shape_is_sufficient(self):
        from run import (
            DRY_RUN_POSITIVES_PASS,
            DRY_RUN_ROWS_PASS,
            SEED,
            build_synthetic_frame,
        )

        from ml.evaluation.splitting import make_splitter
        from sufficiency import MIN_POSITIVES_PER_FOLD, assess_sufficiency

        df = build_synthetic_frame(
            n_rows=DRY_RUN_ROWS_PASS, n_positives=DRY_RUN_POSITIVES_PASS, seed=SEED
        )
        y = df["default"].to_numpy()
        plan = make_splitter(n_splits=5, random_state=SEED)
        verdict = assess_sufficiency(y, plan, min_per_fold=MIN_POSITIVES_PER_FOLD)
        assert verdict.sufficient, "passing shape should satisfy the guard"
        assert verdict.min_positives_in_fold >= MIN_POSITIVES_PER_FOLD


@requires_toolkit
class TestDryRunRecord:
    """Record assembly from a dry-run result."""

    def test_record_builds_and_round_trips(self, tmp_path):
        from fraud_record import assemble_fraud_record
        from run import IDENTIFIER_COLUMNS, SEED, TARGET, build_synthetic_frame

        from ml.evaluation.splitting import make_splitter
        from ml.workflows.classification import run_classification
        from sufficiency import MIN_POSITIVES_PER_FOLD, assess_sufficiency

        df = build_synthetic_frame()
        df_model = df.drop(columns=[c for c in IDENTIFIER_COLUMNS if c in df.columns])
        plan = make_splitter(n_splits=5, random_state=SEED)
        y = df_model[TARGET].to_numpy()
        verdict = assess_sufficiency(y, plan, min_per_fold=MIN_POSITIVES_PER_FOLD)

        result = run_classification(
            df_model,
            target=TARGET,
            output="binary",
            models=None,
            sampling="class_weight",
            splitter=plan,
            calibrate=True,
            cost_fp=None,
            cost_fn=None,
            seed=SEED,
        )

        record = assemble_fraud_record(
            result, df_model, seed=SEED, n_splits=5, verdict=verdict, dry_run=True
        )
        assert record.headline_metric in record.metrics
        assert record.run_kind == "classification"
        assert record.execution.seed == SEED

        # Round-trip through persist
        from runs._shared.parity import persist

        path = persist(record, dry_run=True, target=tmp_path / "test.json")
        from experiments.io import read_record

        loaded = read_record(path)
        assert loaded.metrics == record.metrics

    def test_dry_run_never_writes_index(self, tmp_path):
        from runs._shared.parity import INDEX_ROOT, persist

        from experiments.record import (
            CodeState,
            DataIdentity,
            ExecutionConfig,
            RunRecord,
        )

        record = RunRecord(
            code=CodeState(git_sha="a" * 40, dirty=False, versions={}),
            data=DataIdentity(
                frame_hash="b" * 64, n_rows=10, n_cols=3, columns=("a", "b", "c")
            ),
            execution=ExecutionConfig(
                seed=42, resolved_config={}, folds="test"
            ),
            metrics={"pr_auc": 0.5},
            headline_metric="pr_auc",
            run_kind="classification",
        )
        with pytest.raises(ValueError, match="dry-run may not write"):
            persist(record, dry_run=True, target=INDEX_ROOT / "bad.json")


@requires_toolkit
class TestReproducibility:
    """Two dry-runs at the same seed produce identical metrics."""

    def test_two_runs_same_metrics(self):
        from run import IDENTIFIER_COLUMNS, SEED, TARGET, build_synthetic_frame

        from ml.evaluation.splitting import make_splitter
        from ml.workflows.classification import run_classification

        metrics_list = []
        for _ in range(2):
            df = build_synthetic_frame(seed=SEED)
            df_model = df.drop(columns=[c for c in IDENTIFIER_COLUMNS if c in df.columns])
            plan = make_splitter(n_splits=5, random_state=SEED)
            result = run_classification(
                df_model,
                target=TARGET,
                output="binary",
                models=["logistic"],
                sampling="class_weight",
                splitter=plan,
                calibrate=True,
                cost_fp=None,
                cost_fn=None,
                seed=SEED,
            )
            m = {}
            for model in result.models:
                pr = getattr(model.metrics, "average_precision", None)
                if pr is not None:
                    m[model.name] = float(pr)
            metrics_list.append(m)

        assert metrics_list[0] == metrics_list[1], "two dry-runs at the same seed must produce identical metrics"
