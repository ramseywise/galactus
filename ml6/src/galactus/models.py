"""Typed state model threaded through the pipeline.

No graph framework: the DAG lives in function composition, and this module is
the state those functions pass along. See docs/DESIGN.md (Step 10) for the DAG.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FieldKind = Literal["text", "image_placeholder", "color_ref"]
"""Constraint kinds the validator dispatches on.

Extensible by design: a `max_rendered_px` kind for true typographic fitting is
one more arm here plus one more check in the validator (see plan Risks).
"""

ConstraintName = Literal[
    "required",
    "max_words",
    "min_words",
    "max_chars",
    "unknown_field",
    "color_ref",
    "image_placeholder",
]
"""Machine-readable violation kinds. The repair prompt keys off these."""

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class FieldConstraint(BaseModel):
    """One field of a layout template, and the limits it imposes."""

    model_config = ConfigDict(extra="forbid")

    name: str
    max_words: int | None = None
    min_words: int | None = None
    max_chars: int | None = None
    kind: FieldKind = "text"
    description: str = ""

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field name must not be blank")
        return v

    def model_post_init(self, _context: object, /) -> None:
        if (
            self.max_words is not None
            and self.min_words is not None
            and self.min_words > self.max_words
        ):
            raise ValueError(
                f"field {self.name!r}: min_words ({self.min_words}) "
                f"exceeds max_words ({self.max_words})"
            )


class LayoutTemplate(BaseModel):
    """The layout contract. Everything generated is validated against this."""

    model_config = ConfigDict(extra="forbid")

    template_id: str
    description: str = ""
    fields: list[FieldConstraint]
    theme_colors: dict[str, str]

    @field_validator("fields")
    @classmethod
    def _fields_unique_and_nonempty(
        cls, v: list[FieldConstraint]
    ) -> list[FieldConstraint]:
        if not v:
            raise ValueError("template must declare at least one field")
        names = [f.name for f in v]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate field names: {sorted(duplicates)}")
        return v

    @field_validator("theme_colors")
    @classmethod
    def _colors_are_hex(cls, v: dict[str, str]) -> dict[str, str]:
        bad = {k: val for k, val in v.items() if not _HEX_COLOR.match(val)}
        if bad:
            raise ValueError(f"theme colors must be hex (#rgb or #rrggbb): {bad}")
        return v

    def field_by_name(self, name: str) -> FieldConstraint | None:
        return next((f for f in self.fields if f.name == name), None)

    @property
    def field_names(self) -> set[str]:
        return {f.name for f in self.fields}


class Violation(BaseModel):
    """One contract breach, carrying enough structure to drive a repair prompt.

    Deliberately a returned value rather than a raised exception: the repair
    loop needs every violation in one round-trip, not the first one.
    """

    model_config = ConfigDict(extra="forbid")

    field: str
    constraint: ConstraintName
    repair_hint: str
    actual: int | str | None = None
    limit: int | str | None = None


class Fact(BaseModel):
    """An extracted claim with provenance, for the grounding path (Step 7)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    source_span: str
    page: int | None = None
    confidence: float = 1.0
    origin: Literal["text", "vision", "table"] = "text"
    """Which extraction path produced this fact, and so how it gets verified.

    `text` spans must read back exactly; `table` spans must contain every value
    the row asserts (the row is rephrased to keep its subject, so exact match is
    impossible); `vision` has no span to check. See `ingest.facts.verify_facts`.
    """


class PipelineState(BaseModel):
    """State threaded through the pipeline for one collateral request."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    prompt: str = ""
    sender_facts: list[Fact] = Field(default_factory=list)
    receiver_facts: list[Fact] = Field(default_factory=list)
    draft: dict[str, str] | None = None
    violations: list[Violation] = Field(default_factory=list)
    repair_attempts: int = 0
    used_fallback: bool = False
    first_pass_valid: bool | None = None
    """Whether the very first generation satisfied the contract.

    Recorded separately because the repair loop overwrites `violations` on every
    attempt, and contract pass rate is measured *before* any repair. Once the
    loop has run, the first attempt's verdict is not reconstructable from the
    other counters — a run with `repair_attempts == 0` could equally be a clean
    first pass or a run given no repair budget. None means generation has not
    run yet.
    """
