"""The pack contract: canonical hash, drift refusal, strict schema, approval bound to hash."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from kg.contract import (
    NotApproved,
    Pack,
    PackDrift,
    approval_path,
    approve,
    load_pack,
    pack_hash,
    require_approved,
)

PACKS = Path(__file__).resolve().parents[1] / "packs"
EVAL_PACK = PACKS / "eval-v1.json"


@pytest.fixture
def pack_file(tmp_path: Path) -> Path:
    dst = tmp_path / "eval-v1.json"
    dst.write_text(EVAL_PACK.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def _mutate(path: Path, fn) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    fn(raw)
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")


def test_shipped_pack_validates() -> None:
    pack = load_pack(EVAL_PACK)
    assert {e.name for e in pack.entity_types} == {
        "Metric",
        "Method",
        "Artifact",
        "FailureMode",
        "Tool",
        "Role",
    }
    assert {r.name for r in pack.relation_types} == {
        "measures",
        "mitigates",
        "requires",
        "produces",
        "contradicts",
        "instance-of",
    }


def test_hash_is_stable_and_whitespace_insensitive(pack_file: Path) -> None:
    before = pack_hash(load_pack(pack_file))
    raw = json.loads(pack_file.read_text(encoding="utf-8"))
    pack_file.write_text(json.dumps(raw, separators=(",", ":")), encoding="utf-8")
    assert pack_hash(load_pack(pack_file)) == before
    assert len(before) == 64


def test_one_character_edit_changes_hash_and_old_hash_raises_drift(pack_file: Path) -> None:
    old = pack_hash(load_pack(pack_file))
    _mutate(
        pack_file,
        lambda r: r["entity_types"][0]["boundary_examples"].__setitem__(
            0, r["entity_types"][0]["boundary_examples"][0] + "!"
        ),
    )
    new = pack_hash(load_pack(pack_file))
    assert new != old
    with pytest.raises(PackDrift) as exc:
        load_pack(pack_file, expected_hash=old)
    assert exc.value.expected == old
    assert exc.value.actual == new


def test_matching_expected_hash_loads(pack_file: Path) -> None:
    h = pack_hash(load_pack(pack_file))
    assert load_pack(pack_file, expected_hash=h).name == "eval"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.__setitem__("owner", "someone"),
        lambda r: r["entity_types"][0].__setitem__("colour", "red"),
        lambda r: r["relation_types"][0].__setitem__("weight", 1),
    ],
)
def test_unknown_field_is_rejected(pack_file: Path, mutation) -> None:
    _mutate(pack_file, mutation)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_pack(pack_file)


def test_relation_must_reference_known_types(pack_file: Path) -> None:
    _mutate(pack_file, lambda r: r["relation_types"][0].__setitem__("domain", "Gadget"))
    with pytest.raises(ValidationError, match="Gadget"):
        load_pack(pack_file)


def test_duplicate_type_names_rejected(pack_file: Path) -> None:
    _mutate(pack_file, lambda r: r["entity_types"].append(dict(r["entity_types"][0])))
    with pytest.raises(ValidationError, match="duplicate"):
        load_pack(pack_file)


def test_require_approved_refuses_unapproved_pack(pack_file: Path) -> None:
    pack = load_pack(pack_file)
    with pytest.raises(NotApproved, match="no approval record"):
        require_approved(pack, pack_file)


def test_approval_binds_to_hash(pack_file: Path) -> None:
    at = datetime(2026, 11, 7, tzinfo=UTC)
    record = approve(pack_file, "tester", now=at)
    assert approval_path(pack_file).name == "eval-v1.approval.json"
    pack = load_pack(pack_file)
    assert require_approved(pack, pack_file) == record
    assert record.pack_hash == pack_hash(pack)

    _mutate(pack_file, lambda r: r.__setitem__("version", "1.1"))
    edited = load_pack(pack_file)
    with pytest.raises(NotApproved, match="re-approve"):
        require_approved(edited, pack_file)


def test_approve_requires_a_name(pack_file: Path) -> None:
    with pytest.raises(ValueError, match="approved_by"):
        approve(pack_file, "  ")


def test_approve_refuses_invalid_pack(pack_file: Path) -> None:
    _mutate(pack_file, lambda r: r.__setitem__("extra", True))
    with pytest.raises(ValidationError):
        approve(pack_file, "tester")
    assert not approval_path(pack_file).exists()


def test_pack_lookup_helpers() -> None:
    pack = load_pack(EVAL_PACK)
    assert isinstance(pack, Pack)
    assert pack.entity("Metric") is not None
    assert pack.relation("mitigates").range == "FailureMode"
    assert pack.entity("Nope") is None


def test_shipped_pack_approval_matches_if_present() -> None:
    """The committed approval record, once Ramsey writes it, must match the committed pack."""
    if not approval_path(EVAL_PACK).exists():
        pytest.skip("eval-v1 not yet approved: run the approve command in README.md")
    pack = load_pack(EVAL_PACK)
    assert require_approved(pack, EVAL_PACK).approved_by
