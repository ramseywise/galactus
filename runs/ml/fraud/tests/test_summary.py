"""The summary contract — the machine-readable form of the refusal.

`docs/summary.json` is what a consumer reads to learn whether an operating point was
chosen. The run exits 0 whether it refuses or not, deliberately, so the exit code carries
no information and this payload carries all of it. If `threshold` can be absent, or null
can be confused with zero, or `refusal` can be missing on a successful run, then an
automated reader can score a refusal as a pass — the same defect the guard exists to
prevent, moved from the report to the JSON.

Two layers here, on purpose:

* `TestCommittedArtifacts` runs everywhere. It asserts the invariants against the two
  artefacts the phase actually committed, and turns "the diff is the phase's proof" from
  a manual instruction in the Test Plan into an assertion that runs every time.
* `TestSummariseFunction` calls `summarise()` directly and needs the ML toolkit, because
  `run.py` imports it at module scope. It skips where the toolkit is absent — which is
  this checkout, since `ml/` holds no source and `ML_PACKAGE_ROOT` is unset.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_POC = Path(__file__).resolve().parents[1]


def _toolkit_available() -> bool:
    root = os.environ.get("ML_PACKAGE_ROOT")
    if root and root not in sys.path:
        sys.path.insert(0, root)
    try:
        import ml.workflows.classification  # noqa: F401
    except Exception:  # noqa: BLE001 — any import failure means "cannot test", not "crash"
        return False
    return True


requires_toolkit = pytest.mark.skipif(
    not _toolkit_available(),
    reason=(
        "the ML toolkit has no source in this checkout (ml/ holds only stale __pycache__) "
        "and ML_PACKAGE_ROOT is unset, so run.py cannot be imported"
    ),
)


class TestCommittedArtifacts:
    """The phase's proof, asserted rather than eyeballed."""

    def test_guarded_run_reports_no_threshold_for_any_model(self, fraud_summary):
        assert fraud_summary["models"], "a summary with no models proves nothing"
        for model in fraud_summary["models"]:
            assert model["threshold"] is None, (
                f"{model['name']} reported an operating point on a frame the guard refused"
            )

    def test_threshold_is_explicitly_null_not_absent(self, fraud_summary):
        """Null and missing are different answers to a consumer using .get()."""
        for model in fraud_summary["models"]:
            assert "threshold" in model, f"{model['name']} omits the threshold key entirely"

    def test_unguarded_run_did_report_thresholds(self, before_guard_summary):
        """The negative control. Without this, the guarded run's silence could mean the
        toolkit never reports thresholds at all, and the guard would be unfalsifiable."""
        thresholds = [m["threshold"] for m in before_guard_summary["models"]]
        assert len(thresholds) == 3
        assert all(isinstance(t, dict) for t in thresholds)

    def test_the_withheld_thresholds_were_the_worthless_ones(self, before_guard_summary):
        """What the guard actually suppressed: numbers to four decimal places describing
        zero true positives. This is the phase's motivating defect, pinned."""
        for model in before_guard_summary["models"]:
            threshold = model["threshold"]
            assert threshold["true_positives"] == 0
            assert threshold["precision"] == 0.0
            assert threshold["recall"] == 0.0

    def test_refusal_block_is_present_and_machine_readable(self, fraud_summary):
        refusal = fraud_summary["refusal"]
        assert refusal["operating_point_reported"] is False
        assert refusal["min_positives_in_fold"] == 2
        assert refusal["n_positives"] == 14
        assert refusal["reason"].strip(), "a refusal without a stated reason is a shrug"

    def test_prevalence_floor_is_carried_for_the_reader(self, fraud_summary):
        assert fraud_summary["prevalence_floor"] == pytest.approx(0.0175, abs=1e-4)

    def test_every_pr_auc_sits_near_the_floor(self, fraud_summary):
        """Context for the refusal: the models are at chance. If a future change makes
        them genuinely discriminative, this fails and the refusal needs rethinking."""
        floor = fraud_summary["prevalence_floor"]
        for model in fraud_summary["models"]:
            assert model["pr_auc"] < 2 * floor

    def test_headline_metric_is_named(self, fraud_summary):
        """Phase 1's registry lift depends on the payload naming its own load-bearing
        metric rather than the reader assuming PR-AUC."""
        assert fraud_summary["headline_metric"] == "average_precision"

    @pytest.mark.parametrize("artefact", ["summary.json", "before-guard.json"])
    def test_artefacts_carry_no_identifier(self, artefact):
        """Aggregates only. `uuid` is a real column in the frame; it must not survive."""
        raw = (_POC / "docs" / artefact).read_text(encoding="utf-8")
        assert "uuid" not in raw.lower()

    @pytest.mark.parametrize("artefact", ["summary.json", "before-guard.json"])
    def test_artefacts_carry_no_row_data(self, artefact):
        """Every leaf is a scalar or a container — no list of per-row values."""
        payload = json.loads((_POC / "docs" / artefact).read_text(encoding="utf-8"))

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                # `models` and `fairness_notes` are the only lists, and both are short.
                assert len(node) <= 10, f"{path} holds {len(node)} entries — looks like rows"
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")

        walk(payload)


