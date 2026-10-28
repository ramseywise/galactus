"""Language heuristic: does the response language match what the user needs?

Stopword-overlap detection — no dependencies, good enough for the coarse
"answered in English to a Spanish question" failure this metric exists to
catch. Extend _STOPWORDS for the languages your users actually speak.
"""

from __future__ import annotations

import re

from evals.models import EvalInteraction, GraderResult

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset({"the", "and", "is", "to", "of", "you", "for", "with", "that", "your"}),
    "es": frozenset({"el", "la", "los", "las", "que", "de", "para", "con", "una", "es", "tu"}),
    "fr": frozenset({"le", "la", "les", "des", "est", "pour", "avec", "vous", "une", "et"}),
    "de": frozenset({"der", "die", "das", "und", "ist", "für", "mit", "eine", "nicht", "sie"}),
    "pt": frozenset({"o", "os", "as", "que", "para", "com", "uma", "não", "é", "você"}),
}

_WORD_RE = re.compile(r"[a-zà-ÿ]+")


def detect_language(text: str) -> str | None:
    words = _WORD_RE.findall(text.lower())
    if not words:
        return None
    scores = {lang: sum(1 for w in words if w in sw) for lang, sw in _STOPWORDS.items()}
    best = max(scores, key=lambda lang: scores[lang])
    return best if scores[best] > 0 else None


def grade(interaction: EvalInteraction) -> GraderResult | None:
    expected = interaction.expected_language or detect_language(interaction.query)
    if expected is None:
        return None
    detected = detect_language(interaction.response)
    if detected is None:
        return None
    correct = detected == expected
    return GraderResult(
        interaction_id=interaction.id,
        metric="language",
        grader="heuristic",
        is_correct=correct,
        score=1.0 if correct else 0.0,
        reasoning=f"detected={detected!r} vs expected={expected!r}",
        dimensions={"language_match": float(correct)},
    )
