#!/usr/bin/env python3
"""
validate_paths.py — bidirectional path sweep for ai-project-template.

Static analysis (default):
  - Parse copier.yaml _tasks entries and extract every path they reference
    under _scaffold/ or .claude/ or mcp_servers/ or .agents/.
  - Walk template/ recursively to build the full file/dir inventory.
  - Check that every _tasks path resolves to something in template/
    (substituting known variable defaults so {{ py_project_root }} → backend, etc.).
  - Check that every template/ directory under _scaffold/ and mcp_servers/ is
    reachable by at least one render configuration (no orphans — dirs that
    would survive as rendered output but are never addressed by _tasks).

Capabilities catalog check (--catalog-check):
  - Parse template/.claude/skills/add-capability/references/capabilities-catalog.md.
  - Extract every copier variable name the catalog references in `sets` / `requires`
    / `conflicts_with` cells.
  - Verify each var exists as a top-level key in copier.yaml.
  - Verify each file path referenced in `adds` cells resolves to something in template/
    (after substituting VAR_DEFAULTS).
  - Report uncovered vars: top-level copier.yaml keys (non-private, non-derived) that
    no capability entry references.

Render test (--render-test):
  - Runs copier copy across several option combinations into /tmp.
  - Asserts no {{ }} survives in any output path or file body.
  - Asserts no empty-named directories were created.

Usage:
  python scripts/validate_paths.py                      # static analysis only
  python scripts/validate_paths.py --catalog-check      # + catalog drift check
  python scripts/validate_paths.py --render-test        # + live renders

Exit codes:
  0  no findings
  1  one or more findings (report printed to stdout)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO_ROOT / "template"
COPIER_YAML = REPO_ROOT / "copier.yaml"

# Variable defaults used for static path resolution.
# These mirror the copier.yaml defaults for the "happy path" render.
# Override-aware: we substitute each variable with its default value so
# {{ py_project_root }}/{{ ai_source_root }}/... resolves to a real template path.
VAR_DEFAULTS: dict[str, str] = {
    "py_project_root": "backend",
    "ai_source_root": "src",
    "ml_source_root": "ml",
    "run_registry_root": "experiments",
    "eval_root": "evals",
    "ts_project_root": "my-project",
    "ts_source_root": "src",
    "lg_agent_dir": "lg_agent",
    "adk_agent_dir": "adk_agent",
    "ts_agent_dir": "chat_agent",
    "mcp_server_slug": "my-mcp-server",
    # py_mcp_server_slug/ts_mcp_server_slug default to mcp_server_slug when the
    # matching language is chosen, else mcp_server_slug + '__unchosen_*'.
    # We track both the "chosen" default and the "unchosen" suffix form so
    # reverse-substitution maps concrete unchosen paths back to the {{ var }} name.
    "py_mcp_server_slug": "my-mcp-server",
    "ts_mcp_server_slug": "my-mcp-server__unchosen_ts",
}

# Staging dirs that are legitimately ephemeral — they exist at render time but
# are moved/deleted by _tasks, so their absence in a rendered output is expected.
STAGING_PREFIXES = ("_scaffold",)

# Copier template variable pattern — {{ variable_name }}
JINJA_VAR_RE = re.compile(r"\{\{[^}]+\}\}")
# Matches CSS-style {{ }} blocks (contain `:` property syntax or `;`) — not Jinja expressions.
# Compiled once at module level; used in render-test body sweep.
_CSS_RE = re.compile(r"\{\{\s*[\w-]+(?:\s*:\s*[^}]+|[^}]*;[^}]*)\}\}")
# Python f-string brace escaping, not unrendered Jinja: inside an f-string `{{` and
# `}}` are the escapes for a literal brace, so `f"{{{{{expr}}}}}"` EMITS the text
# `{{value}}` — a placeholder the rendered code writes at runtime. JINJA_VAR_RE sees
# the doubled braces and can't tell the two apart, so the body sweep reported these
# as leftover template syntax on a clean render.
#
# The same false positive is filtered in .github/workflows/test-render.yml's "Check
# for leftover Jinja" step; keep the two in sync. Matching the escape *form* (an odd
# run of braces around a single expression) rather than whitelisting one literal line
# keeps this from rotting the moment that expression is renamed.
_FSTRING_BRACE_RE = re.compile(r"\{\{\{+[^{}]+\}\}\}+")

# Path fragment patterns that _tasks uses (rm, mv, cp, mkdir).
# We extract the path arguments after the command name.
# Matches a bare Jinja identifier used as concatenation operand: ~ var_name ~
JINJA_CONCAT_VAR_RE = re.compile(
    r"~\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*~|~\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*$|^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*~"
)


# ---------------------------------------------------------------------------
# YAML parsing helpers (stdlib only — no PyYAML fallback needed; we parse just
# enough to extract _tasks strings without executing Jinja).
# ---------------------------------------------------------------------------


def _load_yaml_raw(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_tasks_strings(yaml_text: str) -> list[str]:
    """
    Extract the literal Jinja template strings from the _tasks list in copier.yaml.

    copier.yaml _tasks entries are either:
      - Single-quoted strings:  - "{{ ... }}"
      - Block scalars (>-):     >-\n    {{ ... }}

    We extract the raw Jinja expressions so we can substitute variable defaults
    and parse out the shell paths.  We deliberately do NOT evaluate the Jinja
    (that requires copier's full variable context); instead we extract paths
    using regex after substituting the known variable defaults.
    """
    tasks: list[str] = []
    in_tasks = False
    current_task_lines: list[str] = []
    in_block = False

    for line in yaml_text.splitlines():
        if re.match(r"^_tasks\s*:", line):
            in_tasks = True
            continue
        # Any top-level key (non-indented, non-comment, non-empty) ends _tasks
        if in_tasks and line and not line.startswith(" ") and not line.startswith("#"):
            if current_task_lines:
                tasks.append(" ".join(current_task_lines))
                current_task_lines = []
            in_tasks = False
            in_block = False
            continue
        if not in_tasks:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # New list item
        if stripped.startswith("- "):
            if current_task_lines:
                tasks.append(" ".join(current_task_lines))
                current_task_lines = []
            rest = stripped[2:].strip()
            if rest in (">-", ">", "|", "|-"):
                in_block = True
                current_task_lines = []
            else:
                in_block = False
                # Strip surrounding quotes
                rest = rest.strip('"').strip("'")
                current_task_lines = [rest]
        elif in_block:
            current_task_lines.append(stripped)
        else:
            # Continuation of a quoted/flow string (rare — treat as continuation)
            current_task_lines.append(stripped)

    if current_task_lines:
        tasks.append(" ".join(current_task_lines))

    return tasks


def _eval_jinja_concat(expr: str, vars_: dict[str, str]) -> list[str]:
    """
    Evaluate a Jinja string-concatenation expression like:
      'rm -rf ' ~ _copier_conf.dst_path ~ '/_scaffold/' ~ py_project_root ~ '/...'
    into a list of concrete strings by substituting variable defaults.

    Returns a list because the outer {{ ... if cond else ... }} ternary can
    produce one of two branches; we evaluate both and return both.
    """
    # Strip outer {{ }} if present
    expr = expr.strip()
    if expr.startswith("{{") and expr.endswith("}}"):
        expr = expr[2:-2].strip()

    # Split on the top-level ternary `if ... else` at the outermost level.
    # We naively split on ' else ' and take both branches for maximum coverage.
    branches: list[str] = []
    # Simple split — works for copier.yaml's flat ternaries (no nested if/else)
    if " else " in expr:
        parts = expr.split(" else ", 1)
        # Strip the ` if <condition>` suffix that leaks into the first branch.
        # e.g. `'true' if _use_feature else 'false'` → first part is `'true' if _use_feature`
        parts[0] = re.sub(r"\s+if\s+.*", "", parts[0])
        branches.extend(parts)
    else:
        branches.append(expr)

    results: list[str] = []
    for branch in branches:
        # Remove leading `'true' if ... ` guard — we want the else branch too,
        # already handled above.  Strip any leading condition fragment ending at
        # the first ` else `.
        branch = branch.strip().strip("'\"")
        # Now evaluate the concatenation: split on ` ~ ` (Jinja concat operator)
        segments = re.split(r"\s*~\s*", branch)
        parts: list[str] = []
        for seg in segments:
            seg = seg.strip()
            # Strip any stray surrounding quotes left by the branch split
            if len(seg) >= 2 and seg[0] in ("'", '"') and seg[-1] == seg[0]:
                seg = seg[1:-1]
            elif seg.startswith("'"):
                seg = seg[1:]
            elif seg.endswith("'"):
                seg = seg[:-1]
            elif seg.startswith('"'):
                seg = seg[1:]
            elif seg.endswith('"'):
                seg = seg[:-1]

            if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", seg):
                # Bare variable name
                parts.append(vars_.get(seg, ""))
            elif seg == "_copier_conf.dst_path":
                parts.append("__DST__")
            else:
                # Literal string or complex expression — use as-is
                parts.append(seg)
        results.append("".join(parts))

    return results


def _extract_paths_from_task(task_str: str, vars_: dict[str, str]) -> list[str]:
    """
    Given a raw _tasks Jinja expression string, extract all shell paths that
    reference template-relative (staging) locations.

    copier.yaml _tasks entries are Jinja expressions of the form:
      {{ 'true' if COND else 'rm -f ' ~ _copier_conf.dst_path ~ '/_scaffold/...' }}
    or:
      {{ ('mkdir -p ' ~ _copier_conf.dst_path ~ '/...' ~ ' && cp -R ' ~ ...) if COND else 'true' }}

    Strategy:
      1. Evaluate both branches of any top-level ternary.
      2. For each result, split on shell command separators (&& ; ||).
      3. For each shell word, if it contains __DST__ (our dst_path sentinel),
         extract the path after it.
    """
    concrete_strings = _eval_jinja_concat(task_str, vars_)
    paths: list[str] = []

    staging_prefixes = (
        "_scaffold/",
        ".claude/",
        ".agents/",
        "mcp_servers/",
        "frontend/",
        "infrastructure/",
        "configs/",
        ".vscode/",
        ".github/",
    )

    for s in concrete_strings:
        # Split on shell operators / whitespace to get individual tokens
        tokens = re.split(r"[\s;]+", s)
        for token in tokens:
            token = token.strip("'\"./()")
            if "__DST__/" in token:
                after = token.split("__DST__/", 1)[1]
                # Strip trailing /. (cp -R source convention) and trailing /
                after = after.rstrip("/.").rstrip("/")
                if after:
                    paths.append(after)
            elif any(token.startswith(p) for p in staging_prefixes):
                token = token.rstrip("/.").rstrip("/")
                if token:
                    paths.append(token)

    return paths


# ---------------------------------------------------------------------------
# Template tree inventory
# ---------------------------------------------------------------------------


def _inventory_template(template_dir: Path) -> tuple[set[str], set[str]]:
    """
    Return (all_files, all_dirs) as sets of paths relative to template_dir.
    Directory names include their full path from template root.
    """
    files: set[str] = set()
    dirs: set[str] = set()
    for root, dirnames, filenames in os.walk(template_dir):
        rel_root = Path(root).relative_to(template_dir)
        for d in dirnames:
            dirs.add(str(rel_root / d))
        for f in filenames:
            files.add(str(rel_root / f))
    return files, dirs


# ---------------------------------------------------------------------------
# Path resolution: map a _tasks path (post-substitution) to a template path
# ---------------------------------------------------------------------------


def _task_path_to_template_path(path: str, vars_: dict[str, str]) -> str:
    """
    A _tasks path like `_scaffold/backend/src/integrations/n8n_webhook.py`
    maps directly to `template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/...`
    in the template tree.

    We need to reverse-substitute: replace var default values back to their
    {{ var }} forms to match how they appear in the template directory names.
    """
    # Build reverse map: default_value -> {{ var_name }}
    # Longer values first to avoid partial replacements
    reverse = sorted(
        ((v, "{{ " + k + " }}") for k, v in vars_.items()),
        key=lambda x: -len(x[0]),
    )
    result = path
    # Only replace at path segment boundaries (/ delimiters or string edges)
    for default_val, jinja_expr in reverse:
        if not default_val:
            continue
        # Split on /, replace matching segments, rejoin
        segments = result.split("/")
        segments = [jinja_expr if seg == default_val else seg for seg in segments]
        result = "/".join(segments)
    return result


def _all_reverse_substitutions(path: str, vars_: dict[str, str]) -> list[str]:
    """
    Generate all plausible reverse-substituted forms of a concrete path.

    A concrete path like `_scaffold/backend/data/evals` could reverse-map to:
      `_scaffold/{{ py_project_root }}/data/{{ eval_root }}` OR
      `_scaffold/{{ py_project_root }}/data/evals`  (evals is a literal segment)

    We generate all 2^n combinations where each segment that matches a variable
    default is optionally substituted.  Cap at 64 to avoid blowup.
    """
    segments = path.split("/")
    per_segment: list[list[str]] = []
    for seg in segments:
        options: list[str] = [seg]
        for var, default in vars_.items():
            if seg == default and default:
                candidate = "{{ " + var + " }}"
                if candidate not in options:
                    options.append(candidate)
        per_segment.append(options)

    total = 1
    for opts in per_segment:
        total *= len(opts)
    if total > 64:
        return [_task_path_to_template_path(path, vars_)]

    def _product(lists: list[list[str]]) -> list[list[str]]:
        result: list[list[str]] = [[]]
        for lst in lists:
            result = [[*r, item] for r in result for item in lst]
        return result

    return ["/".join(combo) for combo in _product(per_segment)]


def _path_exists_in_template(
    path: str,
    template_files: set[str],
    template_dirs: set[str],
    vars_: dict[str, str],
) -> bool:
    """
    Check whether a _tasks-referenced path (with var defaults substituted in)
    corresponds to something in the template tree.

    Template dir names contain literal {{ var }} segments (e.g.
    `_scaffold/{{ py_project_root }}/{{ ai_source_root }}`), while _tasks
    paths after our substitution use real values (e.g.
    `_scaffold/backend/src`).  We must reverse-substitute to match.
    """
    # Augment vars_ with alternate forms for compound-expression values.
    # py_mcp_server_slug / ts_mcp_server_slug resolve to either the slug or
    # slug + '__unchosen_*', depending on which language is chosen.  Both
    # forms must reverse-map to the same {{ var }} template directory.
    augmented_vars = dict(vars_)
    mcp_slug = vars_.get("mcp_server_slug", "my-mcp-server")
    augmented_vars["py_mcp_server_slug_unchosen"] = mcp_slug + "__unchosen_py"
    augmented_vars["ts_mcp_server_slug_unchosen"] = mcp_slug + "__unchosen_ts"
    # Map unchosen concrete names back to the {{ }} vars for existence checks
    _UNCHOSEN_ALIAS: dict[str, str] = {
        mcp_slug + "__unchosen_py": "{{ py_mcp_server_slug }}",
        mcp_slug + "__unchosen_ts": "{{ ts_mcp_server_slug }}",
    }

    # Generate all plausible reverse-substituted forms (handles ambiguous
    # segments like `evals` that are both a literal and the value of eval_root).
    reverse_forms = _all_reverse_substitutions(path, vars_)
    # Also generate forms with unchosen alias substitution
    for alias_val, alias_expr in _UNCHOSEN_ALIAS.items():
        if alias_val in path:
            reverse_forms.append(path.replace(alias_val, alias_expr))

    # copier strips the .jinja suffix at render time — check both suffixed and
    # unsuffixed forms for each candidate.
    candidates: set[str] = set()
    for form in reverse_forms:
        candidates.add(form)
        candidates.add(form + ".jinja")
    candidates.add(path)
    candidates.add(path + ".jinja")

    for candidate in candidates:
        if candidate in template_files or candidate in template_dirs:
            return True

    # Prefix match: a directory target in _tasks covers all its children
    all_template = template_files | template_dirs
    for candidate in candidates:
        for t in all_template:
            if t == candidate or t.startswith(candidate + "/"):
                return True
    return False


# ---------------------------------------------------------------------------
# Orphan detection: every template dir under _scaffold/ should be reachable
# ---------------------------------------------------------------------------


def _collect_addressable_paths(tasks: list[str], vars_: dict[str, str]) -> set[str]:
    """
    Collect all substituted-value paths addressed by any _tasks entry.
    Paths are in concrete form (e.g. `_scaffold/backend/src`) — the orphan
    check substitutes template {{ }} paths to the same form before comparing.
    """
    addressed: set[str] = set()
    for task in tasks:
        for p in _extract_paths_from_task(task, vars_):
            addressed.add(p)
    return addressed


def _substitute_vars_in_template_path(template_path: str, vars_: dict[str, str]) -> str:
    """
    Replace {{ var_name }} segments in a template-tree path with their default
    values, producing a substituted path that matches _tasks addressed paths.

    E.g. `_scaffold/{{ py_project_root }}/{{ ai_source_root }}` →
         `_scaffold/backend/src`
    """

    def replacer(m: re.Match) -> str:
        inner = m.group(0)[2:-2].strip()
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", inner):
            return vars_.get(inner, m.group(0))
        return m.group(0)

    return JINJA_VAR_RE.sub(replacer, template_path)


def _is_addressed(template_path: str, addressed: set[str], vars_: dict[str, str]) -> bool:
    """
    A template dir is addressed if any addressed path (which uses substituted
    variable values) is a prefix of its substituted form, or covers it exactly.
    """
    substituted = _substitute_vars_in_template_path(template_path, vars_)
    for a in addressed:
        if substituted == a or substituted.startswith(a + "/") or a.startswith(substituted + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# Static analysis driver
# ---------------------------------------------------------------------------


def run_static_analysis() -> list[dict[str, Any]]:
    """Run static analysis and return list of finding dicts."""
    findings: list[dict[str, Any]] = []

    yaml_text = _load_yaml_raw(COPIER_YAML)
    tasks = _extract_tasks_strings(yaml_text)
    template_files, template_dirs = _inventory_template(TEMPLATE_DIR)

    # --- Check 1: every _tasks path resolves to a template entry ---
    # Destination paths (where _tasks moves things TO) are not in template/.
    # Only source/staging paths are.  We identify staging paths by their prefix:
    # _scaffold/ always staging; .claude/ .agents/ mcp_servers/ are both source
    # and destination in template/, so we check them too.
    # Pure-destination paths like backend/, core/, evals/ etc. are skipped.
    staging_check_prefixes = (
        "_scaffold/",
        ".claude/",
        ".agents/",
        "mcp_servers/",
    )
    for task in tasks:
        raw_paths = _extract_paths_from_task(task, VAR_DEFAULTS)
        for p in raw_paths:
            if not any(p.startswith(pfx) for pfx in staging_check_prefixes):
                continue
            if not _path_exists_in_template(p, template_files, template_dirs, VAR_DEFAULTS):
                findings.append(
                    {
                        "type": "MISSING_TASK_PATH",
                        "severity": "ERROR",
                        "path": p,
                        "detail": f"_tasks references '{p}' but no matching entry in template/",
                    }
                )

    # --- Check 2: every _scaffold/ dir in template/ is addressed by _tasks ---
    addressed = _collect_addressable_paths(tasks, VAR_DEFAULTS)
    # Add known always-promoted paths (the big unconditional mv/cp block)
    always_promoted = {
        "_scaffold/.vscode",
        "_scaffold/.github",
        "_scaffold/configs",
        "_scaffold/infrastructure",
        "_scaffold/pyproject.toml",
        "_scaffold/Makefile",
        "_scaffold/.gitignore",
        "_scaffold/.pre-commit-config.yaml",
        "_scaffold/renovate.json",
        "_scaffold/.env.example",
        "_scaffold/README.md",
        "_scaffold/SANYI.md",
        "_scaffold/project_init.sh",
        "_scaffold/railway.toml",
        "_scaffold/promptfoo.config.yaml",
    }
    addressed.update(always_promoted)

    # Walk _scaffold/ dirs only (files under them are covered if their parent dir is)
    for d in sorted(template_dirs):
        if not d.startswith("_scaffold/"):
            continue
        # Only check immediate children of _scaffold/ and their first-level children
        # (deeper nesting is covered by parent addressing)
        parts = Path(d).parts
        if len(parts) > 4:
            continue
        if not _is_addressed(d, addressed, VAR_DEFAULTS):
            findings.append(
                {
                    "type": "ORPHAN_DIR",
                    "severity": "WARNING",
                    "path": d,
                    "detail": f"template/{d} is not referenced by any _tasks entry "
                    f"(may render but never be moved/deleted)",
                }
            )

    # --- Check 3: verify no {{ }} vars remain in template directory NAMES ---
    # (These must all be defined variables with defaults)
    known_vars = set(VAR_DEFAULTS.keys())
    for path in sorted(template_dirs | template_files):
        for m in JINJA_VAR_RE.finditer(path):
            inner = m.group(0)[2:-2].strip()
            if (
                re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", inner)
                and inner not in known_vars
                and inner != "_copier_conf"
            ):
                findings.append(
                    {
                        "type": "UNDEFINED_PATH_VAR",
                        "severity": "ERROR",
                        "path": path,
                        "detail": f"Path uses undefined variable '{inner}' (not in VAR_DEFAULTS)",
                    }
                )

    return findings


# ---------------------------------------------------------------------------
# Render test driver
# ---------------------------------------------------------------------------

RENDER_MATRIX = [
    {
        "label": "python-only defaults",
        "flags": [
            "-d",
            "project_name=TestProject",
            "-d",
            "scaffold_full_project=true",
            "-d",
            "primary_backend_language=python",
            "-d",
            "primary_chat_agent=lg_agent",
            "-d",
            "include_agent_reference_library=false",
            "-d",
            "global_skills_source=none",
            "-d",
            "enable_macos_notifications=false",
        ],
    },
    {
        "label": "typescript-only",
        "flags": [
            "-d",
            "project_name=TestProject",
            "-d",
            "scaffold_full_project=true",
            "-d",
            "primary_backend_language=typescript",
            "-d",
            "ts_agent_framework=vercel_ai_sdk",
            "-d",
            "include_agent_reference_library=false",
            "-d",
            "global_skills_source=none",
            "-d",
            "enable_macos_notifications=false",
        ],
    },
    {
        "label": "both languages",
        "flags": [
            "-d",
            "project_name=TestProject",
            "-d",
            "scaffold_full_project=true",
            "-d",
            "primary_backend_language=both",
            "-d",
            "primary_chat_agent=lg_agent",
            "-d",
            "ts_agent_framework=vercel_ai_sdk",
            "-d",
            "include_agent_reference_library=false",
            "-d",
            "global_skills_source=none",
            "-d",
            "enable_macos_notifications=false",
        ],
    },
    {
        "label": "layering-only",
        "flags": [
            "-d",
            "project_name=TestProject",
            "-d",
            "scaffold_full_project=false",
            "-d",
            "include_agent_reference_library=false",
            "-d",
            "global_skills_source=none",
            "-d",
            "enable_macos_notifications=false",
        ],
    },
    {
        # The ml_model SHAPE — no agentic scaffold at all. Distinct from the
        # "python ml + all metrics" row below, which is ML layered onto one.
        "label": "ml_model shape",
        "flags": [
            "-d",
            "project_name=TestProject",
            "-d",
            "project_type=ml_model",
            "-d",
            "include_agent_reference_library=false",
            "-d",
            "global_skills_source=none",
            "-d",
            "enable_macos_notifications=false",
        ],
    },
    {
        "label": "python ml + all metrics",
        "flags": [
            "-d",
            "project_name=TestProject",
            "-d",
            "scaffold_full_project=true",
            "-d",
            "primary_backend_language=python",
            "-d",
            "primary_chat_agent=lg_agent",
            "-d",
            "include_ml=true",
            "-d",
            "include_metric_escalation=true",
            "-d",
            "include_metric_friction=true",
            "-d",
            "include_metric_intent=true",
            "-d",
            "include_metric_language=true",
            "-d",
            "include_agent_reference_library=false",
            "-d",
            "global_skills_source=none",
            "-d",
            "enable_macos_notifications=false",
        ],
    },
]


def run_render_tests() -> list[dict[str, Any]]:
    """Run copier renders for each matrix entry and check output."""
    findings: list[dict[str, Any]] = []

    try:
        subprocess.run(
            ["copier", "--version"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        findings.append(
            {
                "type": "RENDER_SKIP",
                "severity": "WARNING",
                "path": "",
                "detail": "copier not found or not runnable — skipping render tests",
            }
        )
        return findings

    for combo in RENDER_MATRIX:
        label = combo["label"]
        with tempfile.TemporaryDirectory(prefix="validate_paths_") as dst:
            cmd = [
                "copier",
                "copy",
                "--overwrite",
                "--defaults",
                "--trust",
                *combo["flags"],
                str(REPO_ROOT),
                dst,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                findings.append(
                    {
                        "type": "RENDER_FAILED",
                        "severity": "ERROR",
                        "path": f"[{label}]",
                        "detail": f"copier exited {result.returncode}: "
                        + (result.stderr or result.stdout)[:300].replace("\n", " "),
                    }
                )
                continue

            # Walk output and check for unrendered {{ }} in paths or file bodies
            for root, dirnames, filenames in os.walk(dst):
                rel_root = Path(root).relative_to(dst)
                for d in dirnames:
                    rel = str(rel_root / d)
                    if JINJA_VAR_RE.search(rel):
                        findings.append(
                            {
                                "type": "UNRENDERED_PATH",
                                "severity": "ERROR",
                                "path": f"[{label}] {rel}",
                                "detail": "Directory name contains unrendered {{ }} after render",
                            }
                        )
                    if d == "":
                        findings.append(
                            {
                                "type": "EMPTY_DIR_NAME",
                                "severity": "ERROR",
                                "path": f"[{label}] {rel_root}/",
                                "detail": "Empty-named directory created",
                            }
                        )
                for f in filenames:
                    rel = str(rel_root / f)
                    if JINJA_VAR_RE.search(rel):
                        findings.append(
                            {
                                "type": "UNRENDERED_PATH",
                                "severity": "ERROR",
                                "path": f"[{label}] {rel}",
                                "detail": "File path contains unrendered {{ }} after render",
                            }
                        )
                    # Check file body for unrendered {{ }}
                    full_path = Path(root) / f
                    try:
                        body = full_path.read_text(encoding="utf-8", errors="replace")
                        if JINJA_VAR_RE.search(body):
                            # False-positive filter: some files legitimately contain
                            # Jinja syntax as documentation (CLAUDE.md, skill files,
                            # README.md, .jinja files that are themselves templates).
                            # Only flag .py, .ts, .toml, .json, .yaml, .yml, .sh, Makefile.
                            suffix = full_path.suffix.lower()
                            allowed_template_exts = {
                                ".md",
                                ".jinja",
                                ".txt",
                                ".example",
                            }
                            # Secondary filter: {{ }} in rendered .py files can be
                            # legitimate Python f-string escaping for literal braces
                            # (e.g. CSS property blocks like {{ border-collapse: ... }}).
                            # Only flag if the inner content looks like a Jinja
                            # expression (bare identifier, filter, or operator) —
                            # not CSS properties (contain ; or start with a CSS keyword
                            # followed by non-identifier chars). _CSS_RE is at module level.
                            # f-string escapes are spotted by span rather than by
                            # fullmatch: JINJA_VAR_RE's `[^}]+` stops at the first
                            # `}`, so on `f"{{{{{name}}}}}"` it captures a prefix of
                            # the escape, never the whole thing. Overlapping the
                            # match against the escapes found in the full body is
                            # what makes the two regexes comparable.
                            fstring_spans = [m.span() for m in _FSTRING_BRACE_RE.finditer(body)]

                            def _is_fstring_escape(
                                match: re.Match[str],
                                spans: list[tuple[int, int]] = fstring_spans,
                            ) -> bool:
                                start, end = match.span()
                                return any(s <= start and end <= e for s, e in spans)

                            jinja_matches = [
                                m
                                for m in JINJA_VAR_RE.finditer(body)
                                if not _CSS_RE.fullmatch(m.group(0)) and not _is_fstring_escape(m)
                            ]
                            if (
                                suffix not in allowed_template_exts
                                and full_path.name
                                not in {
                                    "Makefile",
                                    "Dockerfile",
                                }
                                and jinja_matches
                            ):
                                # Find first match for context
                                m = jinja_matches[0]
                                findings.append(
                                    {
                                        "type": "UNRENDERED_BODY",
                                        "severity": "ERROR",
                                        "path": f"[{label}] {rel}",
                                        "detail": f"File body contains unrendered Jinja: "
                                        f"'{m.group(0)[:60]}'",
                                    }
                                )
                    except (PermissionError, IsADirectoryError):
                        pass

    return findings


# ---------------------------------------------------------------------------
# Capabilities catalog check
# ---------------------------------------------------------------------------

CATALOG_PATH = (
    REPO_ROOT
    / "template"
    / ".claude"
    / "skills"
    / "add-capability"
    / "references"
    / "capabilities-catalog.md"
)

# copier.yaml keys that are private/internal or are derived computed vars —
# not user-facing capabilities, so we don't flag them as "uncovered".
_CATALOG_SKIP_VARS: set[str] = {
    # copier internal
    "_min_copier_version",
    "_subdirectory",
    "_external_data",
    "_message_before_copy",
    "_message_after_copy",
    "_exclude",
    "_tasks",
    "_migrations",
    # computed / derived booleans driven by optional_features / other vars
    "is_agent_shaped",
    "has_typescript",
    "has_corpus_pipeline",
    "has_gradeable_interactions",
    "include_interaction_evals",
    "enable_structure_guard",
    "include_run_registry",
    # ml_model shape gates — all derived from project_type via is_ml_shaped,
    # not independently set. They govern which roots a shape renders (the
    # inverse of a capability: you do not "add lifecycle docs" to a project,
    # the shape either has them or it does not), so there is nothing for
    # /add-capability to document.
    "is_ml_shaped",
    "include_llm_kit",
    "include_eval_suite",
    "include_core_etl",
    "include_lifecycle_docs",
    "include_notebooks",
    # derived slug vars (computed from mcp_server_slug; not set independently)
    "py_mcp_server_slug",
    "ts_mcp_server_slug",
    # derived from optional_features multiselect — catalog references the
    # multiselect itself, not each derived boolean
    "include_akira",
    "include_dev_companion",
    "include_promptfoo",
    "include_ragas_grader",
    "include_web_research",
    "include_meeting_intelligence",
    "include_marketing_integrations",
    "include_n8n_webhook",
    "include_composio",
    "include_ml",
    # derived from eval_metrics multiselect
    "include_metric_escalation",
    "include_metric_friction",
    "include_metric_intent",
    "include_metric_language",
    # config/infra vars — not capability-shaped
    "project_name",
    "project_slug",
    "project_description",
    "project_type",
    "primary_users",
    "external_systems",
    "deployment_target",
    "cloud",
    "agent_memory",
    "human_approval",
    "observability_provider",
    "data_sensitivity",
    "ticket_prefix",
    "python_version",
    "aws_region",
    "expensive_command_patterns",
    "eval_allowed_dirs",
    "agent_config_profile",
    "enable_macos_notifications",
    "global_skills_source",
    # path-root vars — covered indirectly via `adds` paths
    "py_project_root",
    "ai_source_root",
    "ml_source_root",
    "run_registry_root",
    "eval_root",
    "ts_project_root",
    "ts_source_root",
    # agent naming vars
    "agent_slug",
    "lg_agent_dir",
    "adk_agent_dir",
    "mcp_server_name",
    "mcp_server_slug",
    # rag sub-options not independently capability-shaped
    "rag_impl",
    "corpus_pipeline_kind",
    "include_ts_rag",
    "enable_postgres_checkpointer",
    # calendar — no catalog entry yet (not in add-capability scope)
    "include_calendar_integration",
    "include_security_guards",
}

# Copier var=value pattern — extract var name only (left of =)
_VAR_ASSIGN_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]*)=[^`]*`")
# "add `VALUE` to `VAR`" pattern — capture only the destination var name
_VAR_ADD_TO_RE = re.compile(r"\badd\s+`[^`]+`\s+to\s+`([a-zA-Z_][a-zA-Z0-9_]*)`")
# Standalone copier var name in backticks — must contain at least one underscore
# (copier var names are snake_case; enum values like `python`, `both`, `duckdb` have no _)
_VAR_STANDALONE_RE = re.compile(r"`([a-zA-Z_][a-zA-Z0-9]*(?:_[a-zA-Z0-9_]+)+)`")
# Known catalog tokens that look like var names (contain _) but are actually
# enum values, multiselect item names, or mode strings — not copier var names.
_CATALOG_VALUE_TOKENS: set[str] = {
    "existing_repo",  # value for scaffold_full_project=false mode label
    "n8n_webhook",  # optional_features list item
    "web_research",  # optional_features list item
    "meeting_intelligence",  # optional_features list item
    "lg_agent",  # primary_chat_agent enum value
    "adk_agent",  # primary_chat_agent enum value
    "vercel_ai_sdk",  # ts_agent_framework enum value
    "split_service",  # frontend_backend_topology enum value
    "rag_agent",  # project_type / agent type label
    "streamText",  # Vercel AI SDK function name (mentioned in adds text)
    "agent_slug",  # path segment var (in _CATALOG_SKIP_VARS; not a set target)
}
# Copier var in a Jinja-style {var_name} reference used in adds paths
_JINJA_CATALOG_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
# Path fragment in adds cells — e.g. `backend/src/agents/rag_agent/` or `evals/graders/escalation.py`
# We only check paths that look like template paths (contain / and no spaces)
_ADDS_PATH_RE = re.compile(r"`([^`\s{}]+/[^`\s{}]+)`")


def _parse_copier_var_names(yaml_text: str) -> set[str]:
    """
    Extract top-level (non-indented) key names from copier.yaml.
    These are the variable names copier exposes.
    """
    vars_: set[str] = set()
    for line in yaml_text.splitlines():
        # Top-level key: starts with a word char, ends with ':'
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:", line)
        if m:
            vars_.add(m.group(1))
    return vars_


def _parse_catalog(catalog_text: str) -> list[dict[str, object]]:
    """
    Parse the capabilities catalog markdown into a list of capability dicts.

    Each dict has:
      name        — capability slug (## heading)
      vars        — set of copier var names referenced (from sets/requires/conflicts_with)
      adds_paths  — list of path strings from the adds row (after stripping {{ }})
    """
    capabilities: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in catalog_text.splitlines():
        # New capability section
        if line.startswith("## ") and not line.startswith("## Notes"):
            if current is not None:
                capabilities.append(current)
            current = {"name": line[3:].strip(), "vars": set(), "adds_paths": []}
            continue

        if current is None:
            continue

        # Extract var names from backtick references in sets/requires/conflicts rows.
        # Only process rows that contain copier variable references (table rows with |).
        if "|" in line:
            # "add `VALUE` to `VAR`" — capture only the destination var
            add_to_vars: set[str] = set()
            for m in _VAR_ADD_TO_RE.finditer(line):
                add_to_vars.add(m.group(1))
                current["vars"].add(m.group(1))  # type: ignore[union-attr]
            # `var=value` — take the var name (left of =)
            for m in _VAR_ASSIGN_RE.finditer(line):
                current["vars"].add(m.group(1))  # type: ignore[union-attr]
            # Standalone `var_name` (must have underscore — filters out plain enum values)
            # Skip tokens already handled as "add … to VAR" values and known value tokens
            for m in _VAR_STANDALONE_RE.finditer(line):
                token = m.group(1)
                if token not in _CATALOG_VALUE_TOKENS:
                    current["vars"].add(token)  # type: ignore[union-attr]

        # Extract path strings from adds rows only
        if line.strip().startswith("| adds") or ("adds" in line and "|" in line):
            for m in _ADDS_PATH_RE.finditer(line):
                path = m.group(1)
                # Strip leading / if any
                path = path.lstrip("/")

                # Replace {var} placeholders with VAR_DEFAULTS values
                def _sub_var(vm: re.Match) -> str:
                    return VAR_DEFAULTS.get(vm.group(1), vm.group(1))

                path = _JINJA_CATALOG_VAR_RE.sub(_sub_var, path)
                # Only keep paths that look like relative template paths
                if "/" in path and not path.startswith("http"):
                    current["adds_paths"].append(path)  # type: ignore[union-attr]

    if current is not None:
        capabilities.append(current)

    return capabilities


def run_catalog_checks() -> list[dict[str, Any]]:
    """
    Verify the capabilities catalog against copier.yaml and template/.

    Checks:
      1. Every var name the catalog references exists in copier.yaml.
      2. Every `adds` path resolves to something in template/ (best-effort;
         paths using copier vars are substituted with VAR_DEFAULTS).
      3. Every non-private, non-derived copier var is covered by at least one
         capability entry (drift: new vars with no catalog coverage).
    """
    findings: list[dict[str, Any]] = []

    if not CATALOG_PATH.exists():
        findings.append(
            {
                "type": "CATALOG_MISSING",
                "severity": "ERROR",
                "path": str(CATALOG_PATH.relative_to(REPO_ROOT)),
                "detail": "Capabilities catalog file not found",
            }
        )
        return findings

    catalog_text = CATALOG_PATH.read_text(encoding="utf-8")
    yaml_text = _load_yaml_raw(COPIER_YAML)
    template_files, template_dirs = _inventory_template(TEMPLATE_DIR)
    copier_vars = _parse_copier_var_names(yaml_text)
    capabilities = _parse_catalog(catalog_text)

    if not capabilities:
        findings.append(
            {
                "type": "CATALOG_EMPTY",
                "severity": "WARNING",
                "path": str(CATALOG_PATH.relative_to(REPO_ROOT)),
                "detail": "No capability entries parsed from catalog",
            }
        )
        return findings

    # Collect all vars the catalog touches across all capabilities
    all_catalog_vars: set[str] = set()
    for cap in capabilities:
        all_catalog_vars.update(cap["vars"])  # type: ignore[arg-type]

    # Check 1: every catalog var exists in copier.yaml
    for var in sorted(all_catalog_vars):
        if var not in copier_vars:
            findings.append(
                {
                    "type": "CATALOG_VAR_MISSING",
                    "severity": "ERROR",
                    "path": "capabilities-catalog.md",
                    "detail": f"Var `{var}` referenced in catalog but not in copier.yaml",
                }
            )

    # Check 2: every `adds` path resolves into template/
    # Catalog paths are rendered-output paths (e.g. `evals/graders/escalation.py`).
    # In the template tree they may live under _scaffold/{{ py_project_root }}/.
    _SCAFFOLD_PREFIXES = [
        "",
        f"_scaffold/{VAR_DEFAULTS.get('py_project_root', 'backend')}/",
        f"_scaffold/{VAR_DEFAULTS.get('ts_project_root', 'my-project')}/",
    ]
    for cap in capabilities:
        cap_name = cap["name"]
        for path in cap["adds_paths"]:  # type: ignore[union-attr]
            path_clean = path.rstrip("/")
            found = False
            for prefix in _SCAFFOLD_PREFIXES:
                if _path_exists_in_template(
                    prefix + path_clean, template_files, template_dirs, VAR_DEFAULTS
                ):
                    found = True
                    break
            if not found:
                findings.append(
                    {
                        "type": "CATALOG_PATH_MISSING",
                        "severity": "WARNING",
                        "path": f"[{cap_name}] {path_clean}",
                        "detail": "`adds` path not found in template/ (may be conditional)",
                    }
                )

    # Check 3: uncovered copier vars (exist in copier.yaml, not in catalog, not skipped)
    uncovered = copier_vars - all_catalog_vars - _CATALOG_SKIP_VARS
    for var in sorted(uncovered):
        findings.append(
            {
                "type": "CATALOG_VAR_UNCOVERED",
                "severity": "INFO",
                "path": "copier.yaml",
                "detail": f"Var `{var}` has no catalog entry (consider documenting)",
            }
        )

    return findings


def run_shared_link_checks() -> list[dict[str, Any]]:
    """
    Verify the template ships shared skills and hooks as symlinks into the root .claude/.

    A template entry whose name also exists at the root must be a symlink that resolves
    there; a real file or directory is a silent re-fork that drifts from canon.
    """
    findings: list[dict[str, Any]] = []
    for kind in ("skills", "hooks"):
        root_dir = REPO_ROOT / ".claude" / kind
        for entry in sorted((TEMPLATE_DIR / ".claude" / kind).iterdir()):
            rel = str(entry.relative_to(REPO_ROOT))
            if entry.is_symlink():
                if not entry.exists():
                    findings.append(
                        {
                            "type": "SHARED_LINK_BROKEN",
                            "severity": "ERROR",
                            "path": rel,
                            "detail": f"Symlink target missing: {entry.readlink()}",
                        }
                    )
                continue
            if (root_dir / entry.name).exists():
                findings.append(
                    {
                        "type": "SHARED_FORKED",
                        "severity": "ERROR",
                        "path": rel,
                        "detail": f"Duplicates .claude/{kind}/{entry.name}; replace with a symlink",
                    }
                )
    return findings


def _print_report(findings: list[dict[str, Any]]) -> None:
    errors = [f for f in findings if f["severity"] == "ERROR"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]
    infos = [f for f in findings if f["severity"] == "INFO"]
    skips = [f for f in findings if f["severity"] not in ("ERROR", "WARNING", "INFO")]

    print()
    print("=" * 80)
    print("  validate_paths.py — findings")
    print("=" * 80)

    if not findings:
        print("  No findings. All checks passed.")
        print("=" * 80)
        return

    header = f"  {'TYPE':<24} {'SEV':<8} {'PATH':<32} DETAIL"
    print(header)
    print("-" * 80)

    for group, label in [
        (errors, "ERRORS"),
        (warnings, "WARNINGS"),
        (infos, "INFO"),
        (skips, "OTHER"),
    ]:
        if not group:
            continue
        print(f"\n  --- {label} ({len(group)}) ---")
        for f in group:
            path_disp = f["path"][:30] + "…" if len(f["path"]) > 31 else f["path"]
            detail = f["detail"][:42] + "…" if len(f["detail"]) > 43 else f["detail"]
            print(f"  {f['type']:<24} {f['severity']:<8} {path_disp:<32} {detail}")

    print()
    print("-" * 80)
    print(
        f"  Summary: {len(errors)} error(s), {len(warnings)} warning(s)"
        + (f", {len(infos)} info" if infos else "")
        + (f", {len(skips)} other" if skips else "")
    )
    print("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate copier.yaml path references against template/ tree.",
    )
    parser.add_argument(
        "--render-test",
        action="store_true",
        help="Also run live copier renders and check output (requires copier)",
    )
    parser.add_argument(
        "--catalog-check",
        action="store_true",
        help="Also check the capabilities catalog against copier.yaml and template/",
    )
    args = parser.parse_args()

    print(f"Repo root : {REPO_ROOT}")
    print(f"Template  : {TEMPLATE_DIR}")
    print(f"copier.yaml: {COPIER_YAML}")
    print()

    findings: list[dict[str, Any]] = []

    print("Running static analysis...")
    findings.extend(run_static_analysis())
    findings.extend(run_shared_link_checks())

    if args.catalog_check:
        print("Running capabilities catalog checks...")
        findings.extend(run_catalog_checks())

    if args.render_test:
        print(f"Running render tests ({len(RENDER_MATRIX)} combinations)...")
        findings.extend(run_render_tests())

    _print_report(findings)

    errors = [f for f in findings if f["severity"] == "ERROR"]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
