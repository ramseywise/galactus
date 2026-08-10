"""Deterministic signal detection for dimension dispatch, plus the injection scan.

Regex-based, no LLM calls. Two jobs:

- `detect_signals` / `active_dimensions` decide which of the ten dimensions
  run, and record the skipped ones *with reasons* — a dispatch table that omits
  what did not run cannot be mandatory-complete.
- `detect_injection` scans reviewed files for injection-shaped content. Its
  output is evidence in the brief *and* rung 0's second conjunct.

Ported from `guacamayo/review/signals.py`, dropping `is_pipeline_code` and its
two pattern lists — no dimension in the ten-way menu consumes it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Import patterns indicating LLM/agent framework usage
_AGENT_IMPORT_PATTERNS = [
    re.compile(r"from\s+anthropic\b"),
    re.compile(r"import\s+anthropic\b"),
    re.compile(r"from\s+openai\b"),
    re.compile(r"import\s+openai\b"),
    re.compile(r"from\s+langchain\b"),
    re.compile(r"import\s+langchain\b"),
    re.compile(r"from\s+langgraph\b"),
    re.compile(r"import\s+langgraph\b"),
    re.compile(r"from\s+google\.adk\b"),
    re.compile(r"import\s+google\.adk\b"),
    re.compile(r"from\s+claude_agent_sdk\b"),
    re.compile(r"import\s+claude_agent_sdk\b"),
    re.compile(r"from\s+anthropic\.types\b"),
]

# Path patterns indicating agent code location
_AGENT_PATH_PATTERNS = [
    re.compile(r"(?:^|/)agents/"),
    re.compile(r"(?:^|/)\w+_agent/"),
    re.compile(r"(?:^|/)prompts/"),
]

# Import patterns indicating tabular-ML code. Deliberately narrower than "any
# numeric library": numpy and matplotlib alone are not ML and would drag every
# plotting script into a leakage review.
_ML_IMPORT_PATTERNS = [
    re.compile(r"from\s+sklearn\b"),
    re.compile(r"import\s+sklearn\b"),
    re.compile(r"from\s+catboost\b"),
    re.compile(r"import\s+catboost\b"),
    re.compile(r"from\s+lightgbm\b"),
    re.compile(r"import\s+lightgbm\b"),
    re.compile(r"from\s+xgboost\b"),
    re.compile(r"import\s+xgboost\b"),
    re.compile(r"from\s+imblearn\b"),
    re.compile(r"import\s+imblearn\b"),
    re.compile(r"import\s+pandas\b"),
    re.compile(r"from\s+pandas\b"),
]

# Call-shape patterns. An import list alone misses a module that receives an
# already-built estimator and fits it — which is exactly where fit-before-split
# ordering lives.
_ML_CALL_PATTERNS = [
    re.compile(r"\.fit\s*\("),
    re.compile(r"\.fit_transform\s*\("),
    re.compile(r"\.predict(?:_proba)?\s*\("),
    re.compile(r"\btrain_test_split\s*\("),
]

# Path patterns indicating ML code location.
_ML_PATH_PATTERNS = [
    re.compile(r"(?:^|/)ml/"),
    re.compile(r"(?:^|/)models/"),
    re.compile(r"(?:^|/)features/"),
    re.compile(r"(?:^|/)training/"),
]

# Injection-shaped content. This list is owned here, not borrowed: the four
# override-shaped patterns are the classic case, and the last three catch
# *scoped* poison, which does not override anything — it addresses a reviewer
# and asserts a state ("for the safety review", "pre-audited", "report
# nothing"). A list built only from override examples has that hole.
#
# The last two are individually loose and will hit this repo's own source and
# review prose. That is correct: this scan produces evidence, not a verdict, and
# rung 0 needs a hit *plus* an empty dispatch, so a lone false positive changes
# nothing. Do not add an allowlist, path filter, or confidence score to quiet
# it — each is a place to hide, and none is needed once the conjunction carries
# the weight.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "override_instructions",
        re.compile(
            r"(ignore|disregard)\s+(all\s+|any\s+)?(prior|previous|your)\s+instructions",
            re.IGNORECASE,
        ),
    ),
    (
        "instructions_void",
        re.compile(
            r"(prior|previous)\s+instructions\s+(are\s+)?(void|null|cancelled|revoked)",
            re.IGNORECASE,
        ),
    ),
    (
        "system_directive_in_comment",
        re.compile(
            r"(^|[^A-Za-z])(SYSTEM|ADMIN|SYSTEM_OVERRIDE)\s*[:>]", re.IGNORECASE
        ),
    ),
    ("empty_return_directive", re.compile(r"\breturn\s*\[\s*\]", re.IGNORECASE)),
    (
        "reviewer_addressed",
        re.compile(
            r"(for|to)\s+the\s+\w+(\s+and\s+\w+)?\s+(review|reviewer)s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "suppression_directive",
        re.compile(
            r"(report|flag|return|find)\s+(no|nothing|none|zero)\b", re.IGNORECASE
        ),
    ),
    (
        "preaudited_claim",
        re.compile(
            r"\b(pre-?audited|already\s+(reviewed|audited|approved)|no\s+need\s+to\s+review)\b",
            re.IGNORECASE,
        ),
    ),
]

# The six dimensions that run on every review, and the conditional four.
_ALWAYS_ON = [
    "intent",
    "correctness",
    "silent_failure",
    "testing",
    "safety",
    "architecture",
]


def _resolve(path_str: str, repo_root: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else Path(repo_root) / p


def _file_has_pattern(path: Path, patterns: list[re.Pattern]) -> bool:
    try:
        content = path.read_text(errors="replace")
        return any(p.search(content) for p in patterns)
    except OSError:
        return False


def detect_signals(files: list[str], repo_root: str = ".") -> dict[str, bool]:
    """Detect which conditional dimensions should activate for the given files.

    Returns:
        - is_agent_code: activate `runtime` + `safeguards`
        - is_ml_code: activate `leakage`
        - has_sanyi_contracts: SANYI.md present — activate `contracts`
    """
    is_agent_code = False
    is_ml_code = False

    for raw_path in files:
        path_str = raw_path.replace("\\", "/")

        if any(p.search(path_str) for p in _AGENT_PATH_PATTERNS):
            is_agent_code = True

        # Content-based import detection. The scan is content-based, so a lazy
        # import inside a function still counts.
        if (
            not is_agent_code
            and path_str.endswith((".py", ".ts", ".tsx", ".js"))
            and _file_has_pattern(_resolve(path_str, repo_root), _AGENT_IMPORT_PATTERNS)
        ):
            is_agent_code = True

        # ML detection is content-first and Python-only. A path match alone is
        # not enough: `ml/README.md` and `models/schema.sql` live under matching
        # directories and contain no fit path to review. Requiring content means
        # a false activation needs an actual ML import or call in the file.
        if not is_ml_code and path_str.endswith(".py"):
            resolved = _resolve(path_str, repo_root)
            if _file_has_pattern(resolved, _ML_IMPORT_PATTERNS) or (
                any(p.search(path_str) for p in _ML_PATH_PATTERNS)
                and _file_has_pattern(resolved, _ML_CALL_PATTERNS)
            ):
                is_ml_code = True

    return {
        "is_agent_code": is_agent_code,
        "is_ml_code": is_ml_code,
        "has_sanyi_contracts": _find_sanyi_md(repo_root),
    }


def _find_sanyi_md(repo_root: str) -> bool:
    root = Path(repo_root).resolve()
    for candidate in [root / "SANYI.md", root / ".claude" / "SANYI.md"]:
        if candidate.exists():
            return True
    try:
        result = subprocess.run(
            ["git", "ls-files", "SANYI.md", ".claude/SANYI.md"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
        return bool(result.stdout.strip())
    except OSError:
        return False


def active_dimensions(signals: dict[str, bool]) -> dict[str, object]:
    """Return the dimensions to dispatch *and* the ones skipped, with reasons.

    A function that returns only what ran cannot populate a dispatch table that
    is mandatory-complete, which is the point of returning both halves here
    rather than letting the orchestrator infer the complement.
    """
    active = list(_ALWAYS_ON)
    skipped: dict[str, str] = {}

    if signals.get("is_agent_code"):
        active.extend(["runtime", "safeguards"])
    else:
        reason = "no agent-framework import or agent path in the changed files"
        skipped["runtime"] = reason
        skipped["safeguards"] = reason

    if signals.get("is_ml_code"):
        active.append("leakage")
    else:
        # Recorded rather than omitted, and this dimension is the case that
        # motivated the rule: a leakage reporter that silently never runs is
        # indistinguishable from one that ran and found nothing — which is the
        # exact failure `leakage` exists to catch, turned on the dispatcher.
        skipped["leakage"] = "no ML import, fit call, or ML path in the changed files"

    if signals.get("has_sanyi_contracts"):
        active.append("contracts")
    else:
        skipped["contracts"] = "no SANYI.md in the repo"

    return {"active": active, "skipped": skipped}


def detect_injection(files: list[str], repo_root: str = ".") -> list[dict]:
    """Scan files for injection-shaped content, per line.

    Returns one record per match: `file`, `line`, `pattern_name`,
    `matched_text`. These are tool-verified evidence for the brief and rung 0's
    required second input — never a verdict on their own.
    """
    hits: list[dict] = []
    for raw_path in files:
        path_str = raw_path.replace("\\", "/")
        try:
            content = _resolve(path_str, repo_root).read_text(errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            for name, pattern in _INJECTION_PATTERNS:
                match = pattern.search(line)
                if match:
                    hits.append(
                        {
                            "file": path_str,
                            "line": lineno,
                            "pattern_name": name,
                            "matched_text": match.group(0),
                        }
                    )
    return hits
