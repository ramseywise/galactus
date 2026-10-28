"""Result types for the generation-under-contract harness.

``CaseResult`` is what one case produced; the metrics are computed from a
list of these. Zero imports from ``galactus.*``, ``ml.*``, or ``agents.*`` —
this module is case-agnostic by construction.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CaseResult:
    """What one case produced. The metrics are computed from a list of these."""

    case_id: str
    difficulty: str
    first_pass_valid: bool
    repair_attempts: int
    used_fallback: bool
    grounded: bool
    contract_valid: bool
    llm_calls: int
    error: str | None = None
