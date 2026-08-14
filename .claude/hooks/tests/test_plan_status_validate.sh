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
  "COMPLETE|Status: COMPLETE\nReview: passed\nCompleted: 2026-08-14\n"
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
  "suffix|Status: EXECUTED — pending /proto-review\nReview: pending\n|carries a suffix"
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

echo "=== Track: is validated when present, never required ==="
# The line is optional by design: every plan doc written before the router lacks
# it, and requiring it would make all of them instantly unwritable.

write_doc "t-absent.md" "Status: READY\n\nNo track line here.\n"
run "$PLANS/t-absent.md"
assert_exit0 "no Track line (legacy docs stay writable)"
[ -z "$LAST_MSG" ] && pass "silent — absent Track is valid" || fail "warned on absent Track: $LAST_MSG"

for t in ml agent; do
  write_doc "t-$t.md" "Status: READY\nTrack: $t\n"
  run "$PLANS/t-$t.md"
  assert_exit0 "valid Track: $t"
  [ -z "$LAST_MSG" ] && pass "silent — valid Track: $t" || fail "warned on valid Track $t: $LAST_MSG"
done

write_doc "t-bogus.md" "Status: READY\nTrack: nonsense\n"
run "$PLANS/t-bogus.md"
assert_blocked "invalid Track value"
case "$LAST_MSG" in *"not a valid track"*) pass "explains — invalid Track" ;; *) fail "no reason for invalid Track (got: ${LAST_MSG:-<empty>})" ;; esac

write_doc "t-suffix.md" "Status: READY\nTrack: ml — because it is tabular\n"
run "$PLANS/t-suffix.md"
assert_blocked "Track with a suffix"
case "$LAST_MSG" in *"exactly one token"*) pass "explains — Track suffix" ;; *) fail "no reason for Track suffix (got: ${LAST_MSG:-<empty>})" ;; esac

write_doc "t-bold.md" "Status: READY\n  **Track**: nonsense\n"
run "$PLANS/t-bold.md"
assert_blocked "bold/indented Track form"
case "$LAST_MSG" in *"not a valid track"*) pass "detects bold Track form" ;; *) fail "missed bold Track form" ;; esac

# A Track: line is checked even with no Status: line — the early accept path for
# a Status-less doc must not become a way to smuggle a bad Track past the hook.
write_doc "t-only.md" "# Plan\n\nTrack: nonsense\n"
run "$PLANS/t-only.md"
assert_blocked "bad Track with no Status line"
case "$LAST_MSG" in *"not a valid track"*) pass "explains — Track checked without Status" ;; *) fail "Track unchecked when Status absent" ;; esac

write_doc "t-only-ok.md" "# Plan\n\nTrack: ml\n"
run "$PLANS/t-only-ok.md"
assert_exit0 "valid Track with no Status line"

echo
echo "=== Fenced snippets are not front matter ==="
# A design doc that *documents* the state machine shows Status:/Epistemic: inside
# code fences. Every scan is first-match-wins over lines, so without fence
# filtering a snippet is indistinguishable from a declaration — and the doc that
# specifies a rule gets judged by it. Track: never exposed this because no plan
# doc discusses Track: in a fence at column zero.

# Front matter wins over a later fenced Status:.
write_doc "f-front-wins.md" "Status: PLANNED\nTrack: agent\n\n\`\`\`\nStatus: COMPLETE\nFrom: EXECUTED\n\`\`\`\n"
run "$PLANS/f-front-wins.md"
assert_exit0 "fenced Status: ignored, front matter used"

# A fenced-only bad Status must not register at all — no Status line means the
# doc is accepted, not blocked on the snippet's value.
write_doc "f-only-fenced.md" "# Design\n\n\`\`\`\nStatus: NOT_A_STATE\n\`\`\`\n"
run "$PLANS/f-only-fenced.md"
assert_exit0 "fenced-only bad Status does not register"

