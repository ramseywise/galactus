"""Gate 4: one triple per canonical key `(subject_norm, relation, object_norm, page_path)`.

The same key is the store's write key, so re-running a page writes over its own triples
instead of adding copies (fog FA-006). First occurrence wins; later ones are returned as
duplicates so the caller can count them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from kg.models import Triple, TripleKey


@dataclass(frozen=True)
class DedupeResult:
    kept: list[Triple]
    duplicates: list[Triple]


def dedupe(triples: Iterable[Triple]) -> DedupeResult:
    seen: set[TripleKey] = set()
    kept: list[Triple] = []
    duplicates: list[Triple] = []
    for t in triples:
        if t.key in seen:
            duplicates.append(t)
        else:
            seen.add(t.key)
            kept.append(t)
    return DedupeResult(kept=kept, duplicates=duplicates)
