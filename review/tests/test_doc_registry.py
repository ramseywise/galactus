"""The other half of the cross-artifact test: the *docs* must agree with the code.

`test_prefix_map.py` binds the skill tree to `models.py`. It does not read the
orchestrator or the shared schema reference, and that gap has a track record:
`review-performance` was registered in `models.py`, `signals.py`, and the skill
tree while `proto-review/SKILL.md` still said "ten dimensions" and omitted
`performance` from both of its tables, and `finding-schema.md` omitted it from
the prefix table. The suite stayed green throughout. The gap was found by hand,
fixed by hand, and left open — so the next dimension re-ran it: the fix for
`performance` did not add the `leakage` row that was *also* missing from §11,
and `finding-schema.md`'s `reporter:` enum was missing both.

Registration touches five sites. `models.py` is authoritative; `test_prefix_map.py`
covers the skill tree; this file covers the remaining three:

1. `proto-review/SKILL.md` Stage 3 — the dispatch table the orchestrator acts on.
2. `proto-review/SKILL.md` Stage 7 §11 — the mandatory-complete accounting table.
3. `review-shared/references/finding-schema.md` — the `reporter:` enum and the
   prefix table a reporter reads its own contract from.

A dimension missing from (1) is never dispatched. Missing from (2) it is dropped
from the only artifact a human reads — indistinguishable from a clean result,
which is precisely what that table exists to prevent. Missing from (3) its
findings are rejectable against a spec that contradicts itself.

These are markdown tables rather than code, so the parsing is deliberately loose:
the assertion is on the *set of dimension names present*, never on formatting.
"""

from __future__ import annotations

import re
from pathlib import Path

from review.models import REPORTER_ID_PREFIX

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

ORCHESTRATOR = SKILLS_DIR / "proto-review" / "SKILL.md"
SCHEMA_REF = SKILLS_DIR / "review-shared" / "references" / "finding-schema.md"

# Dimension names as the docs spell them: underscored, matching Reporter values.
_DIMENSIONS = {r.value for r in REPORTER_ID_PREFIX}


def _section(text: str, start_marker: str, end_marker: str) -> str:
    """Slice between two literal markers; empty string when either is absent."""
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    return text[start : end if end != -1 else len(text)]


def _leading_cells(section: str) -> set[str]:
    """First cell of every markdown table row in `section`, normalized.

    Skill names are hyphenated where Reporter values are underscored, so
    `silent-failure` and `silent_failure` both normalize to `silent_failure`.
    """
    cells: set[str] = set()
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        first = stripped.split("|")[1].strip()
        # Skip separator rows (`|---|`) and header rows.
        if not first or set(first) <= {"-", ":"}:
            continue
        cells.add(first.strip("`").removeprefix("review-").replace("-", "_"))
    return cells


def test_stage3_dispatch_table_covers_every_dimension():
    """The table the orchestrator dispatches from. A dimension absent here is
    registered everywhere else and still never runs."""
    section = _section(
        ORCHESTRATOR.read_text(),
        "The eleven dimensions, their files under `review-shared/dimensions/`, and what activates each:",
        "### Recording dispatch outcomes",
    )
    assert section, "Stage 3 dispatch table not found — did its heading change?"
    missing = _DIMENSIONS - _leading_cells(section)
    assert not missing, f"dimensions missing from the Stage 3 dispatch table: {sorted(missing)}"


def test_stage7_accounting_table_covers_every_dimension():
    """§11 is mandatory-complete by its own prose. A missing row is the silent
    omission the table exists to prevent."""
    section = _section(
        ORCHESTRATOR.read_text(),
        "## 11. Dimension Dispatch Table",
        "**All eleven dimensions get a row",
    )
    assert section, "Stage 7 §11 table not found — did its heading change?"
    missing = _DIMENSIONS - _leading_cells(section)
    assert not missing, f"dimensions missing from the Stage 7 §11 table: {sorted(missing)}"


def test_schema_reference_prefix_table_matches_models():
    """The prefix table claims to mirror REPORTER_ID_PREFIX. Hold it to that —
    both directions, and on the prefixes, not just the names."""
    section = _section(SCHEMA_REF.read_text(), "## Dimension prefixes", "The `wander` agent")
    assert section, "prefix table not found in finding-schema.md"

    declared: dict[str, str] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in stripped.split("|")[1:-1]]
        if len(cells) != 3 or set(cells[0]) <= {"-", ":"} or cells[0] == "Dimension":
            continue
        declared[cells[0].replace("-", "_")] = cells[2]

    expected = {r.value: prefix for r, prefix in REPORTER_ID_PREFIX.items()}
    assert declared == expected


def test_schema_reference_reporter_enum_covers_every_dimension():
    """The `reporter:` enum in the schema block is what a dispatch reads to learn
    which value it may emit. A dimension absent from it has its own findings
    rejected by `validate.py` against a file that contradicts its prefix table."""
    text = SCHEMA_REF.read_text()
    match = re.search(r"^reporter:(.*?)^category:", text, re.MULTILINE | re.DOTALL)
    assert match, "`reporter:` enum not found in the finding-schema.md schema block"

    listed = {v.strip() for v in match.group(1).replace("|", " ").split() if v.strip()}
    missing = _DIMENSIONS - listed
    assert not missing, f"dimensions missing from the `reporter:` enum: {sorted(missing)}"
