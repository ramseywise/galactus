#!/usr/bin/env bash

set -euo pipefail

# Hook payload arrives as JSON on stdin ({"tool_input": {...}}); CLAUDE_TOOL_INPUT
# was never set by Claude Code, which made every guard fail open until 2026-07-28.
_HOOK_INPUT="${CLAUDE_TOOL_INPUT:-}"
if [ -z "$_HOOK_INPUT" ] && [ ! -t 0 ]; then
  _HOOK_INPUT=$(cat || true)
fi

claude_path() {
  jq -r '.tool_input.file_path // .file_path // empty' <<<"$_HOOK_INPUT"
}

claude_command() {
  jq -r '.tool_input.command // .command // empty' <<<"$_HOOK_INPUT"
}

# The directory the *session* is in. The hook process's own cwd is not a reliable
# stand-in: guards run from the dispatching session's repo, so `.` resolves there
# even when the command targets somewhere else entirely.
claude_cwd() {
  jq -r '.cwd // empty' <<<"$_HOOK_INPUT"
}

claude_content() {
  jq -r '.tool_input.new_string // .tool_input.content // .new_string // .content // empty' <<<"$_HOOK_INPUT"
}

# Heredoc bodies are data, not invocations. A `gh issue create --body "$(cat <<'EOF' ...`
# that merely *describes* a blocked command used to trip any guard that greps the command
# as flat text — filing the bug report about a block was itself blocked, twice. Guards
# should match against this stripped text and log the command as written.
# Known hole: `bash <<EOF ... EOF` really does execute its body, which this strips.
# Accepted — these guards are workflow nudges, not a security boundary.
strip_heredoc_bodies() {
  local line tag="" in_hd=0 out=""
  while IFS= read -r line; do
    if [ "$in_hd" -eq 1 ]; then
      [[ "$line" =~ ^[[:space:]]*"$tag"[[:space:]]*$ ]] && in_hd=0
      continue
    fi
    if [[ "$line" =~ \<\<-?[[:space:]]*[\'\"]?([A-Za-z_][A-Za-z0-9_]*)[\'\"]? ]]; then
      tag="${BASH_REMATCH[1]}"
      in_hd=1
    fi
    out+="$line"$'\n'
  done <<< "$1"
  printf '%s' "$out"
}

warn() {
  printf '%s\n' "$*" >&2
}

block() {
  printf '%s\n' "$*" >&2
  exit 2
}

# Repo-local, not ${HOME}/.claude — a hook shipped inside a repo must not write to the
# operator's home directory. Anyone who clones galactus gets logs under their checkout.
_HOOK_LOG_DIR="$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(dirname "$(dirname "$0")")")/.claude/logs"
mkdir -p "$_HOOK_LOG_DIR" 2>/dev/null || true

LOG_FILE="${_HOOK_LOG_DIR}/hook-log.jsonl"

log_event() {
  local hook="$1" exit_code="$2" context="${3:-}"
  local repo
  repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  printf '{"ts":"%s","hook":"%s","exit_code":%d,"repo":"%s","context":"%s"}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$hook" "$exit_code" "$repo" \
    "$(printf '%s' "$context" | head -c 200 | tr '"\\' '..' | tr -d '\000-\037')" \
    >> "$LOG_FILE" || true
}

PASS_LOG_FILE="${_HOOK_LOG_DIR}/hook-pass-log.jsonl"

log_pass() {
  local hook="$1" context="${2:-}"
  local repo
  repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  printf '{"ts":"%s","hook":"%s","repo":"%s","context":"%s"}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$hook" "$repo" \
    "$(printf '%s' "$context" | head -c 200 | tr '"\\' '..' | tr -d '\000-\037')" \
    >> "$PASS_LOG_FILE" || true
  # Cap at 1000 lines. Raised from 100 (2026-07-29): at ~95 passes/day the old cap
  # rotated out within a day, so the dashboard's pass counts were a floor reading of
  # roughly "today" rather than a trend. `tr -d '\000-\037'` above keeps one record
  # on one line, so this line-based cap can no longer truncate mid-record.
  if [[ -f "$PASS_LOG_FILE" ]] && (( $(wc -l < "$PASS_LOG_FILE") > 1000 )); then
    tail -1000 "$PASS_LOG_FILE" > "${PASS_LOG_FILE}.tmp" && mv "${PASS_LOG_FILE}.tmp" "$PASS_LOG_FILE"
  fi
}
