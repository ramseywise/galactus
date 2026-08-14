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

# Hook telemetry sinks live in guacamayo (which owns the insights/dashboard pipeline
# that reads them), not in global ~/.claude. Overridable via CLAUDE_TELEMETRY_DIR.
# Both writers below end in `|| true`, so a bad path loses logging SILENTLY -- hence
# the explicit fallback to ~/.claude if the guacamayo dir is absent (fresh machine,
# repo not cloned yet). Never let telemetry pathing break a hook.
CLAUDE_TELEMETRY_DIR="${CLAUDE_TELEMETRY_DIR:-${HOME}/workspace/guacamayo/.sounding/telemetry}"
if [[ ! -d "$CLAUDE_TELEMETRY_DIR" ]]; then
  CLAUDE_TELEMETRY_DIR="${HOME}/.claude"
fi

LOG_FILE="${CLAUDE_TELEMETRY_DIR}/.hook-log.jsonl"

log_event() {
  local hook="$1" exit_code="$2" context="${3:-}"
  local repo
  repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  printf '{"ts":"%s","hook":"%s","exit_code":%d,"repo":"%s","context":"%s"}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$hook" "$exit_code" "$repo" \
    "$(printf '%s' "$context" | head -c 200 | tr '"\\' '..' | tr -d '\000-\037')" \
    >> "$LOG_FILE" || true
}

# The BUILD transition ledger — one record per *accepted* state edge.
#
# Vendored from galactus (`.claude/hooks/lib.sh`) to close galactus#20: two copies
# of `plan_status_validate.sh` at different vintages both register on `Write|Edit`,
# and settings layers MERGE rather than override. A session whose project dir is not
# the repo ships only the global copy, so before this the ledger recorded nothing
# for any run not launched from the galactus root — indistinguishable at read time
# from a run with no transitions.
#
# The ledger is deliberately per-repo, NOT under CLAUDE_TELEMETRY_DIR: a transition
# count is a property of the repo whose plan docs moved, and pooling every repo's
# edges into one guacamayo-rooted file would make the per-repo count unrecoverable.
# This is why `log_transition` resolves its own root rather than reusing LOG_FILE's.
#
# Separate from the hook logs on purpose: `log_pass` rotates at 1000 lines, and the
# quantity being measured (D10, the loop-back count) is cumulative over months. A
# rotating history can only answer "recently", which is the question that already
# has an answer of zero. So this file is **not rotated** — it grows about one line
# per state transition, kilobytes per year.
#
# `GALACTUS_TRANSITION_LOG` exists for the test suite: the ledger root resolves from
# the *cwd*, not from the doc under validation, so hook tests writing real fixture
# docs would append synthetic edges to the operator's ledger. A count a test suite
# can increment is not a count of human decisions.
_transition_log_file() {
  if [ -n "${GALACTUS_TRANSITION_LOG:-}" ]; then
    printf '%s' "$GALACTUS_TRANSITION_LOG"
    return
  fi
  local root
  root=$(git rev-parse --show-toplevel 2>/dev/null || true)
  # No enclosing repo: land in the global logs dir rather than scattering ledgers
  # into whatever directory the session happened to start in. Written without the
  # `.claude` segment the repo path carries — `${HOME}/.claude/.claude/logs` is the
  # doubled form that produces.
  if [ -z "$root" ]; then
    printf '%s/logs/plan-transitions.jsonl' "${HOME}/.claude"
    return
  fi
  printf '%s/.claude/logs/plan-transitions.jsonl' "$root"
}

