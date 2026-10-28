#!/usr/bin/env bash
# Stop hook: runs the per-file quality checks once, over every changed file,
# instead of after each Write/Edit.
#
# Per edit, only formatting runs (see settings.json). The checks below used to
# run after every edit too — ~12 hook spawns per keystroke-sized change, plus a
# pyright and a tsc each time. Here they run once when the turn ends.
#
# Each per-file hook is reused unchanged: it is fed the same
# {"tool_input":{"file_path":...}} payload it gets as a PostToolUse hook, and
# keeps its own path filter. Hooks that did not render (no TypeScript, say) are
# skipped.
#
# Output contract: any findings → printed to stderr, exit 2, which blocks the
# stop once so the model sees them. The second stop in a row arrives with
# stop_hook_active=true and is let through, so warnings can never loop.

set -uo pipefail

input=$(cat)
[ "$(jq -r '.stop_hook_active // false' <<<"$input" 2>/dev/null)" = "true" ] && exit 0

hooks_dir="$(cd "$(dirname "$0")" && pwd)"
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0

changed=$( { git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } \
  | grep -Ev '(^|/)(node_modules|\.venv|dist|build)/' | sort -u)
[ -z "$changed" ] && exit 0

# Per file: each runs on every changed file and filters by path itself.
PER_FILE=(code_quality sdk_lint function_complexity_warning test_coverage public_api_test_check ts_quality)
# Per project: they check the whole tree, so one run with any TS path is enough.
PER_PROJECT_TS=(ts_typecheck ts_lint)

report=""
run_hook() {  # <hook name> <absolute path>
  local hook="$hooks_dir/$1.sh" out
  [ -f "$hook" ] || return 0
  out=$(printf '{"tool_input":{"file_path":"%s"}}' "$2" | CLAUDE_TOOL_INPUT="" bash "$hook" 2>&1 >/dev/null)
  [ -n "$out" ] && report+="$out"$'\n'
}

first_ts=""
py_files=()
while IFS= read -r f; do
  [ -f "$f" ] || continue
  abs="$root/$f"
  for h in "${PER_FILE[@]}"; do run_hook "$h" "$abs"; done
  case "$f" in
    *.py)
      py_files+=("$f")
      lines=$(wc -l <"$f" | tr -d ' ')
      [ "$lines" -gt 400 ] && report+="Size: $f is $lines lines (>400) — consider splitting"$'\n'
      ;;
    *.ts|*.tsx) [ -z "$first_ts" ] && first_ts="$abs" ;;
  esac
done <<<"$changed"

if [ -n "$first_ts" ]; then
  for h in "${PER_PROJECT_TS[@]}"; do run_hook "$h" "$first_ts"; done
fi

# One pyright over all changed Python files, not one per file.
if [ "${#py_files[@]}" -gt 0 ] && command -v uv >/dev/null 2>&1; then
  # Report diagnostics only: a pyright that failed to start (no venv, bad
  # pyproject) is not a finding about the user's code.
  pyright_hits=$(uv run --quiet pyright "${py_files[@]}" 2>&1 | grep -E ' - (error|warning)' | head -10)
  [ -n "$pyright_hits" ] && report+="Pyright:"$'\n'"$pyright_hits"$'\n'
fi

[ -z "$report" ] && exit 0
printf 'End-of-turn checks on changed files:\n%s' "$report" >&2
exit 2
