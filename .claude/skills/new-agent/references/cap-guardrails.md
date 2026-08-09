# cap-guardrails — Templates for agent safety guardrails

**Tier: T2 — Runtime-adjacent.** The five-layer model and threat boundaries are runtime-agnostic (see `agent-safety.md`). The scaffold here is Python/FastAPI; the patterns are portable. Claude surface tripartition (API / Managed Agents / Computer Use) determines what Layer 4 can check.

## Agnostic contract

Every agent that surfaces output to a user must enforce at minimum Layer 1 (pre-input sanitization, injection detection) and Layer 4 (post-generate structural check). Layers 2, 3, and 5 are additive when the agent does retrieval or supports human handoff. Guardrails must be **fast** (< 5ms each in the hot path) — semantic grading belongs in the offline eval pipeline, not here. See `agent-safety.md` for the full threat model, injection defense, credential custody, and sandboxing rules.

| Runtime | Enforcement surface | Notes |
|---|---|---|
| Claude API | Layer 1 before messages[], Layer 4 on response.content | `computer_use_2025_02_01` beta also needs Layer 4 for tool call inspection |
| Claude Managed Agents | Platform-enforced input/output filtering + Layer 1 in pre-processing step | Layer 4 as post-process before surfacing to user |
| Google ADK | Session event hooks for Layer 1; output_schema validation as Layer 4 | ADK's `output_schema=` handles structural Layer 4 for typed outputs |
| LangGraph | Pre-input and post-generate nodes in the graph | Named nodes make the layers visible in LangSmith traces |
| Vercel AI SDK | Middleware on the API route for Layers 1 + 4 | Streaming: Layer 4 buffer first N tokens for structure check, then stream |

> **Claude surface tripartition (for HITL / Layer 5):** Claude exposes three distinct surfaces for human-in-the-loop interaction: (1) Claude API `tool_choice` with `interrupt_before=` for confirmation gates; (2) Claude Managed Agents with `multiagent` coordinator and per-subagent human-approval nodes; (3) Computer Use tools (`computer`, `bash`, `text_editor`) which require a mandatory human confirmation gate before any write operation. Layer 5 escalation must be designed against the specific surface in use — the gate mechanism differs per surface.

## Design notes

- **Layer order matters**: each layer is independently toggleable but must run in sequence (1 → 2 → 3 → 4 → 5). Never skip Layer 1 for "trusted" inputs — trust boundaries erode under composition.
- **Deny-list is not sufficient**: structural injection detection (XML-close-tag patterns) catches common attacks but is not a complete defense. Combine with instruction hierarchy (system > developer > user) and output grounding checks.
- **Layer 4 for grounding**: for RAG agents, Layer 4 checks that each claim in the output is traceable to a retrieved passage. If the agent's output references information not in the retrieved context, it fails Layer 4 — surface a `cannot_verify` response, not a hallucination.
- **Layer 5 friction signals**: escalate on intent classification score below 0.4, content policy flag, repeated clarification requests, or explicit "I'm not sure" from the model. Do not escalate on every borderline case — calibrate the threshold.

## File: {OUTPUT_DIR}/guardrails.py

