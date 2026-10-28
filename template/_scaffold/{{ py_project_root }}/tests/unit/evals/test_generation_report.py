"""Unit tests for the generation harness's human-readable report
(evals/generation/report.py).

`format_report` is the only part of the harness a person actually reads, and
it is a pure function over `CaseResult` rows plus a `compute_metrics` dict —
no LLM calls, no galactus/ml/agents imports. The metrics dict is built by
`compute_metrics` rather than hand-written, so a change to the metric keys
breaks this test instead of silently rendering a report with a missing number.

Two properties are worth asserting rather than trusting:

  - every case reaches the table, so a report is never a partial view of the
    run it claims to summarize;
  - `repair_convergence=None` (no case converged) renders as "n/a" rather than
    "None", and case errors surface in their own section — a report that
    swallowed either would read like a clean run.
"""

from __future__ import annotations

from evals.generation.metrics import compute_metrics
from evals.generation.report import format_report, summarize_table
from evals.generation.results import CaseResult


def _result(**overrides: object) -> CaseResult:
    base: dict[str, object] = {
        "case_id": "c-1",
        "difficulty": "medium",
        "first_pass_valid": True,
        "repair_attempts": 0,
        "used_fallback": False,
        "grounded": True,
        "contract_valid": True,
        "llm_calls": 1,
        "error": None,
    }
    base.update(overrides)
    return CaseResult(**base)  # type: ignore[arg-type]


class TestSummarizeTable:
    def test_empty_rows_render_as_a_placeholder(self) -> None:
        assert summarize_table([]) == "_no rows_"

    def test_header_and_every_row_are_present(self) -> None:
        table = summarize_table([{"a": "1", "b": "2"}, {"a": "3", "b": "4"}])
        lines = table.splitlines()
        # header, separator, one line per row
        assert len(lines) == 4
        assert "a" in lines[0] and "b" in lines[0]
        assert "1" in lines[2] and "4" in lines[3]

    def test_columns_are_padded_to_a_common_width(self) -> None:
        table = summarize_table([{"case": "short"}, {"case": "a-much-longer-value"}])
        body = table.splitlines()[2:]
        assert len({len(line) for line in body}) == 1


class TestFormatReport:
    def test_every_case_reaches_the_table(self) -> None:
        results = [_result(case_id="a"), _result(case_id="b"), _result(case_id="c")]
        report = format_report(results, compute_metrics(results))
        for case_id in ("a", "b", "c"):
            assert case_id in report

    def test_headline_metrics_are_reported_with_denominators(self) -> None:
        results = [
            _result(case_id="a", first_pass_valid=True, grounded=True),
            _result(case_id="b", first_pass_valid=False, grounded=False),
        ]
        report = format_report(results, compute_metrics(results))
        assert "Cases:                2" in report
        assert "50.0%" in report

    def test_absent_convergence_reads_as_na_not_none(self) -> None:
        # Every case fell back, so no case converged -> repair_convergence is None.
        results = [_result(case_id="a", used_fallback=True)]
        metrics = compute_metrics(results)
        assert metrics["repair_convergence"] is None

        report = format_report(results, metrics)
        assert "Repair convergence:   n/a" in report
        assert "None" not in report

    def test_case_errors_are_surfaced_in_their_own_section(self) -> None:
        results = [
            _result(case_id="ok"),
            _result(case_id="bad", error="provider timed out"),
        ]
        report = format_report(results, compute_metrics(results))
        assert "Errors:" in report
        assert "bad: provider timed out" in report

    def test_a_clean_run_has_no_error_section(self) -> None:
        results = [_result(case_id="ok")]
        report = format_report(results, compute_metrics(results))
        assert "Errors:" not in report