# The companion-field scan (has_field) reads the same filtered view: a fenced
# Review: must not satisfy EXECUTED's requirement.
write_doc "f-companion.md" "Status: EXECUTED\n\n\`\`\`\nReview: passed\n\`\`\`\n"
run "$PLANS/f-companion.md"
assert_blocked "fenced Review: does not satisfy EXECUTED"

# A real front-matter companion still satisfies it with a fence present.
write_doc "f-companion-ok.md" "Status: EXECUTED\nReview: pending\n\n\`\`\`\nStatus: COMPLETE\n\`\`\`\n"
run "$PLANS/f-companion-ok.md"
assert_exit0 "real Review: satisfies EXECUTED despite fenced snippet"

# Indented fences (inside a list item) still toggle.
write_doc "f-indented.md" "Status: PLANNED\n\n  \`\`\`\n  Status: NOT_A_STATE\n  \`\`\`\n"
run "$PLANS/f-indented.md"
assert_exit0 "indented fence toggles correctly"

echo
echo "=== From: validates against the legal-edge table ==="
# LIMITATION, recorded deliberately: From: is a SELF-REPORT. PostToolUse runs
# after the write, so the hook cannot read the pre-edit Status: — a writer that
# lies about From: passes whenever the claimed edge happens to be legal. These
# cases prove the table rejects declared-illegal edges, which catches accidental
# skips; they do not and cannot prove a writer told the truth. Closing that gap
# needs a PreToolUse hook and is deferred to its own issue.

write_doc "e-legal.md" "Status: EXECUTED\nReview: pending\nFrom: IN_PROGRESS\n"
run "$PLANS/e-legal.md"
assert_exit0 "legal edge IN_PROGRESS → EXECUTED"

write_doc "e-illegal.md" "Status: EXECUTED\nReview: pending\nFrom: READY\n"
run "$PLANS/e-illegal.md"
assert_blocked "illegal edge READY → EXECUTED"
case "$LAST_MSG" in *"not a legal transition"*) pass "explains — illegal edge" ;; *) fail "no reason for illegal edge (got: ${LAST_MSG:-<empty>})" ;; esac

write_doc "e-absent.md" "Status: EXECUTED\nReview: pending\n"
run "$PLANS/e-absent.md"
assert_exit0 "From: absent is valid (every pre-existing doc lacks it)"

write_doc "e-terminal.md" "Status: COMPLETE\nFrom: EXECUTED\nReview: passed\nCompleted: 2026-08-14\n"
run "$PLANS/e-terminal.md"
assert_exit0 "legal edge EXECUTED → COMPLETE"

# SUPERSEDED is escalation — reachable from anywhere, so no edge check applies.
write_doc "e-sup.md" "Status: SUPERSEDED\nSuperseded-by: other.md\nFrom: RESEARCH\n"
run "$PLANS/e-sup.md"
assert_exit0 "SUPERSEDED reachable from any state"

write_doc "e-badstate.md" "Status: PLANNED\nFrom: NOT_A_STATE\n"
run "$PLANS/e-badstate.md"
assert_blocked "From: with a non-canonical state"

write_doc "e-suffix.md" "Status: REFINED\nFrom: PLANNED — after review\n"
run "$PLANS/e-suffix.md"
assert_blocked "From: with a suffix"

echo
echo "=== Epistemic: gates by value, never by presence ==="
# Coherence, not presence: requiring the field on READY would rebuild the
# `Review: pending` failure (a required field with an override becomes a field
# everyone sets to the override). UNTESTED + READY stays legal AND visible.

write_doc "p-conflicted.md" "Status: READY\nEpistemic: CONFLICTED\n"
run "$PLANS/p-conflicted.md"
assert_blocked "READY + CONFLICTED"
case "$LAST_MSG" in *"not legal while Epistemic"*) pass "explains — READY blocked by epistemic state" ;; *) fail "no reason for READY+CONFLICTED (got: ${LAST_MSG:-<empty>})" ;; esac

write_doc "p-blocked.md" "Status: READY\nEpistemic: BLOCKED\n"
run "$PLANS/p-blocked.md"
assert_blocked "READY + BLOCKED"

