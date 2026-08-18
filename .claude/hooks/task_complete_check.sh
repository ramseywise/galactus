#!/usr/bin/env bash
# Stop hook: blocks completion until lint + tests pass on changed files.
# Returns exit 2 (block) with feedback if issues found.
# Returns exit 0 (allow) if clean or no relevant changes.

set -euo pipefail
source "$(dirname "$0")/lib.sh" 2>/dev/null || true

# Vendored / reference trees: code the repo carries but does not own or build.
# A nested tree with its own pyproject.toml resolves ruff settings from THAT config,
# so a root-level exclude (even with force-exclude) cannot reach it — the only place
# to drop these is here, before ruff is invoked.
VENDOR_RE='^(examples|third_party|vendor)/|/(\.venv|venv|node_modules|site-packages)/'

# Get changed files (staged + unstaged vs HEAD), skip deleted files
changed_py=$(git diff --name-only HEAD 2>/dev/null | grep '\.py$' | grep -Ev "$VENDOR_RE" | while read -r f; do [ -f "$f" ] && echo "$f"; done || true)
changed_ts=$(git diff --name-only HEAD 2>/dev/null | grep -E '\.(ts|tsx)$' | grep -Ev "$VENDOR_RE" | while read -r f; do [ -f "$f" ] && echo "$f"; done || true)

# No code changes → nothing to check
if [ -z "$changed_py" ] && [ -z "$changed_ts" ]; then
  exit 0
fi

errors=""

# NOTE (2026-07-19): ruff resolves settings from the config nearest each file.
# A repo whose ROOT has no ruff-readable config (no pyproject.toml / ruff.toml)
# gets ruff's BUILT-IN defaults — line-length 88, E+F rules — not the project's
# real settings, so this hook can report files that are correct under the config
# CI actually uses. That is a repo-config gap, not a hook bug: the fix is a root
# ruff.toml in the affected repo (done for ai-project-template, whose governing
# config is itself a Jinja template ruff cannot parse). Left resolved that way on
# purpose — having the hook guess at config, or skip checks when none is found,
# either misreports or silently disables the safety net.
# --- Python checks ---
if [ -n "$changed_py" ]; then
  # Lint (ruff check, no --fix — report only).
  # Branch on EXIT STATUS, not output emptiness: a clean run prints
  # "All checks passed!", which is non-empty and used to block every task that
  # touched a .py file. stderr is kept so a ruff crash surfaces as a failure
  # instead of being silently swallowed into "clean".
  # --force-exclude: ruff ignores a config's exclude list for paths passed
  # explicitly on the command line, which is exactly what this hook does. Without
  # it, a repo that excludes vendored/reference trees (examples/, third_party/)
  # still gets them linted here and blocks on code it does not own.
  set +e
  lint_output=$(printf '%s\n' "$changed_py" | tr '\n' '\0' | xargs -0 uvx ruff check --no-fix --force-exclude 2>&1)
  lint_status=$?
  set -e
  if [ $lint_status -ne 0 ]; then
    errors="${errors}LINT ERRORS (run ruff check --fix):\n${lint_output}\n\n"
  fi

  # Format check — same exit-status rule (ruff exits 1 when files need
  # reformatting), so this no longer depends on matching output wording.
  set +e
  format_output=$(printf '%s\n' "$changed_py" | tr '\n' '\0' | xargs -0 uvx ruff format --check --force-exclude 2>&1)
  format_status=$?
  set -e
  if [ $format_status -ne 0 ]; then
    errors="${errors}FORMAT ISSUES (run ruff format):\n${format_output}\n\n"
  fi
fi

# --- TypeScript checks ---
if [ -n "$changed_ts" ]; then
  if [ -f "node_modules/.bin/tsc" ]; then
    tsc_output=$(npx tsc --noEmit 2>&1 | head -20 || true)
    if [ -n "$tsc_output" ]; then
      errors="${errors}TYPESCRIPT ERRORS:\n${tsc_output}\n\n"
    fi
  fi
fi

# --- Tests (only if a test runner exists and changed files touch src/) ---
if echo "$changed_py" | grep -qE '^(src/|core/|app/)'; then
  if [ -f "pyproject.toml" ] && grep -q "pytest" pyproject.toml 2>/dev/null; then
    # Skip e2e tests that need running servers; prefer tests/unit/ where it exists
    if [ -d "tests/unit" ]; then
      test_output=$(uv run pytest tests/unit/ --tb=short -q --no-header -x 2>&1 | tail -10 || true)
    elif [ -d "tests/e2e" ]; then
      test_output=$(uv run pytest tests/ --ignore=tests/e2e --tb=short -q --no-header -x 2>&1 | tail -10 || true)
    else
      test_output=$(uv run pytest --tb=short -q --no-header -x 2>&1 | tail -10 || true)
    fi
    if echo "$test_output" | grep -qE "FAILED|ERROR"; then
      errors="${errors}TEST FAILURES:\n${test_output}\n\n"
    fi
  fi
fi

# --- Verdict ---
if [ -n "$errors" ]; then
  log_event "task_complete_check" 2 "${errors:0:200}"
  printf '%b' "Task completion blocked — fix these before finishing:\n\n${errors}" >&2
  exit 2
fi

log_event "task_complete_check" 0 "pass"
exit 0
