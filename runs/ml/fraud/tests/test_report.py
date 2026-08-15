"""The report surface's anchors, pinned against real toolkit markup.

`report.py` annotates `ml.reporting.html`'s document by string and regex injection. That
seam is invisible: an anchor that stops matching removes a caveat from the report and
changes nothing else, so the artefact still renders, still looks finished, and quietly
drops the one sentence that tells the reader the numbers are near the floor.

Three of the five anchors were written against markup the toolkit does not emit and were
silently no-ops from the first run — caught only when these tests were added. Every test
below therefore runs against `upstream_report`, a genuine `write_report` document, rather
than against HTML invented to match the implementation.
"""

from __future__ import annotations

import pytest
from report import (
    ReportAnchorError,
    _inject_fairness_notes,
    _inject_floor_note,
    _inject_refusal_banner,
)


def _annotate(document: str, summary: dict) -> str:
    """The same three injections `write_fraud_report` applies, minus the toolkit call."""
    document = _inject_refusal_banner(document, summary)
    document = _inject_floor_note(document, summary)
    return _inject_fairness_notes(document, summary)


class TestAnchorsMatchRealOutput:
    """The regression that the original suite was missing entirely."""

    def test_every_injection_finds_its_anchor(self, upstream_report, fraud_summary):
        # The whole point: no ReportAnchorError against a real document.
        _annotate(upstream_report, fraud_summary)

    def test_annotation_is_additive(self, upstream_report, fraud_summary):
        out = _annotate(upstream_report, fraud_summary)
        assert len(out) > len(upstream_report)
        # Nothing the toolkit wrote is removed — injections only insert.
        assert upstream_report.count("<h2>Model comparison</h2>") == out.count(
            "<h2>Model comparison</h2>"
        )


class TestRefusalBanner:
    def test_banner_lands_directly_after_the_heading(self, upstream_report, fraud_summary):
        out = _inject_refusal_banner(upstream_report, fraud_summary)
        heading = out.index("<h2>Model comparison</h2>")
        banner = out.index("No operating point is reported.")
        table = out.index('<div class="table-wrap">')
        # The refusal must be read before any metric, not after the table.
        assert heading < banner < table

    def test_banner_states_the_evidence_it_refused_over(self, upstream_report, fraud_summary):
        out = _inject_refusal_banner(upstream_report, fraud_summary)
        assert "2 positive case(s)" in out  # thinnest fold
        assert "14 across the frame" in out  # whole frame
        assert "1.75%" in out  # prevalence

    def test_no_banner_when_an_operating_point_is_reported(self, upstream_report, fraud_summary):
        sufficient = {**fraud_summary, "refusal": {**fraud_summary["refusal"]}}
        sufficient["refusal"]["operating_point_reported"] = True
        out = _inject_refusal_banner(upstream_report, sufficient)
        assert out == upstream_report
        assert "No operating point is reported." not in out


class TestFloorNote:
    def test_floor_fact_joins_the_run_facts_list(self, upstream_report, fraud_summary):
        out = _inject_floor_note(upstream_report, fraud_summary)
        assert "<dt>PR-AUC floor</dt><dd>0.0175 (positive-class prevalence)</dd>" in out
        # Inside the definition list, not orphaned after it.
        assert out.index("PR-AUC floor") < out.index("</dl>")

    def test_column_header_carries_the_floor(self, upstream_report, fraud_summary):
        out = _inject_floor_note(upstream_report, fraud_summary)
        assert "<th>PR-AUC (floor 0.0175)</th>" in out
        assert "<th>PR-AUC</th>" not in out

    def test_note_states_the_floor_and_the_lending_contrast(self, upstream_report, fraud_summary):
        out = _inject_floor_note(upstream_report, fraud_summary)
        assert "0.0175" in out
        # Step 7's done-condition: the lending contrast must be on the page.
        assert "0.2056" in out
        # Best PR-AUC is 0.0200 on a 0.0175 floor — 1.1x chance, not "poor but working".
        assert "1.1x chance" in out

    def test_note_lands_under_the_model_table(self, upstream_report, fraud_summary):
        out = _inject_floor_note(upstream_report, fraud_summary)
        note = out.index("no-skill floor")
        assert out.index("</tbody>") < note < out.index("<h2>Curves")

    def test_zero_prevalence_does_not_divide_by_zero(self, upstream_report, fraud_summary):
        empty = {**fraud_summary, "prevalence_floor": 0.0, "models": []}
        out = _inject_floor_note(upstream_report, empty)
        assert "0.0x chance" in out


class TestFairnessNotes:
    def test_section_renders_before_body_close(self, upstream_report, fraud_summary):
        out = _inject_fairness_notes(upstream_report, fraud_summary)
        assert "<h2>Fairness notes</h2>" in out
        assert out.index("Fairness notes") < out.index("</body>")

    def test_the_age_note_is_on_the_page(self, upstream_report, fraud_summary):
        out = _inject_fairness_notes(upstream_report, fraud_summary)
        assert "`age` is used raw" in out
        assert "protected characteristic" in out

    def test_no_section_when_there_are_no_notes(self, upstream_report, fraud_summary):
        out = _inject_fairness_notes(upstream_report, {**fraud_summary, "fairness_notes": []})
        assert out == upstream_report


class TestAnchorDriftIsLoud:
    """The defect class itself: a missing anchor must raise, never shrug.

    Each case deletes one anchor from a real document — the minimal simulation of an
    upstream markup change — and asserts the injection refuses instead of returning a
    report with the caveat quietly missing.
    """

    @pytest.mark.parametrize(
        ("anchor", "inject", "what"),
        [
            ("<h2>Model comparison</h2>", _inject_refusal_banner, "refusal banner"),
            ("<dl class=\"meta\">", _inject_floor_note, "floor fact"),
            ("</body>", _inject_fairness_notes, "fairness notes"),
        ],
    )
    def test_missing_anchor_raises(self, upstream_report, fraud_summary, anchor, inject, what):
        broken = upstream_report.replace(anchor, "<!-- upstream changed -->")
        with pytest.raises(ReportAnchorError) as excinfo:
            inject(broken, fraud_summary)
        # The message must name the fix, not just the failure.
        assert "report.py" in str(excinfo.value)

    def test_a_silent_skip_would_have_passed_the_old_suite(self, upstream_report, fraud_summary):
        """Documents why this class exists: without the raise, the output is a valid
        document that is simply missing its caveat — indistinguishable from success."""
        broken = upstream_report.replace("</body>", "<!-- upstream changed -->")
        with pytest.raises(ReportAnchorError):
            _inject_fairness_notes(broken, fraud_summary)
