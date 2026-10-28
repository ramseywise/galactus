"""The cross-artifact test: skills and core must agree on the eleven prefixes.

Green since Step 7 of the prototyping-review-subsystem plan created the original
nine `review-*` skills; `review-leakage` made it ten, `review-performance` eleven.

`models.py` is authoritative and the skills follow it, never the reverse. This
test is what makes registration code rather than directory convention: adding a
`review-*` directory without its `Reporter` member and `REPORTER_ID_PREFIX`
entry turns it red, as does renaming one or picking a prefix the code does not
know about.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from review.models import REPORTER_ID_PREFIX

REPO_ROOT = Path(__file__).resolve().parents[2]
DIMENSIONS_DIR = REPO_ROOT / ".claude" / "skills" / "review-shared" / "dimensions"

# `prefix:` — that exact key, in the frontmatter. No Parallax skill has such a
# field, so it is an invention of this subsystem and needs pinning down.
_PREFIX_KEY = re.compile(r"^prefix:\s*([A-Z]{2})\s*$", re.MULTILINE)


def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[:end] if end != -1 else ""


def _declared_prefixes() -> dict[str, str]:
    """Map dimension name → declared prefix, read from each dimension file's frontmatter.

    Dimensions are reference files under review-shared/dimensions/, not skills.
    Supporting files there (review-contracts-violations.md) carry no frontmatter
    and are skipped. CROSS-band review skills (/review-defense) stay skills and
    never live in this directory.
    """
    found: dict[str, str] = {}
    for md in sorted(DIMENSIONS_DIR.glob("review-*.md")):
        frontmatter = _frontmatter(md.read_text())
        if not frontmatter:
            continue
        match = _PREFIX_KEY.search(frontmatter)
        # File names are hyphenated; Reporter values are underscored.
        # `silent-failure` → `silent_failure`.
        dimension = md.stem.removeprefix("review-").replace("-", "_")
        found[dimension] = match.group(1) if match else ""
    return found


def test_skill_set_matches_reporter_enum():
    declared = _declared_prefixes()
    if not declared:
        pytest.fail("no dimension files found under .claude/skills/review-shared/dimensions/")
    expected = {r.value for r in REPORTER_ID_PREFIX}
    assert set(declared) == expected


def test_declared_prefixes_match_models_exactly():
    declared = _declared_prefixes()
    if not declared:
        pytest.fail("no dimension files found under .claude/skills/review-shared/dimensions/")
    expected = {r.value: prefix for r, prefix in REPORTER_ID_PREFIX.items()}
    assert declared == expected


def test_prefixes_are_unique():
    """Two dimensions sharing a prefix would make the ID unable to identify
    which skill a dispatch loaded, which is what the prefix is for."""
    values = list(REPORTER_ID_PREFIX.values())
    assert len(values) == len(set(values))
