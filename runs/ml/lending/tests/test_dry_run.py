"""Dry-run tests — the full harness path on the synthetic twins.

Toolkit-coupled: these tests import `run.py`, whose module scope imports `ml.*`, so the
whole file skips with a reason naming `ML_PACKAGE_ROOT` when the toolkit is absent
(plan Open Question 4's posture — a skip that reads as green is the hazard, so the
reason is explicit).

`run.py` is loaded by explicit file path under a private module name: the bare name
`run` belongs to fraud's tests in this suite (see `conftest.py`), and importing it here
would shadow theirs or vice versa.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

_POC = Path(__file__).resolve().parents[1]
_SRC = _POC / "src"

TOOLKIT_SKIP_REASON = (
    "dry-run tests need ML_PACKAGE_ROOT pointing at a rendered ai-project-template "
    "tree with an importable `ml` package; it is unset or not importable here"
)


def _toolkit_available() -> bool:
    """Gate on the env var FIRST, then prove the imports.

    The bare-import probe fraud's tests use is not enough here: galactus vendors a
    partial `ml/` copy at the repo root, and running alongside `review/tests` (a
    package chain) puts the repo root on `sys.path` — the probe would then find the
    vendored copy, un-skip these tests, and run them against a tree with no
    `experiments/`. The plan's posture is explicit: skip when `ML_PACKAGE_ROOT` is
    unset, full stop.
    """
    root = os.environ.get("ML_PACKAGE_ROOT")
    if not root:
        return False
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import experiments.record  # noqa: F401

        import ml.workflows.classification  # noqa: F401
    except Exception:  # noqa: BLE001 — any import failure means "cannot test", not "crash"
        return False
    return True


requires_toolkit = pytest.mark.skipif(not _toolkit_available(), reason=TOOLKIT_SKIP_REASON)


def _load_run_module():
    """Import `src/run.py` as `lending_run` — never as the contested bare name `run`."""
    if "lending_run" in sys.modules:
        return sys.modules["lending_run"]
    spec = importlib.util.spec_from_file_location("lending_run", _SRC / "run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["lending_run"] = module
    spec.loader.exec_module(module)
    return module


@requires_toolkit
def test_dry_run_exits_zero_with_no_data_read(monkeypatch, capsys, tmp_path):
    """The POC demo target: `run.py --dry-run` exits 0 in a checkout with no CSV."""
    run_mod = _load_run_module()
    monkeypatch.setattr(
        sys, "argv", ["run.py", "--dry-run", "--summary-json", str(tmp_path / "s.json")]
    )
    # Point the data default somewhere that cannot exist: a dry run must never read it.
    monkeypatch.setattr(run_mod, "DEFAULT_DATA", tmp_path / "absent" / "never.csv")

    assert run_mod.main() == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["models"], "dry run produced no model entries"
    names = [m["name"] for m in summary["models"]]
    assert "logistic" in names
    # The report landed in a temp dir, never on the tracked real report.
    assert str(_POC / "docs") not in summary["report"]
    assert (tmp_path / "s.json").exists()


@requires_toolkit
def test_dry_run_metrics_compare_against_synthetic_floor(monkeypatch, capsys):
    """Fixture-spec rule: synthetic prevalence is the baseline floor, never 0.4213."""
    import synthetic

    run_mod = _load_run_module()
    monkeypatch.setattr(sys, "argv", ["run.py", "--dry-run"])
    assert run_mod.main() == 0
    summary = json.loads(capsys.readouterr().out)

    logistic = next(m for m in summary["models"] if m["name"] == "logistic")
    # A learnable-but-weak synthetic frame: PR-AUC at or above the no-skill floor, and
    # nowhere near the leak regime. Bounds are structural, not a performance target.
    assert logistic["pr_auc"] >= synthetic.SYNTHETIC_PREVALENCE * 0.8
    assert logistic["roc_auc"] < 0.95


@requires_toolkit
def test_planted_twin_aborts_the_dry_run_path(tmp_path):
    """Invoking the dry-run path with the planted twin must abort via GuardError,
    naming the surviving planted column — exercised from tests, not the CLI."""
    import synthetic
    from frame import SEED, prepare_frame
    from guards import GuardError

    run_mod = _load_run_module()
    df = prepare_frame(synthetic.planted_leak_frame(SEED))
    with pytest.raises(GuardError) as exc_info:
        run_mod.run_pipeline(
            df,
            n_splits=5,
            models=run_mod.DRY_RUN_MODELS,
            report_path=tmp_path / "report.html",
            summary_json=None,
        )
    assert "post_outcome_score" in str(exc_info.value)
    # The abort happened before any artifact was written.
    assert not (tmp_path / "report.html").exists()
