#!/usr/bin/env bash
# Docs drift warning — fires on code file writes (PostToolUse).
# Checks if a README exists in the same or parent directory.
# Advisory only (exit 0 always).

set -euo pipefail
source "$(dirname "$0")/lib.sh"

path=$(claude_path)
[ -z "$path" ] && exit 0

# Only fire on code files, not docs/configs
echo "$path" | grep -qE '\.(py|ts|tsx|js|jsx|rs|go|java|rb|sh)$' || exit 0

dir=$(dirname "$path")
readme=""

# Check same dir, then parent
if [ -f "$dir/README.md" ]; then
  readme="$dir/README.md"
elif [ -f "$(dirname "$dir")/README.md" ]; then
  readme="$(dirname "$dir")/README.md"
fi

[ -z "$readme" ] && exit 0

# Check if the README was also recently modified (within this session — last 30 min)
readme_age=$(( $(date +%s) - $(stat -f %m "$readme" 2>/dev/null || echo 0) ))
if [ "$readme_age" -lt 1800 ]; then
  # README was touched recently, probably being maintained
  exit 0
fi

# Once per README per session: a repeat of the same advisory is tokens, not signal.
sid=$(jq -r '.session_id // empty' <<<"$_HOOK_INPUT" 2>/dev/null || true)
if [ -n "$sid" ]; then
  stamp="${TMPDIR:-/tmp}/claude-docs-drift-${sid}"
  grep -qxF "$readme" "$stamp" 2>/dev/null && exit 0
  printf '%s\n' "$readme" >> "$stamp"
fi

warn "Docs drift: $readme may need updating (code changed in $dir)."
log_event "docs_drift_warn" 0 "$path"
exit 0
