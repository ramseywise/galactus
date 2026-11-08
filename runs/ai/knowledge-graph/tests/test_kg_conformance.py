"""The conformance record: what a build leaves in the shared experiments registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from kg_fakes import ScriptedProposer, ScriptedSeat
from test_kg_build import CAL, Env, good_proposer

from experiments.io import read_record
from experiments.record import NotApplicable
from kg.build import load_report
from kg.conformance import RUN_KIND, record_from_report, write_conformance


def test_record_carries_the_planned_fields(tmp_path: Path) -> None:
    e = Env(tmp_path)
    r = e.run(
        ScriptedProposer({"pages/normal.md": [CAL]}), ScriptedSeat(lambda c, w: ("supported", 0.9))
    )
    rec = read_record(write_conformance(r, e.records))
    assert rec.run_kind == RUN_KIND
    assert (rec.data.n_cols, rec.data.columns) == (1, ("body",))
    assert rec.data.n_rows == 3 and rec.data.frame_hash == r.profile_hash
    assert rec.headline_metric == "band_rate"
    for k in ("gate_pass_rate", "band_rate", "accepted_count", "not_run_count", "cost_usd"):
        assert k in rec.metrics
    assert isinstance(rec.execution.seed, NotApplicable)


def test_band_rate_not_applicable_is_never_written_as_zero(tmp_path: Path) -> None:
    e = Env(tmp_path)
    r = e.run(ScriptedProposer())
    rec = record_from_report(r)
    assert "band_rate" not in rec.metrics
    assert rec.headline_metric == "accepted_count"
    note = rec.execution.resolved_config["headline_note"]
    assert "band_rate not applicable" in str(note)


def test_report_sidecar_round_trips_not_applicable(tmp_path: Path) -> None:
    e = Env(tmp_path)
    r = e.run(ScriptedProposer())
    again = load_report(e.records, r.build_id)
    assert isinstance(again.band_rate, NotApplicable)
    assert again.render() == r.render()


def test_good_build_record_has_cost_metric(tmp_path: Path) -> None:
    e = Env(tmp_path)
    r = e.run(good_proposer())
    assert record_from_report(r).metrics["cost_usd"] == pytest.approx(0.0)