write_doc "p-untested.md" "Status: READY\nEpistemic: UNTESTED\n"
run "$PLANS/p-untested.md"
assert_exit0 "READY + UNTESTED is legal and visible by design"

write_doc "p-noconflict.md" "Status: READY\nEpistemic: NO_CONFLICT\n"
run "$PLANS/p-noconflict.md"
assert_exit0 "READY + NO_CONFLICT"

# CONFLICTED is only incoherent with READY — it must not block other states.
write_doc "p-planned.md" "Status: PLANNED\nEpistemic: CONFLICTED\n"
run "$PLANS/p-planned.md"
assert_exit0 "CONFLICTED is legal on a non-READY state"

write_doc "p-badenum.md" "Status: PLANNED\nEpistemic: PROBABLY_FINE\n"
run "$PLANS/p-badenum.md"
assert_blocked "invalid Epistemic enum value"

write_doc "p-absent.md" "Status: READY\n"
run "$PLANS/p-absent.md"
assert_exit0 "Epistemic: absent is valid — the hook never requires it"

# Provenance companions are free-form and must not trip the enum check.
write_doc "p-prov.md" "Status: READY\nEpistemic: NO_CONFLICT\nEpistemic-by: /assumption-audit\nEpistemic-at: 2026-08-14\nEpistemic-findings: 0\n"
run "$PLANS/p-prov.md"
assert_exit0 "Epistemic provenance companions accepted"

# --- COMPLETE checks its companions by value, not presence -------------------
# Status: and Review: are separate Edits, so a doc can transiently sit at
# COMPLETE while Review: still reads pending. COMPLETE asserts an outcome, so
# presence-only validation would certify the exact stuck-at-pending shape this
# build exists to unstick.

write_doc "c-pending.md" "Status: COMPLETE\nFrom: EXECUTED\nReview: pending\nCompleted: 2026-08-14\n"
run "$PLANS/c-pending.md"
assert_blocked "COMPLETE + Review: pending"
case "$LAST_MSG" in *"Review: passed"*) pass "explains — COMPLETE needs a passed review" ;; *) fail "no reason for COMPLETE+pending (got: ${LAST_MSG:-<empty>})" ;; esac

write_doc "c-noreview.md" "Status: COMPLETE\nFrom: EXECUTED\nCompleted: 2026-08-14\n"
run "$PLANS/c-noreview.md"
assert_blocked "COMPLETE with no Review: line"

write_doc "c-nodate.md" "Status: COMPLETE\nFrom: EXECUTED\nReview: passed\n"
run "$PLANS/c-nodate.md"
assert_blocked "COMPLETE with no Completed: date"

write_doc "c-ok.md" "Status: COMPLETE\nFrom: EXECUTED\nReview: passed\nCompleted: 2026-08-14\n"
run "$PLANS/c-ok.md"
assert_exit0 "COMPLETE with Review: passed + Completed:"

# --- Fence detection is by marker and width, not a bare toggle ----------------
# A 4-backtick block wrapping a 3-backtick one is the standard way to document
# fence syntax. A boolean toggled on any ``` desyncs and leaks the inner
# content as front matter; tilde fences bypass a backtick-only matcher entirely.

write_doc "f-nested.md" "Status: PLANNED\n\`\`\`\`\n\`\`\`\nStatus: COMPLETE\n\`\`\`\n\`\`\`\`\n"
run "$PLANS/f-nested.md"
assert_exit0 "nested 4-backtick fence does not leak an inner Status:"

write_doc "f-tilde.md" "Status: PLANNED\n~~~\nStatus: COMPLETE\n~~~\n"
run "$PLANS/f-tilde.md"
assert_exit0 "tilde fence hides its contents like a backtick fence"

# The front-matter value must still win — proof the filter drops the snippet
# rather than merely tolerating it.
write_doc "f-tilde-super.md" "Status: PLANNED\n~~~\nStatus: SUPERSEDED\n~~~\n"
run "$PLANS/f-tilde-super.md"
assert_exit0 "a fenced SUPERSEDED does not trigger the Superseded-by: requirement"

echo
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