log_transition() {
  local path="$1" from="$2" to="$3" track="${4:-}" epistemic="${5:-}"
  local repo doc target record
  target=$(_transition_log_file)
  mkdir -p "$(dirname "$target")" 2>/dev/null || true
  repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  # Basename only: the ledger is per-repo already, and absolute paths carry the
  # operator's home directory into a file that may later be shared.
  doc=$(basename "$path")
  record=$(printf '"repo":"%s","doc":"%s","from":"%s","to":"%s"' "$repo" "$doc" "$from" "$to")

  # Deduplicate against the immediately preceding record. Settings layers MERGE:
  # in a session rooted at a repo that ships its own copy of this hook, BOTH the
  # repo hook and the global hook fire on one Write, and since galactus#20 both
  # resolve to this same ledger path. Without this guard the fix for under-
  # counting becomes double-counting, and D10 is wrong in the other direction —
  # worse, because a doubled count still looks plausible.
  #
  # Compared on the edge identity only, NOT the timestamp: the two hooks can land
  # in different seconds. The tail -1 scope is deliberate — the same edge traversed
  # again later (a genuine loop-back, the quantity being measured) is separated by
  # other records and must still be counted.
  if [ -f "$target" ] && [ -s "$target" ]; then
    case "$(tail -1 "$target" 2>/dev/null || true)" in
      *"$record"*) return 0 ;;
    esac
  fi

  printf '{"ts":"%s",%s,"track":"%s","epistemic":"%s"}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$record" "$track" "$epistemic" \
    >> "$target" || true
}

# Mark that a recorder was alive in this session — galactus#20 fix direction 2.
#
# `log_transition` alone makes the ledger a record of edges *traversed*, which
# leaves one distinction unmade: a session that recorded nothing because nothing
# moved is byte-identical to a session where no recorder ran at all. That is the
# §2a three-way distinction (yes / no / never asked) applied to the instrument
# rather than to the measurement, and it is exactly the ambiguity step 4 exists
# to remove — one level up. Before this, "0 loop-backs" over a window could mean
# "rare" or "the recorder was asleep," and nothing in the file said which.
#
# Written on the first *validate pass* of a session, not the first transition:
# a marker that only appears alongside an edge cannot witness the empty case,
# which is the only case it exists for.
#
# Latched to fire once per session via a TMPDIR sentinel, the same keying
# `todo_write_nudge.sh` uses. Two reasons it must be once: the ledger is not
# rotated, so a per-write marker would grow it by orders of magnitude and bury
# the edges it exists to contextualize; and settings layers MERGE, so both the
# repo hook and the global hook fire on a single Write. The sentinel makes the
# first writer win and the second a no-op — `log_transition`'s tail -1 dedup
# cannot help here, since the two markers are separated by the edge record.
#
# No session id means no marker rather than an unkeyed one. An unkeyed marker
# cannot be deduplicated or attributed, and inventing a session identity is the
# manufactured-certainty failure this record exists to prevent.
log_recorder_session() {
  local hook="${1:-plan_status_validate}"
  local sid repo target sentinel
  sid=$(jq -r '.session_id // empty' <<<"$_HOOK_INPUT" 2>/dev/null || true)
  [ -z "$sid" ] && return 0

  # Keyed by ledger path as well as session: one session can legitimately write
  # to two ledgers (a plan doc in one repo, then another), and each needs its
  # own marker or the second ledger looks recorder-less.
  target=$(_transition_log_file)
  sentinel="${TMPDIR:-/tmp}/claude-recorder-$(printf '%s%s' "$sid" "$target" | cksum | tr -d ' \t')"
  [ -e "$sentinel" ] && return 0
  : > "$sentinel" 2>/dev/null || true

  mkdir -p "$(dirname "$target")" 2>/dev/null || true
  repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  # `kind` is present only on markers. Every record predating this is an edge and
  # carries no `kind`, so the reader treats absent-kind as a transition and the
  # existing ledger stays readable without a migration.
  printf '{"ts":"%s","kind":"session","session":"%s","repo":"%s","recorder":"%s"}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$sid" "$repo" "$hook" \
    >> "$target" || true
}

PASS_LOG_FILE="${CLAUDE_TELEMETRY_DIR}/.hook-pass-log.jsonl"

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
