"""Approval record bound to a pack hash.

Nothing builds against an unapproved pack. Approval is a human act recorded next to the
pack as `<stem>.approval.json` = `{pack_hash, approved_by, approved_at}`; editing the pack
after approval changes its hash, and `require_approved` then refuses it until a person
approves the new hash.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kg.contract.schema import Pack, load_pack, pack_hash


class NotApproved(RuntimeError):  # noqa: N818 — name fixed by the plan
    """The pack has no approval record, or the record is for a different hash."""


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_by: str = Field(min_length=1)
    approved_at: datetime


def approval_path(pack_path: Path) -> Path:
    return pack_path.with_name(f"{pack_path.stem}.approval.json")


def approve(pack_path: Path, approved_by: str, *, now: datetime | None = None) -> ApprovalRecord:
    """Validate the pack and write its approval record. `approved_by` names a person."""
    if not approved_by.strip():
        raise ValueError("approved_by must name the person approving the pack")
    pack = load_pack(pack_path)
    record = ApprovalRecord(
        pack_hash=pack_hash(pack),
        approved_by=approved_by.strip(),
        approved_at=now or datetime.now(UTC),
    )
    approval_path(pack_path).write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return record


def require_approved(pack: Pack, pack_path: Path) -> ApprovalRecord:
    """Return the approval record for `pack`, or raise `NotApproved` naming why."""
    path = approval_path(pack_path)
    if not path.exists():
        raise NotApproved(f"pack {pack.name} v{pack.version} has no approval record at {path}")
    record = ApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))
    actual = pack_hash(pack)
    if record.pack_hash != actual:
        raise NotApproved(
            f"pack {pack.name} v{pack.version} hashes to {actual}, but the approval record "
            f"at {path} is for {record.pack_hash}; re-approve after reviewing the change"
        )
    return record
