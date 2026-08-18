#!/usr/bin/env bash
# Hook parity check — warns when vendored hooks in .claude/hooks/ drift from
# the canonical copies in ~/.claude/hooks/. Fires on UserPromptSubmit, debounced
# to once per session via a TMPDIR sentinel.
#
# Iterates the VENDORED set only. Global-only hooks are expected (the two sets
# are not equal); vendored files with no global counterpart are flagged.
#
# galactus#29

set -euo pipefail
source "$(dirname "$0")/lib.sh"

# --- session debounce --------------------------------------------------------
sid=$(jq -r '.session_id // empty' <<<"$_HOOK_INPUT" 2>/dev/null || true)
sentinel="${TMPDIR:-/tmp}/claude-hook-parity-${sid:-$$}"
[ -e "$sentinel" ] && exit 0
: > "$sentinel" 2>/dev/null || true

# --- locate directories -----------------------------------------------------
REPO_HOOKS="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.claude/hooks"
GLOBAL_HOOKS="${HOME}/.claude/hooks"

[ -d "$REPO_HOOKS" ] || exit 0
[ -d "$GLOBAL_HOOKS" ] || exit 0

# --- compare vendored files --------------------------------------------------
drifted=()
missing_global=()

while IFS= read -r -d '' file; do
  name="${file##*/}"
  global="${GLOBAL_HOOKS}/${name}"
  if [ ! -f "$global" ]; then
    missing_global+=("$name")
  elif ! cmp -s "$file" "$global"; then
    drifted+=("$name")
  fi
done < <(find "$REPO_HOOKS" -maxdepth 1 -name '*.sh' -not -name 'hook_parity_check.sh' -print0 2>/dev/null)

# Also check test files
if [ -d "$REPO_HOOKS/tests" ] && [ -d "$GLOBAL_HOOKS/tests" ]; then
  while IFS= read -r -d '' file; do
    name="${file##*/}"
    global="${GLOBAL_HOOKS}/tests/${name}"
    if [ ! -f "$global" ]; then
      missing_global+=("tests/$name")
    elif ! cmp -s "$file" "$global"; then
      drifted+=("tests/$name")
    fi
  done < <(find "$REPO_HOOKS/tests" -maxdepth 1 -name '*.sh' -print0 2>/dev/null)
fi

# --- report ------------------------------------------------------------------
if [ ${#drifted[@]} -gt 0 ] || [ ${#missing_global[@]} -gt 0 ]; then
  msg="Hook parity drift detected (.claude/hooks/ vs ~/.claude/hooks/):"
  for f in "${drifted[@]+"${drifted[@]}"}"; do
    msg+=" DIFF:$f"
  done
  for f in "${missing_global[@]+"${missing_global[@]}"}"; do
    msg+=" NO_GLOBAL:$f"
  done
  msg+=" — re-vendor from global (canonical). See CLAUDE.md vendoring exception."
  warn "$msg"
  log_event "hook_parity_check" 1 "${drifted[*]+"${drifted[*]}"} ${missing_global[*]+"${missing_global[*]}"}"
fi

exit 0
