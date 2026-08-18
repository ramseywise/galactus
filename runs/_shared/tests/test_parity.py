"""Tests for the shared parity helpers — persist, toolkit_code_state, _tagged."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from experiments.io import read_record
from experiments.record import (
    CodeState,
    DataIdentity,
    ExecutionConfig,
    NotApplicable,
    RunRecord,
)
from runs._shared.parity import INDEX_ROOT, _tagged, persist, toolkit_code_state


def _sample_record() -> RunRecord:
    return RunRecord(
        code=CodeState(git_sha="a" * 40, dirty=False, versions={"python": "3.12.0"}),
        data=DataIdentity(
            frame_hash="b" * 64,
            n_rows=100,
            n_cols=5,
            columns=("a", "b", "c", "d", "target"),
        ),
        execution=ExecutionConfig(
            seed=42,
            resolved_config={"n_splits": 5},
            folds="kind=stratified n_splits=5 reason=default",
        ),
        metrics={"pr_auc": 0.85, "roc_auc": 0.90},
        headline_metric="pr_auc",
        run_kind="classification",
    )


class TestPersist:
    def test_dry_run_under_index_raises(self, tmp_path: Path) -> None:
        """A dry-run must never write under runs/_index/."""
        target = INDEX_ROOT / "test-record.json"
        with pytest.raises(ValueError, match="dry-run may not write"):
            persist(_sample_record(), dry_run=True, target=target)

    def test_dry_run_outside_index_succeeds(self, tmp_path: Path) -> None:
        target = tmp_path / "dry-run-record.json"
        result = persist(_sample_record(), dry_run=True, target=target)
        assert result.exists()

    def test_real_run_outside_index_succeeds(self, tmp_path: Path) -> None:
        target = tmp_path / "real-record.json"
        result = persist(_sample_record(), dry_run=False, target=target)
        assert result.exists()

    def test_round_trip(self, tmp_path: Path) -> None:
        """write → read must re-fire validation and produce an equal record."""
        record = _sample_record()
        path = persist(record, dry_run=False, target=tmp_path / "rt.json")
        loaded = read_record(path)
        assert loaded.metrics == record.metrics
        assert loaded.headline_metric == record.headline_metric
        assert loaded.data.frame_hash == record.data.frame_hash

    def test_hand_built_index_path_under_dry_run_raises(self, tmp_path: Path) -> None:
        """Even a caller constructing an index path by hand is caught."""
        target = INDEX_ROOT / "sneaky" / "record.json"
        with pytest.raises(ValueError, match="dry-run may not write"):
            persist(_sample_record(), dry_run=True, target=target)


class TestTagged:
    def test_plain_value_passes_through(self) -> None:
        assert _tagged("hello") == "hello"

    def test_not_applicable_becomes_tagged_dict(self) -> None:
        result = _tagged(NotApplicable("test reason"))
        assert isinstance(result, dict)
        assert "not_applicable" in result
        assert result["not_applicable"]["reason"] == "test reason"


class TestToolkitCodeState:
    def test_returns_root_and_sha(self) -> None:
        state = toolkit_code_state()
        assert state["root"] is not None
        assert state["git_sha"] is not None


class TestNamingContract:
    """Verify the naming convention from runs/_index/README.md."""

    def test_record_naming_format(self, tmp_path: Path) -> None:
        import re
        from datetime import datetime

        record = _sample_record()
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"{ts}-{record.data.frame_hash[:8]}.json"
        assert re.match(r"\d{8}T\d{6}Z-[0-9a-f]{8}\.json", name)

        target = tmp_path / name
        persist(record, dry_run=False, target=target)
        loaded = read_record(target)
        assert loaded.data.frame_hash == record.data.frame_hash
