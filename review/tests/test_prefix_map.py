"""The cross-artifact test: skills and core must agree on the nine prefixes.

DESIGNED RED until Step 7 of the prototyping-review-subsystem plan creates the
nine `review-*` skills. That is the dependency made checkable rather than
asserted in prose — Step 7's completion is what turns this green.

`models.py` is authoritative and the skills follow it, never the reverse. This
test fails loudly if Step 7 adds a tenth skill, renames one, or picks a prefix
the code does not know about.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from review.models import REPORTER_ID_PREFIX

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# `prefix:` — that exact key, in the frontmatter. No Parallax skill has such a
# field, so it is an invention of this subsystem and needs pinning down.
_PREFIX_KEY = re.compile(r"^prefix:\s*([A-Z]{2})\s*$", re.MULTILINE)

# `review-shared` matches the glob but carries no dimension — it is the brief
# every dispatch loads alongside its one dimension skill.
_NON_DIMENSION_SKILLS = {"review-shared"}


def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[:end] if end != -1 else ""


def _declared_prefixes() -> dict[str, str]:
    """Map skill dimension name → declared prefix, read from SKILL.md frontmatter."""
    found: dict[str, str] = {}
    for skill_dir in sorted(SKILLS_DIR.glob("review-*")):
        if skill_dir.name in _NON_DIMENSION_SKILLS:
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        match = _PREFIX_KEY.search(_frontmatter(skill_md.read_text()))
        # Skill names are hyphenated (the loader rejects underscores); Reporter
        # values are underscored. `silent-failure` → `silent_failure`.
        dimension = skill_dir.name.removeprefix("review-").replace("-", "_")
        found[dimension] = match.group(1) if match else ""
    return found


def test_skill_set_matches_reporter_enum():
    declared = _declared_prefixes()
    if not declared:
        pytest.fail(
            "no .claude/skills/review-*/SKILL.md files found — expected until "
            "Step 7 of the prototyping-review-subsystem plan lands"
        )
    expected = {r.value for r in REPORTER_ID_PREFIX}
    assert set(declared) == expected


def test_declared_prefixes_match_models_exactly():
    declared = _declared_prefixes()
    if not declared:
        pytest.fail(
            "no .claude/skills/review-*/SKILL.md files found — expected until "
            "Step 7 of the prototyping-review-subsystem plan lands"
        )
    expected = {r.value: prefix for r, prefix in REPORTER_ID_PREFIX.items()}
    assert declared == expected


def test_prefixes_are_unique():
    """Two dimensions sharing a prefix would make the ID unable to identify
    which skill a dispatch loaded, which is what the prefix is for."""
    values = list(REPORTER_ID_PREFIX.values())
    assert len(values) == len(set(values))
