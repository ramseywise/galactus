"""Unit tests for the case-agnostic core of the generation-under-contract
harness (evals/generation/results.py, metrics.py).

No LLM calls, no galactus/ml/agents imports — this is pure Python over
hand-built ``CaseResult`` rows.
"""

from __future__ import annotations

from evals.generation.metrics import compute_metrics, is_grounded
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


class TestIsGrounded:
    def test_empty_grounding_texts_is_never_grounded(self) -> None:
        assert is_grounded({"headline": "meridian partnership"}, []) is False

    def test_shared_distinctive_tokens_ground_the_output(self) -> None:
        output = {"headline": "The meridian partnership expands operations"}
        grounding_texts = ["Meridian signed a new partnership agreement."]
        assert is_grounded(output, grounding_texts) is True

    def test_stopwords_do_not_count_toward_overlap(self) -> None:
        output = {"headline": "This is the way and it is fine"}
        grounding_texts = ["We have this and that for our customers over there"]
        # Only stopwords/short tokens shared -> below MIN_GROUNDING_OVERLAP.
        assert is_grounded(output, grounding_texts) is False

    def test_single_shared_token_is_not_enough(self) -> None:
        output = {"headline": "meridian unrelated words here"}
        grounding_texts = ["meridian is a logistics company"]
        assert is_grounded(output, grounding_texts) is False


class TestComputeMetrics:
    def test_rates_and_denominators(self) -> None:
        results = [
            _result(case_id="a", first_pass_valid=True, grounded=True, contract_valid=True),
            _result(case_id="b", first_pass_valid=False, grounded=False, contract_valid=True),
        ]
        metrics = compute_metrics(results)
        assert metrics["cases"] == 2
        assert metrics["contract_pass_rate"] == 50.0
        assert metrics["grounding_rate"] == 50.0
        assert metrics["contract_valid_rate"] == 100.0

    def test_repair_convergence_is_none_when_nothing_converged(self) -> None:
        results = [
            _result(case_id="a", used_fallback=True),
            _result(case_id="b", error="BoomError: dead"),
        ]
        metrics = compute_metrics(results)
        assert metrics["repair_convergence"] is None

    def test_repair_convergence_excludes_fallback_and_errored_cases(self) -> None:
        results = [
            _result(case_id="a", repair_attempts=2, used_fallback=False, error=None),
            _result(case_id="b", repair_attempts=10, used_fallback=True, error=None),
            _result(case_id="c", repair_attempts=10, used_fallback=False, error="Dead: x"),
        ]
        metrics = compute_metrics(results)
        # Only case "a" converged; convergence is its own repair_attempts.
        assert metrics["repair_convergence"] == 2.0

    def test_no_cases_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="no cases to score"):
            compute_metrics([])

    def test_errors_and_total_llm_calls_are_summed(self) -> None:
        results = [
            _result(case_id="a", llm_calls=3, error=None),
            _result(case_id="b", llm_calls=2, error="Dead: x"),
        ]
        metrics = compute_metrics(results)
        assert metrics["errors"] == 1
        assert metrics["total_llm_calls"] == 5
