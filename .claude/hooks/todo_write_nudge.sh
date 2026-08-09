#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/lib.sh"

# Advisory only (always exit 0): heavy Bash usage in one session without task
# tracking. Fires exactly once, at Bash call #100, keyed by session id.
sid=$(jq -r '.session_id // empty' <<<"$_HOOK_INPUT" 2>/dev/null || true)
[ -z "$sid" ] && exit 0

count_file="${TMPDIR:-/tmp}/claude-bash-count-${sid}"
count=$(( $(cat "$count_file" 2>/dev/null || echo 0) + 1 ))
printf '%s' "$count" > "$count_file"

if [ "$count" -eq 100 ]; then
  warn "HEAVY SESSION: 100 Bash calls this session — consider TaskCreate/TodoWrite to track progress, or compact if past a phase boundary."
fi

exit 0
