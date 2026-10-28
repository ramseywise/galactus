"""Confidence signal for retrieval — informational only in this starter (not
gating/escalation). A real project can route on this in retrieve.py once it has
somewhere to route to (a clarifying question, a fallback tool, a human handoff)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfidenceSignal:
    top_score: float | None  # None = no retrieval results at all

    @property
    def is_confident(self) -> bool:
        return self.top_score is not None

    def score(self, *, threshold: float) -> float:
        """Return a 0-1 confidence score: 0.0 with no results, else the raw top
        similarity score (already 0-1 range for normalized embeddings) with values
        below ``threshold`` reported as-is — the caller decides what to do with a
        low score, this function just measures it."""
        if self.top_score is None:
            return 0.0
        return self.top_score
