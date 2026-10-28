"""Generic case-file loading for the generation-under-contract harness.

This is the case-agnostic half of what a real case type needs: reading a
JSONL file into rows, skipping blanks, rejecting duplicate ids, and
defaulting difficulty. The case-specific half — the fields a domain's
contract actually needs (e.g. source facts, a template id) — lives in the
consumer, which builds its own dataclass on top of this loader's shape.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CaseRow:
    """The generic fields every case row carries, before a consumer adds its own.

    A consumer's case type is not required to subclass this — `load_case_rows`
    hands back plain dicts (via `from_dict`) so a consumer can build whatever
    dataclass its domain needs from the same JSONL shape.
    """

    case_id: str
    difficulty: str = "medium"


def load_case_rows[T](
    path: Path,
    from_dict: Callable[[dict[str, Any]], T],
) -> list[T]:
    """Read a JSONL case file, skipping blank lines, and reject duplicate ids.

    `from_dict` is the consumer's own row parser — it decides which fields
    beyond `case_id`/`difficulty` a row carries. This function only owns the
    file-format contract: one JSON object per non-blank line, and no two rows
    may share a `case_id`.
    """
    rows = [from_dict(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    _reject_duplicate_ids(rows, path)
    return rows


def _reject_duplicate_ids(rows: Iterable[Any], path: Path) -> None:
    ids = [row.case_id for row in rows]
    duplicates = {case_id for case_id in ids if ids.count(case_id) > 1}
    if duplicates:
        raise ValueError(f"duplicate case_id in {path.name}: {sorted(duplicates)}")
