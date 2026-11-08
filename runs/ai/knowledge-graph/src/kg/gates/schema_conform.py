"""Gate 3: entity types and relation exist in the pack, and domain/range are satisfied.

A relation domain or range of `*` admits any entity type in the pack. Constraints stated
only in a relation's prose definition (e.g. instance-of linking two entities of the same
type) are the judge's to apply, not this gate's.
"""

from __future__ import annotations

from kg.contract import ANY_TYPE, Pack
from kg.models import Candidate, GateResult


def check(candidate: Candidate, pack: Pack) -> GateResult:
    for side, type_name in (("subject", candidate.subject_type), ("object", candidate.object_type)):
        if pack.entity(type_name) is None:
            return GateResult(False, f"{side} type {type_name!r} is not in pack {pack.name}")
    rel = pack.relation(candidate.relation)
    if rel is None:
        return GateResult(False, f"relation {candidate.relation!r} is not in pack {pack.name}")
    if rel.domain != ANY_TYPE and rel.domain != candidate.subject_type:
        return GateResult(
            False, f"{rel.name} needs a {rel.domain} subject, got {candidate.subject_type}"
        )
    if rel.range != ANY_TYPE and rel.range != candidate.object_type:
        return GateResult(
            False, f"{rel.name} needs a {rel.range} object, got {candidate.object_type}"
        )
    return GateResult(True, None)
