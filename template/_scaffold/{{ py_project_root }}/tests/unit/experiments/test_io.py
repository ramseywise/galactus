"""Step 4 — the record's on-disk format round-trips without collapsing states.

The claims under test: a written record reads back as the same frozen
dataclasses (not dicts, columns a tuple again); `NotApplicable` survives the
trip as a tagged object and never degrades to `null`; and loading re-runs the
schema's own validation, so a record tampered into an invalid state fails at
load rather than at comparison time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.io import SCHEMA_VERSION, SchemaVersionError, read_record, write_record
from experiments.record import (
    CodeState,
    DataIdentity,
    ExecutionConfig,
    NotApplicable,
    RunRecord,
)


def _classification_record() -> RunRecord:
    return RunRecord(
        code=CodeState(git_sha="deadbeef", dirty=True, versions={"numpy": "2.0.0"}),
        data=DataIdentity(
            frame_hash="abc123",
            n_rows=100,
            n_cols=3,
            columns=("a", "b", "c"),
            source_hash="feedface",
        ),
        execution=ExecutionConfig(
            seed=42,
            resolved_config={"model": "lgbm", "n_estimators": 200},
            folds="5-fold stratified",
        ),
        metrics={"average_precision": 0.75, "roc_auc": 0.9},
        headline_metric="average_precision",
        run_kind="classification",
    )


def _eval_record() -> RunRecord:
    return RunRecord(
        code=CodeState(
            git_sha=NotApplicable("not inside a git repository"),
            dirty=False,
            versions={},
        ),
        data=DataIdentity(frame_hash="def456", n_rows=50, n_cols=2, columns=("x", "y")),
        execution=ExecutionConfig(
            seed=NotApplicable("scripted adapter is deterministic without a seed"),
            resolved_config={},
            folds=NotApplicable("eval harness has no split concept"),
        ),
        metrics={"contract_pass_rate": 0.98},
        headline_metric="contract_pass_rate",
        run_kind="eval",
    )


def test_round_trip_reconstructs_equal_record(tmp_path: Path) -> None:
    record = _classification_record()
    loaded = read_record(write_record(record, tmp_path / "run.json"))
    assert loaded == record
    assert isinstance(loaded, RunRecord)
    assert isinstance(loaded.code, CodeState)
    assert isinstance(loaded.data.columns, tuple)


def test_not_applicable_round_trips_with_reason(tmp_path: Path) -> None:
    record = _eval_record()
    loaded = read_record(write_record(record, tmp_path / "run.json"))
    assert loaded == record
    assert isinstance(loaded.execution.seed, NotApplicable)
    assert loaded.execution.seed.reason == "scripted adapter is deterministic without a seed"
    assert isinstance(loaded.code.git_sha, NotApplicable)


def test_not_applicable_is_tagged_object_on_disk_never_null(tmp_path: Path) -> None:
    path = write_record(_eval_record(), tmp_path / "run.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["execution"]["seed"] == {
        "not_applicable": {"reason": "scripted adapter is deterministic without a seed"}
    }
    assert payload["execution"]["folds"] is not None
    assert payload["code"]["git_sha"] is not None


def test_default_source_hash_round_trips(tmp_path: Path) -> None:
    record = _eval_record()  # source_hash left to its NotApplicable default
    loaded = read_record(write_record(record, tmp_path / "run.json"))
    assert isinstance(loaded.data.source_hash, NotApplicable)
    assert loaded == record


def test_schema_version_mismatch_raises(tmp_path: Path) -> None:
    path = write_record(_classification_record(), tmp_path / "run.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = SCHEMA_VERSION + 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaVersionError, match="schema_version"):
        read_record(path)


def test_null_optional_field_raises(tmp_path: Path) -> None:
    path = write_record(_classification_record(), tmp_path / "run.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["execution"]["seed"] = None
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="null"):
        read_record(path)


def test_load_reruns_record_validation(tmp_path: Path) -> None:
    path = write_record(_classification_record(), tmp_path / "run.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["headline_metric"] = "brier"  # not present in metrics
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="headline_metric"):
        read_record(path)


def test_unserializable_config_raises_rather_than_stringifies(tmp_path: Path) -> None:
    record = RunRecord(
        code=CodeState(git_sha="deadbeef", dirty=False, versions={}),
        data=DataIdentity(frame_hash="abc", n_rows=1, n_cols=1, columns=("a",)),
        execution=ExecutionConfig(seed=0, resolved_config={"callback": object()}, folds="none"),
        metrics={"m": 1.0},
        headline_metric="m",
        run_kind="classification",
    )
    with pytest.raises(TypeError):
        write_record(record, tmp_path / "run.json")