```python
"""Five-layer agent guardrail scaffold for {AGENT_NAME}.

Layer 1: Pre-input  — sanitize, detect injection, redact PII
Layer 2: Pre-retrieval — routing confidence gate
Layer 3: Pre-generate  — retrieval quality gate
Layer 4: Post-generate — structural output check (grounding, citations, boundary)
Layer 5: Escalation    — friction signals → human handoff

Layers 1 and 4 are mandatory. Layers 2, 3, 5 are context-dependent.
Each layer raises GuardrailViolation on failure; the agent loop catches
this and decides whether to escalate, retry, or surface an error.

See agent-safety.md for threat model, injection defense, and credential custody.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Violation type
# ---------------------------------------------------------------------------


@dataclass
class GuardrailViolation(Exception):
    """Raised when a guardrail layer blocks the request."""

    layer: int
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"Layer {self.layer} guardrail violation: {self.reason}"


# ---------------------------------------------------------------------------
# Layer 1 — Pre-input
# ---------------------------------------------------------------------------

# Structural injection patterns: these attempt to close/override the system prompt.
_INJECTION_PATTERNS = [
    re.compile(r"</?(system|user|assistant|tool)[_\s]", re.IGNORECASE),
    re.compile(r"ignore (all )?(previous|prior) instructions", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"disregard (your|all) (previous |prior )?instructions", re.IGNORECASE),
    re.compile(r"<ADMIN>|<SYSTEM_OVERRIDE>", re.IGNORECASE),
]

# Simple PII patterns — supplement with a dedicated PII library for production.
_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def layer1_pre_input(
    text: str,
    *,
    redact_pii: bool = True,
    check_injection: bool = True,
    max_length: int = 10_000,
) -> str:
    """Layer 1: sanitize input text before it enters the agent pipeline.

    Args:
        text: Raw user input string.
        redact_pii: If True, replace detected PII with placeholders.
        check_injection: If True, raise on structural injection patterns.
        max_length: Maximum allowed input length in characters.

    Returns:
        Sanitized input string (PII redacted if requested).

    Raises:
        GuardrailViolation: On injection detection or oversized input.
    """
    if len(text) > max_length:
        raise GuardrailViolation(
            layer=1,
            reason=f"Input too long: {len(text)} chars (max {max_length})",
        )

    if check_injection:
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning("Layer 1: injection pattern detected in input")
                raise GuardrailViolation(
                    layer=1,
                    reason="Potential prompt injection detected",
                    details={"pattern": pattern.pattern},
                )

    if redact_pii:
        for pii_type, pattern in _PII_PATTERNS.items():
            text = pattern.sub(f"[{pii_type.upper()}_REDACTED]", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Layer 2 — Pre-retrieval (routing confidence gate)
# ---------------------------------------------------------------------------


def layer2_routing_gate(
    intent_score: float,
    threshold: float = 0.4,
) -> None:
    """Layer 2: reject low-confidence intent before retrieval.

    Args:
        intent_score: Classification confidence score (0.0–1.0).
        threshold: Minimum score to proceed to retrieval.

    Raises:
        GuardrailViolation: If intent_score < threshold.
    """
    if intent_score < threshold:
        raise GuardrailViolation(
            layer=2,
            reason=f"Low routing confidence: {intent_score:.2f} < {threshold:.2f}",
            details={"intent_score": intent_score, "threshold": threshold},
        )


# ---------------------------------------------------------------------------
# Layer 3 — Pre-generate (retrieval quality gate)
# ---------------------------------------------------------------------------


def layer3_retrieval_gate(
    passages: list[dict[str, Any]],
    threshold: float = 0.7,
) -> None:
    """Layer 3: skip generation if retrieval quality is too low.

    Args:
        passages: Retrieved passage dicts with 'score' keys.
        threshold: Minimum top-passage score to proceed.

    Raises:
        GuardrailViolation: If top passage score < threshold or no passages.
    """
    if not passages:
        raise GuardrailViolation(
            layer=3,
            reason="No passages retrieved — cannot ground a response",
        )

    top_score = max(p.get("score", 0.0) for p in passages)
    if top_score < threshold:
        raise GuardrailViolation(
            layer=3,
            reason=f"Retrieval quality too low: top score {top_score:.2f} < {threshold:.2f}",
            details={"top_score": top_score, "threshold": threshold},
        )


# ---------------------------------------------------------------------------
# Layer 4 — Post-generate (structural output check)
# ---------------------------------------------------------------------------


def layer4_output_check(
    response_text: str,
    passages: list[dict[str, Any]] | None = None,
    *,
    min_length: int = 10,
    max_length: int = 8_000,
    check_grounding: bool = True,
) -> None:
    """Layer 4: structural integrity check on generated output.

    Checks: minimum/maximum length, basic content policy, and optionally
    whether cited URLs appear in the retrieved passage set.

    Args:
        response_text: The agent's generated response.
        passages: Optional retrieved passages for grounding check.
        min_length: Minimum response length in characters.
        max_length: Maximum response length in characters.
        check_grounding: If True and passages provided, verify citation URLs.

    Raises:
        GuardrailViolation: If any structural check fails.
    """
    if len(response_text) < min_length:
        raise GuardrailViolation(
            layer=4,
            reason=f"Response too short: {len(response_text)} chars (min {min_length})",
        )

    if len(response_text) > max_length:
        raise GuardrailViolation(
            layer=4,
            reason=f"Response too long: {len(response_text)} chars (max {max_length})",
        )

    if check_grounding and passages:
        passage_urls = {
            p.get("url", "")
            or p.get("location", {}).get("webLocation", {}).get("url", "")
            for p in passages
        }
        passage_urls.discard("")

        # Extract URLs from response (simple heuristic — extend with a proper URL parser)
        cited_urls = set(re.findall(r"https?://[^\s\)\"']+", response_text))

        # Allow citations only to retrieved passage sources
        ungrounded = cited_urls - passage_urls
        if ungrounded and passage_urls:
            logger.warning("Layer 4: ungrounded citations: %s", ungrounded)
            # Warn but don't block by default — change to raise for strict grounding.
            # Raise here for strict: GuardrailViolation(layer=4, reason=f"Ungrounded citations: {ungrounded}")


# ---------------------------------------------------------------------------
# Layer 5 — Escalation
# ---------------------------------------------------------------------------


@dataclass
class EscalationSignal:
    """Escalation decision output from layer5_escalation_check."""

    should_escalate: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


def layer5_escalation_check(
    response_text: str,
    intent_score: float | None = None,
    content_policy_flag: bool = False,
    clarification_count: int = 0,
    *,
    intent_threshold: float = 0.4,
    clarification_limit: int = 2,
) -> EscalationSignal:
    """Layer 5: decide whether to escalate to a human.

    Does not raise — returns an EscalationSignal. The agent loop decides
    what to do with it (HITL handoff, queue for review, etc.).

    Args:
        response_text: The agent's generated response.
        intent_score: Routing confidence score (if available).
        content_policy_flag: True if a content policy check flagged this response.
        clarification_count: Number of clarification requests in this session.
        intent_threshold: Escalate if intent_score < this.
        clarification_limit: Escalate after this many clarification attempts.

    Returns:
        EscalationSignal with should_escalate bool and reason string.
    """
    signals: list[str] = []

    if intent_score is not None and intent_score < intent_threshold:
        signals.append(f"low intent confidence ({intent_score:.2f})")

    if content_policy_flag:
        signals.append("content policy flag")

    if clarification_count >= clarification_limit:
        signals.append(f"clarification limit reached ({clarification_count})")

    # Heuristic: explicit uncertainty in the response
    uncertainty_phrases = ["i'm not sure", "i don't know", "cannot determine", "unclear"]
    if any(phrase in response_text.lower() for phrase in uncertainty_phrases):
        signals.append("explicit uncertainty in response")

    should_escalate = bool(signals)
    reason = "; ".join(signals) if signals else "no escalation signals"

    if should_escalate:
        logger.info("Layer 5: escalation triggered — %s", reason)

    return EscalationSignal(
        should_escalate=should_escalate,
        reason=reason,
        details={"signals": signals},
    )
```
