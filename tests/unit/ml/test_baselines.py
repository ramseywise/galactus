"""Targets and baseline comparison.

The claims that matter here are all about *not* reporting a false pass. A gate
that cannot be evaluated must say so rather than staying silent, because a metric
absent from a gate report is indistinguishable from one that passed.
"""

from __future__ import annotations

import json

from ml.evaluation.baselines import (
    check_absolute,
    check_baseline,
    load_targets,
    write_baseline,
)

TARGETS = {
    "absolute": {
        "average_precision_over_prevalence": 1.0,
        "roc_auc": 0.70,
        "brier": 0.20,
    },
    "baseline": {"tolerance": 0.01, "metrics": ["average_precision", "roc_auc", "brier"]},
    "direction": {"lower_is_better": ["brier"]},
}


def test_shipped_targets_file_parses():
    """The file ships with the template — a malformed one breaks every run."""
    targets = load_targets()
    assert "absolute" in targets
    assert targets["baseline"]["tolerance"] == 0.01


def test_missing_targets_file_yields_empty(tmp_path):
    """A project that has not set targets must still be able to run."""
    assert load_targets(tmp_path / "nope.yaml") == {}


# ── absolute targets ─────────────────────────────────────────────────────────


def test_higher_is_better_metric_passes_above_its_floor():
    verdict = check_absolute({"roc_auc": 0.80}, TARGETS, prevalence=0.05)
    roc = next(v for v in verdict.verdicts if v.metric == "roc_auc")
    assert roc.passed


def test_higher_is_better_metric_fails_below_its_floor():
    verdict = check_absolute({"roc_auc": 0.60}, TARGETS, prevalence=0.05)
    roc = next(v for v in verdict.verdicts if v.metric == "roc_auc")
    assert not roc.passed
    assert not verdict.passed


def test_lower_is_better_metric_is_not_inverted():
    """Brier is declared lower-is-better; treating it as higher-is-better would
    silently invert the gate, which is worse than having none."""
    good = check_absolute({"brier": 0.10}, TARGETS, prevalence=0.05)
    bad = check_absolute({"brier": 0.30}, TARGETS, prevalence=0.05)

    assert next(v for v in good.verdicts if v.metric == "brier").passed
    assert not next(v for v in bad.verdicts if v.metric == "brier").passed


def test_a_metric_at_chance_fails_the_prevalence_floor():
    """PR-AUC equal to prevalence is chance, whatever the number looks like."""
    verdict = check_absolute({"average_precision": 0.05}, TARGETS, prevalence=0.05)

    over = next(v for v in verdict.verdicts if v.metric == "average_precision_over_prevalence")
    assert over.passed, "1.0x prevalence exactly meets a 1.0x floor"

    worse = check_absolute({"average_precision": 0.03}, TARGETS, prevalence=0.05)
    assert not next(
        v for v in worse.verdicts if v.metric == "average_precision_over_prevalence"
    ).passed


def test_prevalence_floor_is_skipped_not_passed_when_prevalence_is_unknown():
    """The important negative case: a gate that cannot be evaluated must not
    report success."""
    verdict = check_absolute({"average_precision": 0.4}, TARGETS, prevalence=None)

    assert "average_precision_over_prevalence" in verdict.skipped
    assert not any(v.metric == "average_precision_over_prevalence" for v in verdict.verdicts)


def test_an_unreported_metric_is_skipped_not_passed():
    verdict = check_absolute({"roc_auc": 0.9}, TARGETS, prevalence=0.05)
    assert "brier" in verdict.skipped


# ── baseline comparison ──────────────────────────────────────────────────────


def test_first_run_skips_every_metric(tmp_path):
    """ "No baseline" and "no regression" are different facts."""
    verdict = check_baseline({"roc_auc": 0.8}, tmp_path / "baseline.json", TARGETS)

    assert verdict.verdicts == []
    assert "first run" in verdict.skipped["roc_auc"]


def test_a_regression_beyond_tolerance_fails(tmp_path):
    baseline = tmp_path / "baseline.json"
    write_baseline({"roc_auc": 0.85}, baseline, model_name="logistic", prevalence=0.05)

    verdict = check_baseline({"roc_auc": 0.70}, baseline, TARGETS)

    roc = next(v for v in verdict.verdicts if v.metric == "roc_auc")
    assert not roc.passed
    assert "-0.15" in roc.detail


def test_a_movement_inside_tolerance_is_reported_as_unchanged(tmp_path):
    """A 0.0002 movement reported as a regression trains people to ignore the gate."""
    baseline = tmp_path / "baseline.json"
    write_baseline({"roc_auc": 0.8500}, baseline, model_name="logistic")

    verdict = check_baseline({"roc_auc": 0.8498}, baseline, TARGETS)

    roc = next(v for v in verdict.verdicts if v.metric == "roc_auc")
    assert roc.passed
    assert "unchanged" in roc.detail


def test_an_improvement_passes(tmp_path):
    baseline = tmp_path / "baseline.json"
    write_baseline({"roc_auc": 0.70}, baseline, model_name="logistic")

    verdict = check_baseline({"roc_auc": 0.85}, baseline, TARGETS)

    assert verdict.passed


def test_lower_is_better_regression_is_detected(tmp_path):
    """Brier rising is a regression; the direction map must be honoured here too."""
    baseline = tmp_path / "baseline.json"
    write_baseline({"brier": 0.10}, baseline, model_name="logistic")

    worse = check_baseline({"brier": 0.25}, baseline, TARGETS)
    better = check_baseline({"brier": 0.05}, baseline, TARGETS)

    assert not next(v for v in worse.verdicts if v.metric == "brier").passed
    assert next(v for v in better.verdicts if v.metric == "brier").passed


def test_a_metric_absent_from_the_baseline_is_skipped(tmp_path):
    baseline = tmp_path / "baseline.json"
    write_baseline({"roc_auc": 0.8}, baseline, model_name="logistic")

    verdict = check_baseline({"roc_auc": 0.8, "brier": 0.1}, baseline, TARGETS)

    assert "brier" in verdict.skipped


# ── writing ──────────────────────────────────────────────────────────────────


def test_write_baseline_records_prevalence(tmp_path):
    """A stored metric without prevalence cannot be re-interpreted later."""
    path = write_baseline(
        {"average_precision": 0.12},
        tmp_path / "nested" / "baseline.json",
        model_name="lightgbm",
        prevalence=0.048,
    )

    payload = json.loads(path.read_text())
    assert payload["prevalence"] == 0.048
    assert payload["model"] == "lightgbm"
    assert payload["metrics"]["average_precision"] == 0.12


def test_report_names_the_overall_verdict(tmp_path):
    verdict = check_absolute({"roc_auc": 0.60}, TARGETS, prevalence=0.05)
    report = verdict.report()

    assert "FAIL" in report
    assert "roc_auc" in report