@requires_toolkit
class TestSummariseFunction:
    """`summarise()` itself — the code that decides what reaches the JSON.

    The committed-artefact tests above prove one run behaved. These prove the function
    behaves, including the branch no committed artefact exercises: a frame the guard
    passes, where thresholds *must* appear.
    """

    @staticmethod
    def _fake_result(*, with_threshold: bool):
        from types import SimpleNamespace as Ns

        def model(name, is_baseline=False):
            threshold = None
            if with_threshold:
                threshold = Ns(
                    threshold=0.0562,
                    precision=0.5,
                    recall=0.4,
                    n_flagged=20,
                    true_positives=8,
                    expected_cost=100.0,
                    cost_at_default=200.0,
                    savings_vs_default=100.0,
                )
            return Ns(
                name=name,
                is_baseline=is_baseline,
                metrics=Ns(
                    average_precision=0.02, roc_auc=0.49, prevalence=0.0175, brier_score=0.017
                ),
                fit_seconds=1.23,
                calibration=Ns(
                    method="sigmoid",
                    brier_before=0.02,
                    brier_after=0.017,
                    ece_before=0.03,
                    ece_after=0.01,
                ),
                threshold=threshold,
            )

        baseline = model("logistic", is_baseline=True)
        best = model("lightgbm")
        return Ns(
            n_rows=800,
            n_features=42,
            sampling="class_weight",
            class_balance={"0": 786, "1": 14},
            split_plan=Ns(kind="stratified", n_splits=5),
            skipped=[],
            beats_baseline=False,
            models=[baseline, best],
            baseline=baseline,
            best=best,
        )

    @staticmethod
    def _verdict(*, sufficient: bool):
        from sufficiency import SufficiencyVerdict

        return SufficiencyVerdict(
            sufficient=sufficient,
            reason="test verdict",
            n_positives=14,
            min_positives_in_fold=2 if not sufficient else 40,
            prevalence=0.0175,
        )

    def test_refusal_nulls_every_threshold(self, tmp_path):
        from run import summarise

        summary = summarise(
            self._fake_result(with_threshold=False),
            self._verdict(sufficient=False),
            out=tmp_path / "r.html",
        )
        assert summary["refusal"]["operating_point_reported"] is False
        assert all(m["threshold"] is None for m in summary["models"])

    def test_sufficiency_reports_every_threshold(self, tmp_path):
        """The other direction. Without this, `summarise` could null thresholds
        unconditionally and every refusal test would still pass."""
        from run import summarise

        summary = summarise(
            self._fake_result(with_threshold=True),
            self._verdict(sufficient=True),
            out=tmp_path / "r.html",
        )
        assert summary["refusal"]["operating_point_reported"] is True
        assert all(m["threshold"] is not None for m in summary["models"])
        assert all(m["threshold"]["SELECTED_IN_SAMPLE"] is True for m in summary["models"])

    def test_refusal_block_present_even_when_not_refusing(self, tmp_path):
        """A consumer must never infer absence-of-refusal from a missing key."""
        from run import summarise

        summary = summarise(
            self._fake_result(with_threshold=True),
            self._verdict(sufficient=True),
            out=tmp_path / "r.html",
        )
        assert "refusal" in summary
        assert summary["refusal"]["reason"]
