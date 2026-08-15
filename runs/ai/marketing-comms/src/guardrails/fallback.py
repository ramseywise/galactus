"""Deterministic last resort: always return something that fits the contract.

When the repair loop exhausts its budget the endpoint must still return valid
JSON. This module guarantees that — `validate(fallback(draft, template),
template)` is empty for any input draft, which is what makes the API's contract
unconditional rather than best-effort.

Truncation alone cannot deliver that guarantee: a draft can also be *under* a
word floor, missing a field, or carrying a bad color reference. So each
violation kind has a deterministic repair:

| Violation           | Repair                                                  |
|---------------------|---------------------------------------------------------|
| `max_words`         | drop trailing words, preferring a sentence boundary     |
| `max_chars`         | drop trailing words until under the character ceiling   |
| `min_words`         | pad with a neutral filler token                         |
| `required`          | synthesize a minimal value valid for the field's kind   |
| `unknown_field`     | remove the field                                        |
| `image_placeholder` | replace with `{{field_name}}`                           |
| `color_ref`         | replace with the template's first theme color           |

Every degradation is reported: `fallback_report()` returns the fields it
touched, and the caller sets `was_truncated` / `used_fallback` so the response
never claims undegraded quality.
"""

from __future__ import annotations

import re

from guardrails.validator import count_words, validate
from models import FieldConstraint, LayoutTemplate

FILLER_WORD = "and"
"""Neutral padding for under-length fields. Semantically empty by design — the
alternative is inventing content, which is a grounding violation, not a repair."""

_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def fallback(draft: dict[str, str], template: LayoutTemplate) -> dict[str, str]:
    """Return a contract-valid draft derived from `draft`.

    Never raises. The input is not mutated.
    """
    result: dict[str, str] = {}

    for field in template.fields:
        value = draft.get(field.name)
        if value is None:
            result[field.name] = _synthesize(field, template)
            continue

        if field.kind == "text":
            result[field.name] = _fit_text(value, field)
        elif field.kind == "image_placeholder":
            result[field.name] = _fit_placeholder(value, field)
        elif field.kind == "color_ref":
            result[field.name] = _fit_color_ref(value, template)

    # Unknown fields are dropped by construction: only template fields are copied.
    return result


def fallback_report(
    draft: dict[str, str], template: LayoutTemplate
) -> tuple[dict[str, str], list[str]]:
    """Run `fallback` and report which fields were changed.

    Returns:
        `(repaired_draft, changed_field_names)`. A caller that gets a non-empty
        change list must mark the response as degraded.
    """
    repaired = fallback(draft, template)
    changed = sorted(
        name for name in set(repaired) | set(draft) if draft.get(name) != repaired.get(name)
    )
    return repaired, changed


def was_degraded(draft: dict[str, str], template: LayoutTemplate) -> bool:
    """True if `draft` would need any repair to satisfy the contract."""
    return bool(validate(draft, template))


# ---------------------------------------------------------------------------
# Text fitting
# ---------------------------------------------------------------------------


def _fit_text(value: str, field: FieldConstraint) -> str:
    """Bring `value` within this field's word and character limits.

    Order matters. Truncation runs first, then padding — but truncating to the
    character ceiling can itself drop the word count below the floor (one
    300-character word becomes one 70-character word, under a 3-word minimum).
    So when a floor exists, the character cut reserves room for the filler the
    padding step will need.
    """
    text = value.strip()

    if field.max_words is not None and count_words(text) > field.max_words:
        text = _truncate_to_words(text, field.max_words)

    if field.max_chars is not None and len(text) > field.max_chars:
        text = _truncate_to_chars(text, field.max_chars - _padding_reserve(text, field))

    if field.min_words is not None and count_words(text) < field.min_words:
        text = _pad_to_words(text, field.min_words, field)

    return text


