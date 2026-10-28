"""Shared verdict schema every judge must return (score + reasoning + dimensions)."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field


class JudgeVerdict(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    is_correct: bool
    reasoning: str = ""
    dimensions: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_response_text(cls, text: str) -> JudgeVerdict:
        """Parse a judge's raw response into a verdict.

        Tolerates markdown code fences around the JSON. Extra numeric keys the
        judge returned beyond the schema are folded into ``dimensions``.
        """
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
        parsed = json.loads(raw)
        known = {"score", "is_correct", "reasoning", "dimensions"}
        dimensions = dict(parsed.get("dimensions", {}))
        for key, value in parsed.items():
            if key not in known and isinstance(value, (int, float)) and not isinstance(value, bool):
                dimensions[key] = float(value)
        return cls(
            score=float(parsed.get("score", 0.0)),
            is_correct=bool(parsed.get("is_correct", float(parsed.get("score", 0.0)) >= 0.7)),
            reasoning=str(parsed.get("reasoning", "")),
            dimensions=dimensions,
        )
