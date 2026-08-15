"""Tests for the eval harness.

The harness is the thing that turns "it handles constraints" into a number, so
the number had better be right. These tests exercise the arithmetic and the
scoring rules directly rather than trusting a green dry run: a metric that is
computed wrong still prints, and prints confidently.

`evals/` is a script directory, not a package — nothing imports it in
production, so it is deliberately outside `src/`. The repo root goes on the path
here for the same reason `run.py` puts `src/` on it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.run import (
    CaseResult,
    EvalCase,
    ScriptedEvalLLM,
    compute_metrics,
    format_report,
    is_grounded,
    load_cases,
    main,
    run_all,
    run_case,
    summarize_table,
)

from models import Fact


def _result(
    case_id: str = "c",
    *,
    first_pass_valid: bool = True,
    repair_attempts: int = 0,
    used_fallback: bool = False,
    grounded: bool = True,
    contract_valid: bool = True,
    llm_calls: int = 1,
    error: str | None = None,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        difficulty="medium",
        first_pass_valid=first_pass_valid,
        repair_attempts=repair_attempts,
        used_fallback=used_fallback,
        grounded=grounded,
        contract_valid=contract_valid,
        llm_calls=llm_calls,
        error=error,
    )


# ---------------------------------------------------------------------------
# Case loading
# ---------------------------------------------------------------------------


def test_the_shipped_case_file_loads():
    cases = load_cases()

    assert len(cases) >= 10
    assert all(c.case_id and c.template_id for c in cases)
    assert {c.difficulty for c in cases} == {"easy", "medium", "hard"}


def test_case_file_covers_the_paths_the_metrics_need():
    """A case file of only easy cases would report a perfect, meaningless run."""
    cases = load_cases()

    assert any(c.difficulty == "hard" for c in cases)
    assert any(not c.sender_facts and not c.receiver_facts for c in cases)
    assert any(f.origin == "vision" for c in cases for f in c.sender_facts + c.receiver_facts)


def test_duplicate_case_ids_are_rejected(tmp_path):
    """Two rows with one id would silently halve a denominator."""
    path = tmp_path / "dupes.jsonl"
    row = {"case_id": "same", "prompt": "x", "template_id": "two_column_brief"}
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")

    with pytest.raises(ValueError, match="duplicate case_id"):
        load_cases(path)


def test_blank_lines_are_skipped(tmp_path):
    path = tmp_path / "gappy.jsonl"
    path.write_text(
        json.dumps({"case_id": "a", "prompt": "x"})
        + "\n\n"
        + json.dumps({"case_id": "b", "prompt": "y"})
        + "\n"
    )

    assert [c.case_id for c in load_cases(path)] == ["a", "b"]


def test_from_dict_fills_defaults():
    case = EvalCase.from_dict({"case_id": "bare"})

    assert case.template_id == "two_column_brief"
    assert case.difficulty == "medium"
    assert case.sender_facts == []


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------


def _fact(text: str) -> Fact:
    return Fact(text=text, source_span="p1:0-10", page=1)


def test_grounded_when_the_draft_reuses_distinctive_fact_tokens():
    facts = [_fact("Meridian moved 184,000 shipments through the Chicago corridor.")]
    draft = {"headline": "Meridian moved 184,000 shipments"}

    assert is_grounded(draft, facts)


def test_ungrounded_when_the_draft_shares_nothing_distinctive():
    facts = [_fact("Meridian moved 184,000 shipments through the Chicago corridor.")]
    draft = {"headline": "A bold new era begins"}

    assert not is_grounded(draft, facts)


def test_one_shared_token_is_not_enough():
    """A company name alone is a mention, not grounding."""
    facts = [_fact("Meridian moved 184,000 shipments through the Chicago corridor.")]
    draft = {"headline": "Meridian announces something entirely unrelated"}

    assert not is_grounded(draft, facts)


def test_a_case_with_no_facts_is_never_grounded():
    """The vacuous pass is the exact overclaim these metrics exist to prevent."""
    assert not is_grounded({"headline": "Anything at all"}, [])


def test_stopwords_do_not_count_as_grounding():
    facts = [_fact("the and for with from that this")]
    draft = {"headline": "the and for with from that this"}

    assert not is_grounded(draft, facts)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_metrics_over_a_mixed_run():
    results = [
        _result("a", first_pass_valid=True, repair_attempts=0),
        _result("b", first_pass_valid=False, repair_attempts=2),
        _result("c", first_pass_valid=False, repair_attempts=1, grounded=False),
        _result(
            "d",
            first_pass_valid=False,
            repair_attempts=3,
            used_fallback=True,
            grounded=False,
        ),
    ]

    metrics = compute_metrics(results)

    assert metrics["cases"] == 4
    assert metrics["contract_pass_rate"] == 25.0
    assert metrics["fallback_rate"] == 25.0
    assert metrics["grounding_rate"] == 50.0
    assert metrics["contract_valid_rate"] == 100.0


def test_convergence_excludes_the_cases_that_never_converged():
    """A fallback case burned its whole budget without converging.

    Averaging it in would inflate the mean with a number that is not a
    convergence time — it is the budget ceiling, recorded for a case that hit it.
    """
    results = [
        _result("a", repair_attempts=1),
        _result("b", repair_attempts=1),
        _result("c", repair_attempts=3, used_fallback=True),
    ]

    # 1 and 1 over two converged cases, not 5/3 over three.
    assert compute_metrics(results)["repair_convergence"] == 1.0


def test_convergence_excludes_errored_cases():
    results = [
        _result("a", repair_attempts=2),
        _result("b", repair_attempts=0, error="LLMError: boom", contract_valid=False),
    ]

    assert compute_metrics(results)["repair_convergence"] == 2.0
    assert compute_metrics(results)["errors"] == 1


def test_convergence_is_none_when_nothing_converged():
    """None, not zero. Zero would read as 'converged immediately'."""
    results = [_result("a", repair_attempts=3, used_fallback=True)]

    assert compute_metrics(results)["repair_convergence"] is None


def test_contract_pass_rate_is_first_pass_not_final():
    """The two are different numbers, and conflating them is the whole trap."""
    results = [_result("a", first_pass_valid=False, repair_attempts=1)]

    metrics = compute_metrics(results)

    assert metrics["contract_pass_rate"] == 0.0
    assert metrics["contract_valid_rate"] == 100.0


def test_llm_calls_are_summed():
    results = [_result("a", llm_calls=1), _result("b", llm_calls=4)]

    assert compute_metrics(results)["total_llm_calls"] == 5


def test_scoring_an_empty_run_is_an_error():
    with pytest.raises(ValueError, match="no cases"):
        compute_metrics([])


# ---------------------------------------------------------------------------
# Running cases
# ---------------------------------------------------------------------------


async def test_a_clean_case_passes_on_the_first_call(template):
    case = EvalCase(
        case_id="clean",
        prompt="Announce it.",
        template_id="two_column_brief",
        sender_facts=[_fact("Meridian operates 42 distribution centers.")],
    )
    llm = ScriptedEvalLLM(template, overshoot=False, stubborn=False)

    result = await run_case(case, llm)

    assert result.first_pass_valid
    assert result.repair_attempts == 0
    assert not result.used_fallback
    assert result.contract_valid
    assert result.llm_calls == 1


async def test_an_overshooting_case_repairs_once_and_converges(template):
    case = EvalCase(case_id="over", prompt="Be expansive.", template_id="two_column_brief")
    llm = ScriptedEvalLLM(template, overshoot=True, stubborn=False)

    result = await run_case(case, llm)

    assert not result.first_pass_valid
    assert result.repair_attempts == 1
    assert not result.used_fallback
    assert result.contract_valid
    assert result.llm_calls == 2


async def test_a_stubborn_case_exhausts_the_budget_and_falls_back(template):
    case = EvalCase(case_id="stuck", prompt="Never comply.", template_id="two_column_brief")
    llm = ScriptedEvalLLM(template, overshoot=True, stubborn=True)

    result = await run_case(case, llm)

    assert result.repair_attempts == 3
    assert result.used_fallback
    # The fallback is the guarantee: degraded, but never invalid.
    assert result.contract_valid
    assert result.llm_calls == 4


async def test_a_dead_provider_scores_as_an_error_rather_than_ending_the_run(template):
    class DeadLLM:
        calls = 0

        async def complete_structured(self, prompt, schema):
            raise RuntimeError("provider is down")

    cases = [
        EvalCase(case_id="dead", prompt="x", template_id="two_column_brief"),
        EvalCase(case_id="also-dead", prompt="y", template_id="two_column_brief"),
    ]

    results = await run_all(cases, DeadLLM())

    assert len(results) == 2
    assert all(r.error and not r.contract_valid for r in results)


async def test_run_all_preserves_case_order(template):
    cases = [
        EvalCase(case_id=f"c{i}", prompt="x", template_id="two_column_brief") for i in range(3)
    ]

    results = await run_all(cases, ScriptedEvalLLM(template, overshoot=False, stubborn=False))

    assert [r.case_id for r in results] == ["c0", "c1", "c2"]


# ---------------------------------------------------------------------------
# The scripted adapter
# ---------------------------------------------------------------------------


def test_stress_fields_breach_only_the_named_fields(template):
    """Otherwise every hard case reports the same violations and distinguishes nothing."""
    from guardrails.validator import validate

    llm = ScriptedEvalLLM(
        template,
        overshoot=True,
        stubborn=True,
        stress_fields=frozenset({"headline"}),
    )
    draft = {f.name: llm._value_for(f, breaching=True) for f in template.fields}

    assert {v.field for v in validate(draft, template)} == {"headline"}


def test_bad_color_emits_a_hex_literal(template):
    llm = ScriptedEvalLLM(
        template,
        overshoot=True,
        stubborn=True,
        stress_fields=frozenset(),
        bad_color=True,
    )
    color_field = next(f for f in template.fields if f.kind == "color_ref")

    assert llm._value_for(color_field, breaching=True).startswith("#")
    assert llm._value_for(color_field, breaching=False) == "accent"


# ---------------------------------------------------------------------------
# Reporting and entry point
# ---------------------------------------------------------------------------


def test_summarize_table_renders_a_header_and_a_row_per_dict():
    out = summarize_table([{"a": 1, "b": "x"}, {"a": 22, "b": "yy"}])
    lines = out.splitlines()

    assert len(lines) == 4  # header, rule, two rows
    assert lines[0].startswith("| a")
    assert "22" in lines[3]


def test_summarize_table_handles_no_rows():
    assert summarize_table([]) == "_no rows_"


def test_report_names_every_metric():
    results = [_result("a"), _result("b", used_fallback=True, repair_attempts=3)]
    report = format_report(results, compute_metrics(results))

    for label in (
        "Contract pass rate",
        "Repair convergence",
        "Fallback rate",
        "Grounding rate",
    ):
        assert label in report


def test_report_surfaces_errors():
    results = [_result("a", error="LLMError: boom", contract_valid=False)]
    report = format_report(results, compute_metrics(results))

    assert "Errors:" in report
    assert "LLMError: boom" in report


def test_dry_run_exits_zero_without_a_credential(capsys, monkeypatch):
    """The whole point of --dry-run: no network, no key, no spend.

    `ANTHROPIC_API_KEY` is removed rather than left to the ambient environment,
    so a machine that happens to have one set tests the same path as CI.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "Contract valid after repair+fallback: 100.0%" in out
    assert "no-facts-at-all" in out


def test_dry_run_json_output_is_parseable(capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert main(["--dry-run", "--json"]) == 0

    metrics = json.loads(capsys.readouterr().out)
    assert set(metrics) >= {
        "contract_pass_rate",
        "repair_convergence",
        "fallback_rate",
        "grounding_rate",
    }
    assert metrics["cases"] >= 10


def test_dry_run_spread_is_not_degenerate(capsys, monkeypatch):
    """A run where every case behaves identically measures nothing."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    main(["--dry-run", "--json"])
    metrics = json.loads(capsys.readouterr().out)

    assert 0.0 < metrics["contract_pass_rate"] < 100.0
    assert metrics["fallback_rate"] > 0.0
    assert metrics["total_llm_calls"] > metrics["cases"]
