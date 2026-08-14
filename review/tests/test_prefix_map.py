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
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# `prefix:` — that exact key, in the frontmatter. No Parallax skill has such a
# field, so it is an invention of this subsystem and needs pinning down.
_PREFIX_KEY = re.compile(r"^prefix:\s*([A-Z]{2})\s*$", re.MULTILINE)

# `review-shared` matches the glob but carries no dimension — it is the brief
# every dispatch loads alongside its one dimension skill.
_NON_DIMENSION_SKILLS = {"review-shared"}

# CROSS-band skills (`/review-defense`) also match the glob. They attack an
# artifact and return a judgment rather than reporting findings against a diff,
# so they have no `Reporter` member and no prefix. They declare `job:`; the
# dimension skills do not, so the key is the discriminator — a new CROSS skill
# is excluded by construction rather than by being added to a list here.
_JOB_KEY = re.compile(r"^job:\s*\S+", re.MULTILINE)


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
        frontmatter = _frontmatter(skill_md.read_text())
        if _JOB_KEY.search(frontmatter):
            continue
        match = _PREFIX_KEY.search(frontmatter)
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
