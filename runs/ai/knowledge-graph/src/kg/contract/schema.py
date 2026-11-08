"""Pack schema, canonical hash, and a loader that refuses drift.

The pack is the contract between the proposer, the gates and the judge: which entity and
relation types exist, what each means, and where its boundary lies. It is hashed over a
canonical JSON form so a one-character edit to any definition or boundary example changes
the hash, and everything downstream (approval, builds, records) pins that hash.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ANY_TYPE = "*"
"""A relation domain or range of `*` admits any entity type in the pack."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EntityType(_Strict):
    name: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9]*$")
    definition: str = Field(min_length=1)
    boundary_examples: list[str] = Field(min_length=1)


class RelationType(_Strict):
    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    definition: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    range: str = Field(min_length=1)
    boundary_examples: list[str] = Field(min_length=1)


class Pack(_Strict):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    entity_types: list[EntityType] = Field(min_length=1)
    relation_types: list[RelationType] = Field(min_length=1)

    @field_validator("entity_types", "relation_types")
    @classmethod
    def _unique_names(cls, v: list[EntityType] | list[RelationType]) -> list:
        names = [t.name for t in v]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate type names: {dupes}")
        return v

    @model_validator(mode="after")
    def _relations_reference_known_types(self) -> Pack:
        known = {e.name for e in self.entity_types} | {ANY_TYPE}
        for r in self.relation_types:
            for side in ("domain", "range"):
                if getattr(r, side) not in known:
                    raise ValueError(
                        f"relation {r.name!r} {side} {getattr(r, side)!r} is not an entity type"
                    )
        return self

    def entity(self, name: str) -> EntityType | None:
        return next((e for e in self.entity_types if e.name == name), None)

    def relation(self, name: str) -> RelationType | None:
        return next((r for r in self.relation_types if r.name == name), None)


class PackDrift(ValueError):  # noqa: N818 — name fixed by the plan
    """The pack on disk does not hash to the value it was pinned at."""

    def __init__(self, *, expected: str, actual: str) -> None:
        super().__init__(f"pack drift: expected sha256 {expected}, got {actual}")
        self.expected = expected
        self.actual = actual


def canonical_json(pack: Pack) -> str:
    return json.dumps(pack.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def pack_hash(pack: Pack) -> str:
    """sha256 over canonical JSON (sorted keys, no whitespace), hex."""
    return hashlib.sha256(canonical_json(pack).encode("utf-8")).hexdigest()


def load_pack(path: Path, expected_hash: str | None = None) -> Pack:
    pack = Pack.model_validate_json(path.read_text(encoding="utf-8"))
    actual = pack_hash(pack)
    if expected_hash is not None and actual != expected_hash:
        raise PackDrift(expected=expected_hash, actual=actual)
    return pack
