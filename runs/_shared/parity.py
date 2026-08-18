"""Run-agnostic record helpers — written once, consumed by every run.

Three things, each here because it was otherwise duplicated or advisory:

- `_tagged` — `NotApplicable` → JSON-native tagged dict, needed inside
  `resolved_config` (which `experiments.io` passes through without coercion).
- `_toolkit_code_state` — provenance of the ML toolkit tree.
- `persist` — the single enforcing chokepoint into `runs/_index/`. A dry-run
  never writes there; enforced against the resolved target so no caller can
  opt out by constructing its own path.
"""

from __future__ import annotations

import os
from pathlib import Path

from experiments.io import _NOT_APPLICABLE_KEY, write_record
from experiments.provenance import capture_code_state
from experiments.record import NotApplicable, RunRecord

GALACTUS_ROOT = Path(__file__).resolve().parents[2]
INDEX_ROOT = GALACTUS_ROOT / "runs" / "_index"


def _tagged(value: str | NotApplicable) -> object:
    """`resolved_config` is a plain-JSON pass-through — a raw `NotApplicable`
    nested inside it would fail `write_record`. Encode in the registry's own
    tagged form so the toolkit entry round-trips."""
    if isinstance(value, NotApplicable):
        return {_NOT_APPLICABLE_KEY: {"reason": value.reason}}
    return value


def toolkit_code_state() -> dict[str, object]:
    """Provenance of the ML toolkit tree.

    When `ML_PACKAGE_ROOT` is set, fingerprints that external tree. Otherwise
    fingerprints the galactus repo itself (ml/ and experiments/ are first-party).
    """
    toolkit_root = os.environ.get("ML_PACKAGE_ROOT")
    if toolkit_root:
        state = capture_code_state(repo=Path(toolkit_root))
        return {
            "root": toolkit_root,
            "git_sha": _tagged(state.git_sha),
            "dirty": state.dirty,
        }
    state = capture_code_state(repo=GALACTUS_ROOT)
    return {
        "root": str(GALACTUS_ROOT / "ml"),
        "git_sha": _tagged(state.git_sha),
        "dirty": state.dirty,
    }


def persist(record: RunRecord, *, dry_run: bool, target: Path) -> Path:
    """The one chokepoint into `runs/_index/`.

    A dry-run never writes there — enforced against the resolved target, so no
    caller can opt out by constructing its own path.
    """
    resolved = target.resolve()
    if dry_run and (resolved == INDEX_ROOT.resolve() or INDEX_ROOT.resolve() in resolved.parents):
        raise ValueError(f"dry-run may not write under {INDEX_ROOT}: {resolved}")
    return write_record(record, target)
