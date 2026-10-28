"""The dry-run adapter — a scripted provider with a real, non-degenerate spread.

This is the first-class requirement of the generation harness (see
CLAUDE.md's rationale on the eval kind this extends). Deliberately not a
stub returning one canned draft: it reads the requested limits off each
field and produces text that mostly fits, overshooting on cases whose
difficulty says they should fight the contract — so a dry run exercises the
clean path, the repair path, and the fallback path rather than reporting a
perfect score against a fixture that could never fail.

Repair calls tighten toward the limit, which is what a real model does when
handed a specific violation. A `stubborn=True` case never tightens, so the
repair budget runs out and the fallback engages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

from .ports import FieldSpec

LOREM: list[str] = [
    "meridian",
    "calder",
    "partnership",
    "shipments",
    "corridor",
    "network",
    "delivery",
    "freight",
    "logistics",
    "carriers",
    "routing",
    "terminals",
    "capacity",
    "coverage",
    "performance",
    "operations",
    "customers",
    "enterprise",
    "regional",
    "volume",
    "reliability",
    "service",
]
"""Deterministic filler vocabulary. Indexing is `i % len(LOREM)` — no
randomness, so a dry run is byte-identical run over run."""


@dataclass(frozen=True)
class StressProfile:
    """Which fields a case's scripted provider actually breaches, and how.

    Without this every hard case would breach every field identically, and a
    run would report the same violations N times over — a spread that says
    nothing about whether the repair loop handles different breach classes
    differently.
    """

    stress_fields: frozenset[str] | None = None
    """`None` means every text field overshoots. A named set breaches only
    those fields, so a case that stresses one field does not also report
    violations on fields it never pressured."""
    bad_color: bool = False
    """Emit a hex literal where the contract requires a named reference."""
    stubborn: bool = False
    """Never tighten across repair calls, exhausting the repair budget."""


class GenerationCase(Protocol):
    """The two attributes the scripted-provider selector needs from a case."""

    case_id: str
    difficulty: str


class ScriptedProvider:
    """A fake provider that behaves like a plausible model, deterministically."""

    LOREM: ClassVar[list[str]] = LOREM

    def __init__(
        self,
        fields: list[FieldSpec],
        *,
        overshoot: bool,
        stubborn: bool,
        stress_fields: frozenset[str] | None = None,
        bad_color: bool = False,
    ) -> None:
        self.fields = fields
        self.overshoot = overshoot
        self.stubborn = stubborn
        self.stress_fields = stress_fields
        self.bad_color = bad_color
        self.calls = 0

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1

        # A repair prompt is the second call onward; the first is generation.
        repairing = self.calls > 1
        breaching = self.overshoot and (self.stubborn or not repairing)

        return {f.name: self._value_for(f, breaching=breaching) for f in self.fields}

    def _value_for(self, field_spec: FieldSpec, *, breaching: bool) -> str:
        if field_spec.kind == "image_placeholder":
            return f"{{{{{field_spec.name}}}}}"
        if field_spec.kind == "color_ref":
            # A hex literal where the contract requires a named theme color.
            return "#ff2d55" if breaching and self.bad_color else "accent"

        over = breaching and (self.stress_fields is None or field_spec.name in self.stress_fields)

        # Aim just inside the word ceiling, or past it when overshooting.
        ceiling = field_spec.max_words or 20
        floor = field_spec.min_words or 1
        count = ceiling + 6 if over else max(floor, ceiling - 1)

        words = [self.LOREM[i % len(self.LOREM)] for i in range(count)]
        text = " ".join(words).capitalize()

        # Respect max_chars on the non-overshooting path by dropping whole
        # words — a mid-word cut would be a truncation the model would not make.
        if not over and field_spec.max_chars is not None:
            while len(text) > field_spec.max_chars and " " in text:
                text = text.rsplit(" ", 1)[0]

        return text


def scripted_provider_for(
    case: GenerationCase,
    fields: list[FieldSpec],
    stress_profiles: dict[str, StressProfile],
) -> ScriptedProvider:
    """Give each case a scripted provider matched to its difficulty.

    Difficulty drives behaviour so the dry-run metrics have a real spread:
    easy and medium cases pass first time, hard cases need repair, and a
    stubborn case exhausts the budget. `stress_profiles` is an injected
    mapping rather than a module constant, because its keys name case ids
    that belong to the caller's case file, not to this harness.
    """
    profile = stress_profiles.get(case.case_id, StressProfile())
    return ScriptedProvider(
        fields,
        overshoot=case.difficulty == "hard",
        stubborn=profile.stubborn,
        stress_fields=profile.stress_fields,
        bad_color=profile.bad_color,
    )
