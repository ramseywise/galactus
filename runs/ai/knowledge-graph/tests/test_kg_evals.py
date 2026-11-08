"""`evals/run.py` end to end, by subprocess.

`import evals` would resolve to marketing-comms' `evals` package (it is earlier on the
pytest pythonpath), so the script is run as a script, in a scrubbed environment: no
provider key, no KG_LIVE, and a cwd with no `.env` above it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

RUN = Path(__file__).resolve().parent.parent
SCRIPT = RUN / "evals" / "run.py"

# Every row of the spec's Measurement table, as the report's metric ids.
MEASUREMENT_TABLE = {
    "grounding_rate",
    "judge_precision_hard_negative",
    "review_band_rate_at_floor",
    "kappa",
    "ece",
    "not_run_pages_per_build",
    "cost_per_100_accepted",
    "retrieval_recall_at_5",
    "ask_p95_latency",
    "source_size_lines",
}


class MetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    seat: str
    threshold: str
    n: int | None
    value: float | None
    ci: list[float] | None
    status: str
    reason: str | None
    detail: str | None


class GoldModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    source: str
    rows: int
    by_label: dict[str, int]
    by_split: dict[str, int]


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    judge: str
    store: str
    gold: GoldModel
    split: str
    repeats: int
    n_scored: int
    confusion: dict[str, int]
    notes: list[str]
    metrics: list[MetricModel]


def run(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "VIRTUAL_ENV")}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**base, **env},
        cwd=Path("/"),
        timeout=120,
        check=False,
    )


def report(*args: str) -> dict[str, Any]:
    proc = run("--dry-run", "--json", *args)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_dry_run_json_validates_and_carries_every_measurement_row() -> None:
    rep = ReportModel.model_validate(report())
    assert rep.mode == "dry-run" and rep.judge == "scripted"
    assert {m.metric for m in rep.metrics} >= MEASUREMENT_TABLE
    for m in rep.metrics:
        assert m.seat == "scripted"
        if m.status == "measured":
            assert m.n is not None and m.value is not None
        else:
            assert m.status == "n/a" and m.value is None and m.reason


def test_empty_gold_falls_back_to_the_fixture_and_says_so() -> None:
    rep = report()
    assert rep["gold"]["source"] == "fixture-fallback"
    assert rep["gold"]["rows"] == 12
    assert rep["split"] == "test"  # calibration defaults to the test split
    assert rep["n_scored"] == 2
    text = run("--dry-run").stdout
    assert "fixture-fallback" in text and "real gold is empty" in text


def test_split_all_gives_every_row_a_verdict_and_populates_the_metrics() -> None:
    rep = ReportModel.model_validate(report("--split", "all"))
    assert rep.n_scored == 12
    by = {m.metric: m for m in rep.metrics}
    for key in (
        "tpr",
        "tnr",
        "kappa",
        "ece",
        "judge_precision_hard_negative",
        "hard_negative_tnr",
        "control_tnr",
        "test_retest_agreement",
    ):
        assert by[key].status == "measured" and by[key].n, key
    assert by["kappa"].ci is not None
    assert by["judge_precision_hard_negative"].n != by["tnr"].n  # a separate pool, own n


def test_not_applicable_prints_as_na_with_reason_never_zero() -> None:
    out = run("--dry-run").stdout  # test split of the fixture has no control row
    line = next(ln for ln in out.splitlines() if ln.startswith("control_tnr"))
    assert "n/a (no control rows" in line and "0.0000" not in line


def test_text_report_states_f3_and_f4() -> None:
    out = run("--dry-run").stdout
    assert "agreement is not precision" in out
    assert "hard-negative precision (reported separately" in out
    assert any(ln.strip().startswith("judge_precision_hard_negative") for ln in out.splitlines())


def test_dry_run_is_deterministic() -> None:
    assert run("--dry-run", "--json").stdout == run("--dry-run", "--json").stdout


def test_split_all_is_refused_outside_dry_run() -> None:
    proc = run("--judge", "claude", "--split", "all", KG_LIVE="1")
    assert proc.returncode != 0 and "--split all" in proc.stderr


def test_judge_claude_without_kg_live_refuses_with_the_plan_message() -> None:
    proc = run("--judge", "claude")
    assert proc.returncode != 0
    assert "live evaluation is a separate decision; see docs/spend-decision.md" in proc.stderr
    assert "set KG_LIVE=1" in proc.stderr
    assert proc.stdout == ""


def test_judge_claude_with_kg_live_but_no_key_refuses_naming_the_variable() -> None:
    proc = run("--judge", "claude", KG_LIVE="1")
    assert proc.returncode != 0 and "ANTHROPIC_API_KEY" in proc.stderr
    assert "unavailable" in proc.stderr


def test_judge_jev_without_its_key_refuses_naming_the_variable() -> None:
    proc = run("--dry-run", "--judge", "jev")
    assert proc.returncode != 0
    assert "OPENROUTER_API_KEY" in proc.stderr and "jev" in proc.stderr


def test_store_neo4j_refuses_by_name() -> None:
    proc = run("--dry-run", "--store", "neo4j")
    assert proc.returncode != 0
    assert "neo4j" in proc.stderr and "Phase B" in proc.stderr


def test_scripted_seat_refuses_without_dry_run() -> None:
    proc = run("--judge", "scripted")
    assert proc.returncode != 0 and "--dry-run" in proc.stderr


@pytest.mark.parametrize("flag", [["--judge", "claude"], ["--judge", "jev"]])
def test_refusals_happen_before_any_scoring(flag: list[str]) -> None:
    assert run(*flag).stdout == ""
