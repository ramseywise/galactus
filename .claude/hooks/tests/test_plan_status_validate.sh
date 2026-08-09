#!/usr/bin/env bash
# End-to-end tests for plan_status_validate.sh — the real hook, real JSON payloads on
# stdin, real files in a temp dir. Mirroring the logic would not catch the defect this
# file exists for — the house pattern (docs_hygiene.sh) exits 10 under `set -e`, not 0.
#
# Since #79 the hook BLOCKS: a non-conforming Status exits 2 (the PostToolUse blocking
# code) and a conforming one exits 0. Both directions are asserted — valid docs must exit
# 0 silently, invalid docs must exit 2 with a reason. A hook that always exited 0 would
# pass the valid cases and fail every invalid one, so this suite cannot go green on a
# guard that never fires.

set -euo pipefail

HOOK="$(cd "$(dirname "$0")/.." && pwd)/plan_status_validate.sh"

PASS=0
FAIL=0
pass() { echo "PASS: $1"; (( PASS++ )) || true; }
fail() { echo "FAIL: $1"; (( FAIL++ )) || true; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
PLANS="$TMP/.claude/docs/plans"
mkdir -p "$PLANS"

# --- Harness ---
# run <file-path> -> sets $LAST_RC and $LAST_MSG
LAST_RC=0
LAST_MSG=""
run() {
  local p="$1" err
  err="$TMP/stderr.$$"
  set +e
  printf '{"tool_input":{"file_path":"%s"}}' "$p" | bash "$HOOK" 2>"$err"
  LAST_RC=$?
  set -e
  LAST_MSG=$(cat "$err")
}

# assert_exit0 <label>
assert_exit0() {
  [ "$LAST_RC" -eq 0 ] && pass "exit 0 — $1" || fail "exit $LAST_RC (must be 0) — $1"
}

# assert_blocked <label> — 2 is the PostToolUse blocking code
assert_blocked() {
  [ "$LAST_RC" -eq 2 ] && pass "exit 2 (blocked) — $1" || fail "exit $LAST_RC (must be 2) — $1"
}

# write_doc <name> <content...>
write_doc() { local n="$1"; shift; printf '%b' "$*" > "$PLANS/$n"; }

echo "=== Valid members pass silently (exit 0, no warning) ==="
# EXECUTED and SUPERSEDED carry their required companion fields.
declare -a VALID=(
  "RESEARCH|Status: RESEARCH\n"
  "RESEARCHED|Status: RESEARCHED\n"
  "PLANNED|Status: PLANNED\n"
  "REFINED|Status: REFINED\n"
  "READY|Status: READY\n"
  "IN_PROGRESS|Status: IN_PROGRESS\n"
  "EXECUTED|Status: EXECUTED\nReview: pending\n"
  "COMPLETE|Status: COMPLETE\n"
  "SUPERSEDED|Status: SUPERSEDED\nSuperseded-by: 2026-07-19-other.md\n"
)
for entry in "${VALID[@]}"; do
  name="${entry%%|*}"; body="${entry#*|}"
  write_doc "v-$name.md" "$body"
  run "$PLANS/v-$name.md"
  assert_exit0 "valid $name"
  [ -z "$LAST_MSG" ] && pass "silent — valid $name" || fail "warned on valid $name: $LAST_MSG"
done

echo "=== Non-conforming values are rejected (exit 2, with a reason) ==="
# label|content|expected substring in the warning
declare -a BAD=(
  "space form|Status: IN PROGRESS\n|not a canonical state"
  "lowercase hyphen|Status: in-progress\n|not a canonical state"
  "bogus value|Status: BOGUS\n|not a canonical state"
  "suffix|Status: EXECUTED — pending /workflow-review\nReview: pending\n|carries a suffix"
  "EXECUTED without Review|Status: EXECUTED\n|requires a 'Review:' line"
  "SUPERSEDED without pointer|Status: SUPERSEDED\n|requires a 'Superseded-by:' line"
)
i=0
for entry in "${BAD[@]}"; do
  i=$((i+1))
  label="${entry%%|*}"; rest="${entry#*|}"
  body="${rest%|*}"; want="${rest##*|}"
  write_doc "b-$i.md" "$body"
  run "$PLANS/b-$i.md"
  assert_blocked "invalid: $label"
  case "$LAST_MSG" in
    *"$want"*) pass "explains — $label" ;;
    *) fail "no reason matching '$want' — $label (got: ${LAST_MSG:-<empty>})" ;;
  esac
done

echo "=== Scope: only plan docs are validated ==="
printf 'Status: BOGUS\n' > "$TMP/outside.md"
run "$TMP/outside.md"
assert_exit0 "non-plan-doc path"
[ -z "$LAST_MSG" ] && pass "silent — non-plan-doc path ignored" || fail "fired outside docs/plans: $LAST_MSG"

mkdir -p "$TMP/.claude/docs/research"
printf 'Status: BOGUS\n' > "$TMP/.claude/docs/research/r.md"
run "$TMP/.claude/docs/research/r.md"
assert_exit0 "sibling docs/ dir"
[ -z "$LAST_MSG" ] && pass "silent — docs/research ignored" || fail "fired on docs/research: $LAST_MSG"

echo "=== Edge cases ==="
run "$PLANS/does-not-exist.md"
assert_exit0 "missing file"

write_doc "no-status.md" "# A plan with no Status line\n\nSome prose.\n"
run "$PLANS/no-status.md"
assert_exit0 "no Status line"
[ -z "$LAST_MSG" ] && pass "silent — no Status line (presence is #75's concern)" || fail "warned on absent Status: $LAST_MSG"

write_doc "leading-ws.md" "  Status: BOGUS\n"
run "$PLANS/leading-ws.md"
assert_blocked "leading whitespace"
case "$LAST_MSG" in *"not a canonical state"*) pass "detects leading-whitespace form" ;; *) fail "missed leading-whitespace form" ;; esac

write_doc "bold.md" "**Status**: BOGUS\n"
run "$PLANS/bold.md"
assert_blocked "bold key form"
case "$LAST_MSG" in *"not a canonical state"*) pass "detects bold key form" ;; *) fail "missed bold key form" ;; esac

echo
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
