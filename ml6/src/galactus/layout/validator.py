"""The deterministic layout-contract validator.

This is the centre of the design. The LLM's job is content; counting words is a
job for code. Nothing here calls a model, and nothing here is probabilistic:
given a draft and a template, the set of violations is a pure function of the
two.

Every violation carries a natural-language `repair_hint` that is fed back to the
model in the repair loop (Step 6), and structured `actual`/`limit` fields so the
prompt builder does not have to parse prose.
"""

from __future__ import annotations

import re

from galactus.models import FieldConstraint, LayoutTemplate, Violation

PLACEHOLDER_RE = re.compile(r"^\{\{[a-z0-9_]+\}\}$")
"""Image placeholder tokens look like `{{hero_image}}` — never a URL or a path."""

_HEX_LITERAL_RE = re.compile(r"^#?[0-9a-fA-F]{3,8}$")

_WORD_RE = re.compile(r"\S+")


def count_words(text: str) -> int:
    """Count whitespace-delimited words.

    One definition, used by the validator, the fallback, and the prompt builder
    alike — so that "9 words" means the same thing in all three.
    """
    return len(_WORD_RE.findall(text))


def validate(draft: dict[str, str], template: LayoutTemplate) -> list[Violation]:
    """Return every way `draft` breaches `template`. Empty list means it fits.

    Reports all violations rather than raising on the first: the repair loop
    needs the full set in one round-trip, or each extra violation costs another
    LLM call.
    """
    violations: list[Violation] = []

    for field in template.fields:
        value = draft.get(field.name)

        if value is None:
            violations.append(
                Violation(
                    field=field.name,
                    constraint="required",
                    repair_hint=(
                        f"Field '{field.name}' is missing and must be provided."
                    ),
                )
            )
            continue

        if field.kind == "text":
            violations.extend(_check_text(field.name, value, field))
        elif field.kind == "image_placeholder":
            violations.extend(_check_image_placeholder(field.name, value))
        elif field.kind == "color_ref":
            violations.extend(_check_color_ref(field.name, value, template))

    violations.extend(_check_unknown_fields(draft, template))
    return violations


def is_valid(draft: dict[str, str], template: LayoutTemplate) -> bool:
    """True when the draft satisfies the contract completely."""
    return not validate(draft, template)


# ---------------------------------------------------------------------------
# Per-kind checks
# ---------------------------------------------------------------------------


def _check_text(name: str, value: str, field: FieldConstraint) -> list[Violation]:
    violations: list[Violation] = []
    words = count_words(value)

    if field.max_words is not None and words > field.max_words:
        violations.append(
            Violation(
                field=name,
                constraint="max_words",
                actual=words,
                limit=field.max_words,
                repair_hint=(
                    f"Shorten '{name}' from {words} to at most {field.max_words} words."
                ),
            )
        )

    if field.min_words is not None and words < field.min_words:
        violations.append(
            Violation(
                field=name,
                constraint="min_words",
                actual=words,
                limit=field.min_words,
                repair_hint=(
                    f"Expand '{name}' from {words} to at least "
                    f"{field.min_words} words — short text leaves awkward "
                    f"whitespace in the layout."
                ),
            )
        )

    if field.max_chars is not None and len(value) > field.max_chars:
        violations.append(
            Violation(
                field=name,
                constraint="max_chars",
                actual=len(value),
                limit=field.max_chars,
                repair_hint=(
                    f"Shorten '{name}' from {len(value)} to at most "
                    f"{field.max_chars} characters."
                ),
            )
        )

    return violations


def _check_image_placeholder(name: str, value: str) -> list[Violation]:
    if PLACEHOLDER_RE.match(value):
        return []
    return [
        Violation(
            field=name,
            constraint="image_placeholder",
            actual=value,
            limit="{{snake_case_token}}",
            repair_hint=(
                f"Field '{name}' must be a placeholder token like "
                f"'{{{{{name}}}}}', not a URL, path, or description. "
                f"Images are supplied by the layout engine, not the model."
            ),
        )
    ]


def _check_color_ref(
    name: str, value: str, template: LayoutTemplate
) -> list[Violation]:
    if value in template.theme_colors:
        return []

    known = ", ".join(sorted(template.theme_colors))
    if _HEX_LITERAL_RE.match(value):
        hint = (
            f"Field '{name}' must name a theme color, not a literal value like "
            f"{value!r}. Choose one of: {known}."
        )
    else:
        hint = f"Field '{name}' must be one of the theme colors: {known}."

    return [
        Violation(
            field=name,
            constraint="color_ref",
            actual=value,
            limit=known,
            repair_hint=hint,
        )
    ]


def _check_unknown_fields(
    draft: dict[str, str], template: LayoutTemplate
) -> list[Violation]:
    unknown = sorted(set(draft) - template.field_names)
    return [
        Violation(
            field=name,
            constraint="unknown_field",
            actual=name,
            repair_hint=(
                f"Field '{name}' is not part of the "
                f"'{template.template_id}' template and must be removed."
            ),
        )
        for name in unknown
    ]
