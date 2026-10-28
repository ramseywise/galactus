"""Stall detection for the LangGraph agent loop.

Detects repeated identical tool calls or outputs and escalates by raising
``StallDetectedError``.  Wire into a LangGraph node or after-step callback
to catch infinite loops before hitting the recursion limit.

Usage (in a custom node or step hook)::

    from agents.{{ lg_agent_dir }}.stall_detector import StallDetector, StallDetectedError

    detector = StallDetector(threshold=3)

    # After each tool call:
    try:
        detector.record_tool_call(tool_name, tool_input)
    except StallDetectedError as exc:
        # escalate / terminate
        raise

    # After each LLM output:
    try:
        detector.record_output(answer_text)
    except StallDetectedError as exc:
        raise
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from typing import Any

log = logging.getLogger(__name__)

_STALL_THRESHOLD_DEFAULT = 3


class StallDetectedError(RuntimeError):
    """Raised when repeated identical tool calls or outputs are detected."""

    def __init__(self, kind: str, key: str, count: int) -> None:
        self.kind = kind
        self.key = key
        self.count = count
        super().__init__(
            f"Stall detected: {kind} repeated {count}x — key={key!r}. "
            "Terminating loop to prevent infinite recursion."
        )


def _fingerprint(data: Any) -> str:
    """Stable, collision-resistant fingerprint for any JSON-serialisable value."""
    try:
        serialised = json.dumps(data, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialised = str(data)
    return hashlib.sha256(serialised.encode()).hexdigest()[:16]


class StallDetector:
    """Track tool calls and LLM outputs within a single agent run.

    Parameters
    ----------
    threshold:
        Number of identical observations that constitutes a stall.
        Defaults to 3, matching the acceptance criterion.
    """

    def __init__(self, threshold: int = _STALL_THRESHOLD_DEFAULT) -> None:
        if threshold < 2:
            raise ValueError(f"threshold must be >= 2, got {threshold}")
        self.threshold = threshold
        self._tool_calls: Counter[str] = Counter()
        self._outputs: Counter[str] = Counter()

    def record_tool_call(self, tool_name: str, tool_input: Any) -> None:
        """Record a tool invocation; raise ``StallDetectedError`` if stalled.

        Parameters
        ----------
        tool_name:
            Name of the tool being called.
        tool_input:
            The input dict/value passed to the tool.  Fingerprinted so
            different inputs with the same tool name are counted separately.
        """
        key = f"{tool_name}:{_fingerprint(tool_input)}"
        self._tool_calls[key] += 1
        count = self._tool_calls[key]
        log.debug("stall-detector tool_call key=%s count=%d", key, count)
        if count >= self.threshold:
            log.warning("stall-detector STALL tool_call key=%s count=%d", key, count)
            raise StallDetectedError("tool_call", key, count)

    def record_output(self, output: str) -> None:
        """Record an LLM output; raise ``StallDetectedError`` if stalled.

        Parameters
        ----------
        output:
            The text output from the LLM.  Fingerprinted before counting so
            whitespace normalisation is the caller's responsibility.
        """
        key = _fingerprint(output)
        self._outputs[key] += 1
        count = self._outputs[key]
        log.debug("stall-detector output key=%s count=%d", key, count)
        if count >= self.threshold:
            log.warning("stall-detector STALL output key=%s count=%d", key, count)
            raise StallDetectedError("output", key, count)

    def reset(self) -> None:
        """Clear all counters — call between outer verification-loop attempts."""
        self._tool_calls.clear()
        self._outputs.clear()
