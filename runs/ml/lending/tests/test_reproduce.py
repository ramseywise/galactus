"""Reproduce + persistence tests — the Evaluation table's reproduce check.

Toolkit-coupled (needs `experiments.io`): same skip posture as `test_dry_run.py`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_dry_run import TOOLKIT_SKIP_REASON, _load_run_module, _toolkit_available

_POC = Path(__file__).resolve().parents[1]

requires_toolkit = pytest.mark.skipif(not _toolkit_available(), reason=TOOLKIT_SKIP_REASON)


def _execute_dry_run(tmp_dir: Path):
    """One full dry-run path at the run's own seed; returns the assembled record."""
    import argparse

    import synthetic
    from frame import GROUP_COL, SEED, prepare_frame
    from run_record import assemble_run_record

    run_mod = _load_run_module()
    df = prepare_frame(synthetic.clean_frame(SEED))
    _, result = run_mod.run_pipeline(
        df,
        n_splits=5,
        models=run_mod.DRY_RUN_MODELS,
        report_path=tmp_dir / "report.html",
        summary_json=None,
    )
    args = argparse.Namespace(
        data=None, report=None, n_splits=5, dry_run=True, models=None, summary_json=None
    )
    return assemble_run_record(result, df.drop(columns=[GROUP_COL]), args)


@requires_toolkit
def test_double_execution_metrics_byte_identical(tmp_path):
    """Same seed, same frame → the two `metrics` blocks serialize to identical bytes."""
    first = _execute_dry_run(tmp_path / "a")
    second = _execute_dry_run(tmp_path / "b")
    as_bytes = [json.dumps(r.metrics, sort_keys=True).encode("utf-8") for r in (first, second)]
    assert as_bytes[0] == as_bytes[1]
    assert first.data.frame_hash == second.data.frame_hash


@requires_toolkit
def test_record_round_trips_and_revalidates(tmp_path):
    """`read_record(write_record(...))` reconstructs the frozen dataclasses — every
    `__post_init__` fires again on load — and compares equal to what was saved."""
    from experiments.io import read_record, write_record

    record = _execute_dry_run(tmp_path)
    loaded = read_record(write_record(record, tmp_path / "record.json"))
    assert loaded == record
    assert isinstance(loaded.data.columns, tuple)


@requires_toolkit
def test_tampered_record_fails_at_load(tmp_path):
    """A record edited into an invalid state fails on read, not downstream."""
    from experiments.io import SchemaVersionError, read_record, write_record

    record = _execute_dry_run(tmp_path)
    path = write_record(record, tmp_path / "record.json")

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["headline_metric"] = "a_metric_nobody_computed"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="a_metric_nobody_computed"):
        read_record(path)

    payload["headline_metric"] = record.headline_metric
    payload["schema_version"] = 999
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaVersionError):
        read_record(path)


@requires_toolkit
def test_real_run_targets_the_index_dry_run_never_does(tmp_path):
    """The destination rule, asserted without executing a real run (which is
    documented in the READMEs, not run in tests — it needs the real CSV)."""
    run_mod = _load_run_module()
    now = datetime(2026, 8, 16, 10, 45, 12, tzinfo=UTC)

    real = run_mod.record_destination(
        dry_run=False, frame_hash="abcdef0123456789", now=now, report_path=tmp_path / "r.html"
    )
    assert real == run_mod.INDEX_ROOT / "20260816T104512Z-abcdef01.json"
    assert real.parent.name == "_index" and real.parent.parent.name == "runs"

    dry = run_mod.record_destination(
        dry_run=True, frame_hash="abcdef0123456789", now=now, report_path=tmp_path / "r.html"
    )
    assert dry.parent == tmp_path
    assert not str(dry).startswith(str(run_mod.INDEX_ROOT))
