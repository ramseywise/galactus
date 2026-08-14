"""Deterministic signal detection for dimension dispatch, plus the injection scan.

Regex-based, no LLM calls. Two jobs:

- `detect_signals` / `active_dimensions` decide which of the eleven dimensions
  run, and record the skipped ones *with reasons* — a dispatch table that omits
  what did not run cannot be mandatory-complete.
- `detect_injection` scans reviewed files for injection-shaped content. Its
  output is evidence in the brief *and* rung 0's second conjunct.

Ported from `guacamayo/review/signals.py`, dropping `is_pipeline_code` and its
two pattern lists — no dimension in the eleven-way menu consumes it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from review.models import REPORTER_ID_PREFIX

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

# The two tracks a work item can route to. The single place a track name is
# enumerated — a second list would be a second answer to "what tracks exist".
_TRACKS = ("ml", "agent")

# Prose patterns for doc-level track detection. These are deliberately *not*
# paraphrases of the import lists above: an import already has a pattern, and
# restating it here in prose form would put two definitions of "ML code" in one
# module. Every entry is a phrase that appears in a design doc and has no import
# equivalent.
_ML_DOC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"train[/ ]test split",
        r"target leakage",
        r"feature engineering",
        r"class imbalance",
        r"cross[- ]validation",
        r"baseline metric",
        r"\bAUC\b",
        r"\bRMSE\b",
        r"\btabular\b",
        r"\bdataframe\b",
    )
]
_AGENT_DOC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"tool call",
        r"system prompt",
        r"context window",
        r"agent loop",
        r"\bretrieval\b",
        r"eval harness",
        r"\bMCP\b",
        r"LangGraph",
        r"\bADK\b",
        r"\bsubagent\b",
    )
]

# Mirrors the hook's tolerant `Status:` form (`plan_status_validate.sh:30`).
# Bold and leading-whitespace variants both occur in the corpus, and two
# different notions of "a Track: line" between hook and router is exactly the
# drift this must not introduce.
_TRACK_RE = re.compile(r"^[ \t]*(?:\*\*)?Track(?:\*\*)?:[ \t]*(.*)$", re.MULTILINE)

# Fenced code blocks inside a doc, so the *import* lists can be reused against
# a doc's code rather than paraphrased into prose patterns.
_FENCE_RE = re.compile(r"```.*?\n(.*?)```", re.DOTALL)

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
        re.compile(r"(^|[^A-Za-z])(SYSTEM|ADMIN|SYSTEM_OVERRIDE)\s*[:>]", re.IGNORECASE),
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
        re.compile(r"(report|flag|return|find)\s+(no|nothing|none|zero)\b", re.IGNORECASE),
    ),
    (
        "preaudited_claim",
        re.compile(
            r"\b(pre-?audited|already\s+(reviewed|audited|approved)|no\s+need\s+to\s+review)\b",
            re.IGNORECASE,
        ),
    ),
]

# The seven dimensions that run on every review. The remaining four
# (`runtime`, `safeguards`, `leakage`, `contracts`) are conditional, gated by
# three signals in `active_dimensions` — agent code activates two of them.
_ALWAYS_ON = [
    "intent",
    "correctness",
    "silent_failure",
    "testing",
    "safety",
    "architecture",
    "performance",
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


def _count_distinct(text: str, patterns: list[re.Pattern]) -> int:
    """How many *distinct* patterns hit — not how many times any one of them did.

    Ten occurrences of `dataframe` is one piece of evidence repeated, not ten;
    counting matches instead of patterns would let a single keyword reach the
    two-signal confidence bar on its own.
    """
    return sum(1 for p in patterns if p.search(text))


def _doc_scan(doc_text: str) -> tuple[int, int]:
    """Score a doc for each track: (ml_hits, agent_hits), distinct patterns.

    Prose is scanned with the doc pattern lists; fenced code blocks are scanned
    with the *import* lists that `detect_signals` already owns, so a doc that
    pastes `from sklearn...` is read with the same definition of "ML code" the
    file-level detector uses.
    """
    code = "\n".join(_FENCE_RE.findall(doc_text))

    ml = _count_distinct(doc_text, _ML_DOC_PATTERNS)
    agent = _count_distinct(doc_text, _AGENT_DOC_PATTERNS)

    if code:
        ml += _count_distinct(code, _ML_IMPORT_PATTERNS)
        agent += _count_distinct(code, _AGENT_IMPORT_PATTERNS)

    return ml, agent


def detect_track(
    doc_text: str | None = None,
    files: list[str] | None = None,
    repo_root: str = ".",
) -> dict[str, object]:
    """Classify a work item as the `ml` or `agent` track.

    Four-level precedence: `declared` (a `Track:` line in the doc) → `doc`
    (keyword scan) → `files` (`detect_signals`) → `default`.

    **The router abstains rather than guesses.** When `confidence` is `"low"`,
    `track` is `None` — not the fallback. A caller that reads only `track` gets
    nothing usable and so cannot silently consume an inference; the fallback is
    reported separately as `default_track`, which a caller must name explicitly
    to use. The abstention rule lives in the return shape rather than in a
    downstream skill's prose because an instruction is the weakest enforcement
    layer available (`CLAUDE.md`: hook > linter > test > instruction), and a
    router that quietly defaults is worse than no router — its callers cannot
    tell inference from a coin flip.

    Tie-break at the `doc` and `files` levels: both signals true → `ml` wins.
    Asymmetric cost (`agent-uncertainty.md` §asymmetric cost) — routing ML work
    to the agent track skips leakage discipline, which is the expensive
    direction to get wrong.

    Returns `track`, `source`, `confidence`, `reason`, and `default_track`.
    """
    if doc_text:
        declared = _TRACK_RE.search(doc_text)
        if declared:
            value = declared.group(1).strip()
            token = value.split()[0] if value.split() else ""
            if token.lower() in _TRACKS:
                return {
                    "track": token.lower(),
                    "source": "declared",
                    "confidence": "high",
                    "reason": f"declared 'Track: {token.lower()}' in the doc",
                    "default_track": "agent",
                }

        ml_hits, agent_hits = _doc_scan(doc_text)
        if ml_hits or agent_hits:
            # Tie-break: both present → ml.
            track = "ml" if ml_hits >= agent_hits and ml_hits else "agent"
            hits = ml_hits if track == "ml" else agent_hits
            # Fewer than two *distinct* patterns is one keyword, which is not
            # evidence of a track — it is evidence of a word.
            if hits < 2:
                return {
                    "track": None,
                    "source": "doc",
                    "confidence": "low",
                    "reason": (
                        f"only {hits} distinct doc pattern(s) matched "
                        f"(ml={ml_hits}, agent={agent_hits}); too thin to classify"
                    ),
                    "default_track": "agent",
                }
            return {
                "track": track,
                "source": "doc",
                "confidence": "high",
                "reason": f"doc keyword scan: ml={ml_hits}, agent={agent_hits}",
                "default_track": "agent",
            }

    if files:
        signals = detect_signals(files, repo_root=repo_root)
        if signals["is_ml_code"] or signals["is_agent_code"]:
            track = "ml" if signals["is_ml_code"] else "agent"
            return {
                "track": track,
                "source": "files",
                "confidence": "high",
                "reason": (
                    f"file signals: is_ml_code={signals['is_ml_code']}, "
                    f"is_agent_code={signals['is_agent_code']}"
                ),
                "default_track": "agent",
            }

    return {
        "track": None,
        "source": "default",
        "confidence": "low",
        "reason": "no doc or file signal",
        "default_track": "agent",
    }


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

    # Mandatory-complete, enforced rather than intended. `_ALWAYS_ON` and the
    # branches above name dimensions as bare strings, so a dimension added to
    # `Reporter` but forgotten here would appear in neither list — vanishing
    # from the dispatch table with no skip reason, which is indistinguishable
    # from a dimension that ran clean. That is the one failure this function's
    # two-halves contract exists to prevent, so it fails loudly here instead.
    covered = set(active) | set(skipped)
    expected = {r.value for r in REPORTER_ID_PREFIX}
    if covered != expected:
        raise AssertionError(
            "active_dimensions must account for every registered dimension; "
            f"unaccounted: {sorted(expected - covered)}, "
            f"unregistered: {sorted(covered - expected)}"
        )

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
