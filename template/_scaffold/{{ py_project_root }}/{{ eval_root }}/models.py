"""Data models for the interaction-eval suite (graders/heuristic + graders/judges).

Distinct from the retrieval golden-QA models in pipelines/run.py — retrieval
grades search quality against a golden set; interaction evals grade recorded
assistant conversations (escalation, friction, intent, language) with paired
heuristic flags and LLM-judge scores.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvalInteraction(BaseModel):
    """One recorded user↔assistant exchange to grade.

    Optional fields activate individual metrics — an interaction with no
    ``expected_intent`` simply isn't graded for intent. Loaded from JSONL;
    see data/evals/interactions_sample.jsonl for the shape.
    """

    id: str
    query: str
    response: str

    # intent: what the system routed/classified vs. what it should have
    routed_to: str | None = None
    expected_intent: str | None = None

    # escalation: did the assistant hand off, and should it have
    escalated: bool | None = None
    escalation_expected: bool | None = None

    # language: expected response language (BCP47-ish short code, e.g. "en")
    expected_language: str | None = None

    latency_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraderResult(BaseModel):
    interaction_id: str
    metric: str
    grader: str  # "heuristic" | "judge"
    is_correct: bool
    score: float
    reasoning: str = ""
    dimensions: dict[str, float] = Field(default_factory=dict)


class MetricSummary(BaseModel):
    metric: str
    n_heuristic: int
    n_judge: int
    heuristic_pass_rate: float | None = None
    judge_pass_rate: float | None = None
    judge_mean_score: float | None = None


class InteractionReport(BaseModel):
    generated_at: str
    n_interactions: int
    judges_ran: bool
    redaction_applied: bool
    summaries: list[MetricSummary]
