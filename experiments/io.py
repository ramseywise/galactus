"""Writing a `RunRecord` to disk so that loading it re-validates it.

The registry owns its on-disk format. Without this module, the first consumer
would write records with its own serializer and de-facto define the format one
layer below the schema that owns it — and the second consumer would fork it.

Two decisions carry the module:

**`NotApplicable` round-trips as a tagged object, never `null`.** The whole
point of the sentinel (see `record.NotApplicable`) is that "there is nothing
to record" and "forgot to record it" must not look identical on disk. A JSON
`null` is exactly that collapse. So an inapplicable field is written as
`{"not_applicable": {"reason": ...}}`, and a `null` found in an optional field
on load is rejected loudly.

**Loading reconstructs the frozen dataclasses, not dicts.** `read_record`
calls the real constructors, so `ExecutionConfig.__post_init__` and
`RunRecord.__post_init__` re-run on every load — a record edited by hand (or
written by a buggy foreign writer) into an invalid state fails at load, not
at the point downstream where its numbers are compared. `DataIdentity.columns`
is restored to a tuple: JSON has no tuple, and handing back a list would make
a loaded record compare unequal to the record that was saved.

Versioning follows the `ml/persistence.py` precedent: a `schema_version` field
in the payload, checked on load, raising `SchemaVersionError` on mismatch
rather than guessing at a migration.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.record import (
    CodeState,
    DataIdentity,
    ExecutionConfig,
    NotApplicable,
    RunRecord,
)

SCHEMA_VERSION = 1

_NOT_APPLICABLE_KEY = "not_applicable"


class SchemaVersionError(ValueError):
    """The record on disk was written under a different schema version.

    Raised instead of best-effort loading: a silently half-loaded record
    would be compared against fresh runs as if it were complete, which is
    the exact class of bug the registry exists to prevent.
    """


def _encode_optional(value: object) -> object:
    """A plain value passes through; `NotApplicable` becomes a tagged object."""
    if isinstance(value, NotApplicable):
        return {_NOT_APPLICABLE_KEY: {"reason": value.reason}}
    return value


def _decode_optional(value: object, field: str) -> object:
    """Invert `_encode_optional`, rejecting the states the schema rules out.

    A bare `null` is never valid for an optional field — on disk it is
    indistinguishable from "forgot to record it", which is the collapse the
    `NotApplicable` sentinel exists to prevent.
    """
    if value is None:
        raise ValueError(
            f"{field} is null in the record on disk — null is never a valid "
            "value for an optional field. A valid record carries either a "
            f'value or {{"{_NOT_APPLICABLE_KEY}": {{"reason": ...}}}}.'
        )
    if isinstance(value, dict):
        if set(value) != {_NOT_APPLICABLE_KEY} or not isinstance(value[_NOT_APPLICABLE_KEY], dict):
            raise ValueError(
                f"{field} carries an unrecognized object {value!r} — expected "
                f'a plain value or {{"{_NOT_APPLICABLE_KEY}": {{"reason": ...}}}}.'
            )
        return NotApplicable(reason=str(value[_NOT_APPLICABLE_KEY]["reason"]))
    return value


def write_record(record: RunRecord, path: Path | str) -> Path:
    """Write `record` as versioned JSON. Returns the path written.

    `resolved_config` must be JSON-serializable — an unserializable value
    raises rather than being coerced with `default=str`, because a config
    that silently stringifies on write no longer round-trips to the values
    that produced the numbers.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_kind": record.run_kind,
        "headline_metric": record.headline_metric,
        "metrics": dict(record.metrics),
        "code": {
            "git_sha": _encode_optional(record.code.git_sha),
            "dirty": record.code.dirty,
            "versions": dict(record.code.versions),
        },
        "data": {
            "frame_hash": record.data.frame_hash,
            "n_rows": record.data.n_rows,
            "n_cols": record.data.n_cols,
            "columns": list(record.data.columns),
            "source_hash": _encode_optional(record.data.source_hash),
        },
        "execution": {
            "seed": _encode_optional(record.execution.seed),
            "resolved_config": record.execution.resolved_config,
            "folds": _encode_optional(record.execution.folds),
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_record(path: Path | str) -> RunRecord:
    """Load a record, reconstructing the frozen dataclasses so they re-validate.

    Raises `SchemaVersionError` on a version mismatch, `ValueError` when the
    payload violates the schema's invariants (a `null` optional field, a
    headline metric absent from `metrics`), and `KeyError` when a required
    field is missing outright.
    """
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SchemaVersionError(
            f"record at {path} has schema_version {version!r}, this reader "
            f"expects {SCHEMA_VERSION}. Refusing to guess at a migration — "
            "a half-loaded record would be compared as if it were complete."
        )

    code_payload = payload["code"]
    code = CodeState(
        git_sha=_decode_optional(code_payload["git_sha"], "code.git_sha"),
        dirty=code_payload["dirty"],
        versions=dict(code_payload["versions"]),
    )

    data_payload = payload["data"]
    data = DataIdentity(
        frame_hash=data_payload["frame_hash"],
        n_rows=data_payload["n_rows"],
        n_cols=data_payload["n_cols"],
        columns=tuple(data_payload["columns"]),
        source_hash=_decode_optional(data_payload["source_hash"], "data.source_hash"),
    )

    execution_payload = payload["execution"]
    execution = ExecutionConfig(
        seed=_decode_optional(execution_payload["seed"], "execution.seed"),
        resolved_config=execution_payload["resolved_config"],
        folds=_decode_optional(execution_payload["folds"], "execution.folds"),
    )

    return RunRecord(
        code=code,
        data=data,
        execution=execution,
        metrics=dict(payload["metrics"]),
        headline_metric=payload["headline_metric"],
        run_kind=payload["run_kind"],
    )