def _padding_reserve(text: str, field: FieldConstraint) -> int:
    """Characters to hold back from the char cut so padding can reach the floor.

    Zero unless the field has a word floor that the text is at risk of falling
    under once truncated. Reserves one filler token per word still needed.
    """
    if field.min_words is None or field.max_chars is None:
        return 0

    # Words that survive a naive character cut, as a lower bound on what padding
    # will have to make up.
    surviving = count_words(_truncate_to_chars(text, field.max_chars))
    shortfall = field.min_words - surviving
    if shortfall <= 0:
        return 0

    return min(
        shortfall * (len(FILLER_WORD) + 1),
        max(0, field.max_chars - len(FILLER_WORD)),
    )


_BOUNDARY_RETENTION = 0.25
"""A sentence cut must keep at least this fraction of the allowed words.

Ending mid-clause looks careless, so a sentence boundary is preferred — but only
when it does not gut the field. At 0.25 a 22-word pull quote will cut back to a
clean 6-word sentence, while a 95-word column will not collapse to a stray
two-word opener.
"""


def _truncate_to_words(text: str, max_words: int) -> str:
    """Keep at most `max_words` words, preferring to end at a sentence boundary."""
    words = text.split()
    clipped = " ".join(words[:max_words])

    boundaries = [m.end() for m in _SENTENCE_END_RE.finditer(clipped)]
    if boundaries:
        candidate = clipped[: boundaries[-1]].strip()
        if count_words(candidate) >= max(1, int(max_words * _BOUNDARY_RETENTION)):
            return candidate

    return clipped.rstrip(",;:- ")


def _truncate_to_chars(text: str, max_chars: int) -> str:
    """Trim to `max_chars`, never splitting a word.

    Falls back to a hard character cut only when the first word alone exceeds
    the ceiling.
    """
    if len(text) <= max_chars:
        return text

    words = text.split()
    kept: list[str] = []
    for word in words:
        candidate = " ".join([*kept, word])
        if len(candidate) > max_chars:
            break
        kept.append(word)

    if not kept:
        return text[:max_chars]

    return " ".join(kept).rstrip(",;:- ")


def _pad_to_words(text: str, min_words: int, field: FieldConstraint) -> str:
    """Pad up to `min_words` with filler, without breaking the character ceiling.

    If padding cannot fit under `max_chars`, the character ceiling wins: it is
    the constraint that actually breaks the layout, whereas a short field only
    leaves whitespace. `_fit_text` cannot satisfy both in that case, and
    `validate` would still flag it — so templates must leave room for their own
    floors. `test_no_template_field_has_an_unsatisfiable_range` asserts the
    shipped template does.
    """
    words = text.split() if text.strip() else []
    while len(words) < min_words:
        candidate = [*words, FILLER_WORD]
        if field.max_chars is not None and len(" ".join(candidate)) > field.max_chars:
            break
        words = candidate
    return " ".join(words)


# ---------------------------------------------------------------------------
# Non-text kinds
# ---------------------------------------------------------------------------


def _synthesize(field: FieldConstraint, template: LayoutTemplate) -> str:
    """Build a minimal valid value for a field that the draft omitted."""
    if field.kind == "image_placeholder":
        return _placeholder_token(field.name)
    if field.kind == "color_ref":
        return _first_theme_color(template)
    return _pad_to_words("", field.min_words or 0, field)


def _fit_placeholder(value: str, field: FieldConstraint) -> str:
    from guardrails.validator import PLACEHOLDER_RE

    if PLACEHOLDER_RE.match(value):
        return value
    return _placeholder_token(field.name)


def _placeholder_token(field_name: str) -> str:
    return f"{{{{{field_name}}}}}"


def _fit_color_ref(value: str, template: LayoutTemplate) -> str:
    if value in template.theme_colors:
        return value
    return _first_theme_color(template)


def _first_theme_color(template: LayoutTemplate) -> str:
    """The template's first theme color, or `""` if it declares none.

    A template with a `color_ref` field and an empty `theme_colors` is
    malformed, and nothing today ships that way. But this runs inside the one
    path that must not fail, and an unguarded `next(iter(...))` would raise
    `StopIteration` there — turning a malformed template into a failed request
    at the exact moment the fallback exists to prevent one. `""` is not valid
    against such a template either, so `validate` still reports it; the
    difference is a reported violation instead of an exception.
    """
    return next(iter(template.theme_colors), "")
