"""Constrained generation: LLM content, deterministic contract.

The flow this module implements is the centre of the design:

    LLM generates -> schema constrains shape -> deterministic validator checks
    fit -> bounded repair loop -> deterministic truncation fallback

Each stage narrows what can go wrong, and the last one cannot fail. The schema
gets the *shape* right (the correct nine keys, all strings, nothing extra). The
validator gets the *fit* right (word and character limits). Neither trusts the
other, because they cannot: JSON Schema can express `maxLength`, but structured
outputs do not enforce string-length or numeric bounds — the Python SDK strips
those keywords before the request and checks them client-side. So the limits are
carried three ways, and only the third is binding:

  - in the schema, as documentation for a reader of the request;
  - in the prompt prose, where the model can actually act on them;
  - in `layout.validator`, which is what decides.

That is why the repair loop exists rather than a single well-specified call.
"""

from __future__ import annotations

from typing import Any

from galactus.ml6.src.galactus.layout.fallback import fallback
from galactus.ml6.src.galactus.layout.validator import validate
from galactus.ml6.src.galactus.llm.port import LLM
from galactus.ml6.src.galactus.models import Fact, LayoutTemplate, PipelineState, Violation
from galactus.ml6.src.galactus.obs import OP_GENERATE, OP_REPAIR, span

DEFAULT_MAX_REPAIRS = 3
"""Repair attempts before falling back.

Bounded because an unbounded loop is an unbounded bill and an unbounded
latency. Three is empirical headroom, not a guess at convergence: the violations
handed back are precise and mechanical ("shorten from 27 to at most 22 words"),
so a model that cannot satisfy them in three tries is not converging, and a
fourth call is unlikely to differ from the third.
"""


def schema_for(template: LayoutTemplate) -> dict[str, Any]:
    """Build a JSON Schema for a draft of `template`.

    Constrains shape only. Every field is a required string, and
    `additionalProperties: false` closes the object — structured outputs enforce
    both, which removes the `required` and `unknown_field` violation classes
    from the repair loop's normal workload before the first call.

    Character ceilings are emitted as `maxLength` even though the SDK strips
    them from the outbound request. They cost nothing, they document the
    contract at the point a reader looks for it, and if the API ever honours
    them the schema is already correct. Word counts have no JSON Schema
    equivalent at all, so they live only in the prompt and the validator.
    """
    properties: dict[str, Any] = {}

    for field in template.fields:
        prop: dict[str, Any] = {
            "type": "string",
            "description": _field_description(field),
        }
        if field.kind == "text":
            if field.max_chars is not None:
                prop["maxLength"] = field.max_chars
        properties[field.name] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": [field.name for field in template.fields],
        "additionalProperties": False,
    }


def build_prompt(state: PipelineState, template: LayoutTemplate) -> str:
    """Build the first-pass generation prompt.

    Carries three things the schema cannot: the numeric limits in a form the
    model can act on, the grounding facts, and the rule that content must come
    from those facts rather than from the model's own knowledge.
    """
    sections = [
        "You are writing marketing collateral that must fit a fixed page "
        "layout. The layout is not negotiable: text that exceeds its limits "
        "overflows the page and the piece is unusable.",
        "",
        f"# Layout: {template.template_id}",
        template.description,
        "",
        "# Fields",
        _render_field_specs(template),
    ]

    if state.prompt:
        sections += ["", "# Brief", state.prompt]

    facts = _render_facts(state)
    if facts:
        sections += [
            "",
            "# Source facts",
            "Every factual claim must come from these. Do not introduce "
            "figures, dates, names, or claims that are not here.",
            "",
            facts,
        ]

    sections += [
        "",
        "# Rules",
        "- Respect every word and character limit exactly. Count before you "
        "answer.",
        "- Image fields take a placeholder token such as `{{hero_image}}` — "
        "never a URL, path, or description. The layout engine supplies the "
        "image.",
        "- Color fields name one of the theme colors listed above — never a "
        "hex value.",
        "- Return only the JSON object.",
    ]

    return "\n".join(sections)


def build_repair_prompt(
    draft: dict[str, str], violations: list[Violation], template: LayoutTemplate
) -> str:
    """Build a prompt that asks for a targeted fix to `draft`.

    Sends the whole draft back rather than the offending fields alone. Fields
    are not independent — shortening a column changes how it balances against
    the other one — and a model editing in isolation produces a draft that fits
    the contract but reads as though it was assembled from parts.

    The violations carry their own `repair_hint`; this function does not
    re-derive the arithmetic, it forwards it.
    """
    lines = [
        "The draft below breaks the layout contract. Fix every listed problem "
        "and return the complete corrected JSON object.",
        "",
        "# Problems",
    ]
    lines += [f"- {v.repair_hint}" for v in violations]
    lines += [
        "",
        "# Current draft",
        _render_draft(draft),
        "",
        "# Rules",
        "- Return every field, not only the corrected ones.",
        "- Preserve the meaning and the source facts. Fixing length is an "
        "editing task, not a rewriting task — and never invent content to "
        "reach a minimum.",
        "- Do not break a limit that is currently satisfied while fixing one "
        "that is not.",
        "- Return only the JSON object.",
    ]

    return "\n".join(lines)


