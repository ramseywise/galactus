"""Step 1 — the record schema's enforced not-applicable sentinels.

The claim under test: a `RunRecord` cannot silently carry a headline metric
it does not have, and an optional field cannot silently carry a bare `None`
where a `NotApplicable(reason=...)` was required. Both are the concrete
failure mode (WALKTHROUGH's brier/getattr bug) this schema exists to close.
"""

from __future__ import annotations

import pytest

from experiments.record import (
    CodeState,
    DataIdentity,
    ExecutionConfig,
    NotApplicable,
    RunRecord,
)


def _code_state() -> CodeState:
    return CodeState(git_sha="deadbeef", dirty=False, versions={"numpy": "2.0.0"})


def _data_identity() -> DataIdentity:
    return DataIdentity(
        frame_hash="abc123", n_rows=100, n_cols=5, columns=("a", "b", "c", "d", "e")
    )


def test_headline_metric_absent_from_metrics_raises() -> None:
    with pytest.raises(ValueError, match="headline_metric"):
        RunRecord(
            code=_code_state(),
            data=_data_identity(),
            execution=ExecutionConfig(seed=42, resolved_config={}, folds="5-fold stratified"),
            metrics={"accuracy": 0.9},
            headline_metric="average_precision",
            run_kind="classification",
        )


def test_headline_metric_present_constructs_cleanly() -> None:
    record = RunRecord(
        code=_code_state(),
        data=_data_identity(),
        execution=ExecutionConfig(seed=42, resolved_config={}, folds="5-fold stratified"),
        metrics={"accuracy": 0.9, "average_precision": 0.75},
        headline_metric="average_precision",
        run_kind="classification",
    )
    assert record.headline_metric == "average_precision"
    assert record.metrics["average_precision"] == 0.75


def test_seed_not_applicable_constructs_cleanly() -> None:
    config = ExecutionConfig(
        seed=NotApplicable("scripted adapter is deterministic without a seed"),
        resolved_config={},
        folds=NotApplicable("eval harness has no split concept"),
    )
    assert isinstance(config.seed, NotApplicable)
    assert isinstance(config.folds, NotApplicable)


def test_seed_none_raises() -> None:
    with pytest.raises(ValueError, match="seed"):
        ExecutionConfig(seed=None, resolved_config={}, folds="5-fold stratified")


def test_folds_none_raises() -> None:
    with pytest.raises(ValueError, match="folds"):
        ExecutionConfig(seed=42, resolved_config={}, folds=None)