async def generate_collateral(
    state: PipelineState,
    template: LayoutTemplate,
    llm: LLM,
    max_repairs: int = DEFAULT_MAX_REPAIRS,
    model: str = "unknown",
) -> tuple[dict[str, str], bool]:
    """Generate a contract-valid draft. Always succeeds.

    Calls the model once, then re-prompts with the specific violations until the
    draft fits or the repair budget runs out. When the budget runs out the
    deterministic fallback truncates and pads the last draft into compliance, so
    the return value satisfies the contract unconditionally.

    `state` is mutated to record what happened — `draft`, `violations`,
    `repair_attempts`, `used_fallback` — because those counters are the eval
    metrics (contract pass rate, repair convergence, fallback rate), and
    reconstructing them after the fact is not possible.

    Args:
        state: Pipeline state, carrying the brief and the grounding facts.
        template: The layout contract to satisfy.
        llm: Any `port.LLM` implementation.
        max_repairs: Repair attempts before falling back.
        model: Model name recorded on the spans. Passed in rather than read off
            the port, which is deliberately narrow enough not to expose it.

    Returns:
        `(draft, used_fallback)`. `used_fallback` True means the draft fits but
        was mechanically degraded, and the caller must not present it as
        undegraded work.

    Raises:
        LLMError: If a provider call fails outright. A non-conforming draft is
            not an error; a dead provider is.
    """
    schema = schema_for(template)

    with span(OP_GENERATE, model, job_id=state.job_id, stage="generate", attempt=0):
        draft = await llm.complete_structured(build_prompt(state, template), schema)

    violations = validate(draft, template)
    state.first_pass_valid = not violations

    while violations and state.repair_attempts < max_repairs:
        state.repair_attempts += 1
        with span(
            OP_REPAIR,
            model,
            job_id=state.job_id,
            stage="repair",
            attempt=state.repair_attempts,
            violation_count=len(violations),
        ):
            draft = await llm.complete_structured(
                build_repair_prompt(draft, violations, template), schema
            )
        violations = validate(draft, template)

    state.draft = draft
    state.violations = violations

    if violations:
        # Budget exhausted with the contract still broken. The fallback is
        # guaranteed to produce a valid draft, so the endpoint never fails —
        # it degrades, and says so.
        state.draft = fallback(draft, template)
        state.used_fallback = True
        return state.draft, True

    state.used_fallback = False
    return draft, False


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


def _field_description(field: Any) -> str:
    """One field's spec as a single line, limits included.

    The template's own `description` is layout-grounded ("Overflow wraps to two
    lines and pushes the columns off the page") and explains *why* a limit
    exists, which reads as a better instruction than the bare number.
    """
    parts = [field.description] if field.description else []

    if field.kind == "text":
        limits = []
        if field.min_words is not None and field.max_words is not None:
            limits.append(f"{field.min_words}-{field.max_words} words")
        elif field.max_words is not None:
            limits.append(f"at most {field.max_words} words")
        elif field.min_words is not None:
            limits.append(f"at least {field.min_words} words")
        if field.max_chars is not None:
            limits.append(f"at most {field.max_chars} characters")
        if limits:
            parts.append(f"Limit: {', '.join(limits)}.")

    return " ".join(parts)


def _render_field_specs(template: LayoutTemplate) -> str:
    lines = []
    for field in template.fields:
        lines.append(f"- `{field.name}` ({field.kind}): {_field_description(field)}")

    colors = ", ".join(f"`{name}`" for name in template.theme_colors)
    lines.append("")
    lines.append(f"Theme colors (name one, do not use a hex value): {colors}")
    return "\n".join(lines)


def _render_facts(state: PipelineState) -> str:
    """Render the grounding facts, labelled by side.

    Sender and receiver facts are kept apart. Collateral about a partnership
    attributes claims to one party or the other, and a flat list invites the
    model to mix them.
    """
    blocks = []
    for label, facts in (
        ("Sender", state.sender_facts),
        ("Receiver", state.receiver_facts),
    ):
        if facts:
            blocks.append(f"## {label}")
            blocks += [_render_fact(fact) for fact in facts]
    return "\n".join(blocks)


def _render_fact(fact: Fact) -> str:
    # `page` is optional, and a fact without one rendered as the literal "pNone"
    # is a citation the model reads and can echo. No page means no citation.
    if fact.page is None:
        return f"- {fact.text}"
    return f"- {fact.text} (source: p{fact.page})"


def _render_draft(draft: dict[str, str]) -> str:
    return "\n".join(f"- `{name}`: {value!r}" for name, value in draft.items())
