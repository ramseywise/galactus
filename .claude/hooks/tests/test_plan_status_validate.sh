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

# Redirect the transition ledger into the temp dir. Without this the suite writes
# its fixture edges into the operator's real `plan-transitions.jsonl` — the
# ledger whose whole purpose is counting transitions a human actually made. A
# measurement a test run can increment measures the test run.
export GALACTUS_TRANSITION_LOG="$TMP/plan-transitions.jsonl"
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
  # Every member of the Review: vocabulary, not only the one /proto-execute writes.
  # `failed` and `blocked` are the outcomes that hold a doc AT EXECUTED; a hook that
  # accepted only `pending` and `passed` would make a failed review unrecordable and
  # push writers to lie about the outcome to get past the gate.
  "EXECUTED-passed|Status: EXECUTED\nReview: passed\n"
  "EXECUTED-failed|Status: EXECUTED\nReview: failed\n"
  "EXECUTED-blocked|Status: EXECUTED\nReview: blocked\n"
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
  # COMPLETE's companions are checked by VALUE, not presence. The c-* section below
  # covers the same three shapes; these entries additionally pin the wording, so a
  # rewrite that keeps blocking but stops explaining why still fails here.
  "COMPLETE at Review: pending|Status: COMPLETE\nReview: pending\nCompleted: 2026-08-14\n|requires 'Review: passed'"
  "COMPLETE without Completed|Status: COMPLETE\nReview: passed\n|requires a 'Completed:' date"
  "COMPLETE without Review|Status: COMPLETE\nCompleted: 2026-08-14\n|must read 'passed'"
  # Review: is an enum, not free text. Without these the field would satisfy
  # EXECUTED's requirement by presence alone, which is the stuck-at-pending shape
  # in a different disguise: any prose after the colon would count as an outcome.
  "Review: not run|Status: EXECUTED\nReview: not run\n|is not a valid outcome"
  "Review with suffix|Status: EXECUTED\nReview: passed with nits\n|exactly one token"
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

# The filter must not become an escape hatch. Every case above proves the hook
# ignores what is INSIDE a fence; this one proves the presence of a fence does not
# make it ignore what is outside — the direction in which a fence-filter bug is a
# silent bypass rather than a false reject.
write_doc "f-plus-bad.md" "Status: BOGUS\n\n\`\`\`\nStatus: COMPLETE\n\`\`\`\n"
run "$PLANS/f-plus-bad.md"
assert_blocked "unfenced BOGUS beside a fence"
case "$LAST_MSG" in *"not a canonical state"*) pass "fence filter is not an escape hatch" ;; *) fail "fence filter swallowed a real violation" ;; esac

echo
echo "=== From: validates against the legal-edge table ==="
# These cases test the EDGE TABLE, which is still this hook's job: they prove a
# declared-illegal edge is rejected. They do not prove the writer told the truth
# about the prior state, and they are not meant to — that is verified against the
# doc on disk by plan_transition_validate.sh (PreToolUse), whose own suite is
# test_plan_transition_validate.sh. The two hooks answer different questions:
# this one owns "is that edge legal", the other owns "was that prior state there".

write_doc "e-legal.md" "Status: EXECUTED\nReview: pending\nFrom: IN_PROGRESS\n"
run "$PLANS/e-legal.md"
assert_exit0 "legal edge IN_PROGRESS → EXECUTED"

# The edge /proto-execute declares at step 2. Together with the case above it,
# these two cover the execute→review handoff that previously went unrecorded:
# READY → IN_PROGRESS → EXECUTED. Both halves must hold for the D10 loop-back
# count to be measurable, since a missing From: leaves no traversal to count.
write_doc "e-start.md" "Status: IN_PROGRESS\nFrom: READY\n"
run "$PLANS/e-start.md"
assert_exit0 "legal edge READY → IN_PROGRESS"

# The waved-through path: /proto-execute run on a doc that never cleared refine.
# The skill is told to name the state it actually found, so this is the shape a
# truthful writer produces there — and the gate rejecting it is the point.
write_doc "e-skipgate.md" "Status: IN_PROGRESS\nFrom: PLANNED\n"
run "$PLANS/e-skipgate.md"
assert_blocked "illegal edge PLANNED → IN_PROGRESS (refine gate skipped)"

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

# --- The transition ledger (step 4) -------------------------------------------
# The hook is the only component that sees every accepted edge, so it is the only
# place D10 — the loop-back count — can be recorded. Three properties matter, and
# each one is a way the count could lie:
#
#   1. an accepted edge is recorded (or the count undercounts)
#   2. a *rejected* edge is not (or an attempt inflates the count it exists to measure)
#   3. a non-transition write is not (or prose edits bury the traversals in noise)

# ledger_count <from> <to> -> number of matching records
ledger_count() {
  grep -c "\"from\":\"$1\",\"to\":\"$2\"" "$GALACTUS_TRANSITION_LOG" 2>/dev/null || true
}

: > "$GALACTUS_TRANSITION_LOG"

write_doc "t-accept.md" "Status: EXECUTED\nFrom: IN_PROGRESS\nReview: pending\n"
run "$PLANS/t-accept.md"
[ "$(ledger_count IN_PROGRESS EXECUTED)" -eq 1 ] \
  && pass "ledger records an accepted edge" \
  || fail "ledger records an accepted edge (got $(ledger_count IN_PROGRESS EXECUTED))"

# The loop-back itself — the edge D10 counts and the corpus has never shown.
write_doc "t-loopback.md" "Status: PLANNED\nFrom: EXECUTED\n"
run "$PLANS/t-loopback.md"
[ "$(ledger_count EXECUTED PLANNED)" -eq 1 ] \
  && pass "ledger records the EXECUTED -> PLANNED loop-back (D10)" \
  || fail "ledger records the EXECUTED -> PLANNED loop-back (D10)"

# A blocked write never landed, so the transition did not happen. Counting the
# attempt would inflate exactly the number the ledger exists to measure.
write_doc "t-reject.md" "Status: COMPLETE\nFrom: IN_PROGRESS\nReview: passed\nCompleted: 2026-08-14\n"
run "$PLANS/t-reject.md"
assert_blocked "illegal edge is rejected — precondition for the next assertion"
[ "$(ledger_count IN_PROGRESS COMPLETE)" -eq 0 ] \
  && pass "ledger does NOT record a rejected edge" \
  || fail "ledger does NOT record a rejected edge"

# Most writes to a plan doc are prose edits, not transitions. `From:` absent is
# the signal for "this was not an edge" — recording those buries the traversals.
before=$(wc -l < "$GALACTUS_TRANSITION_LOG")
write_doc "t-prose.md" "Status: PLANNED\n\nSome prose, no From: line.\n"
run "$PLANS/t-prose.md"
assert_exit0 "a write with no From: is valid — not every write is a transition"
[ "$(wc -l < "$GALACTUS_TRANSITION_LOG")" -eq "$before" ] \
  && pass "ledger does NOT record a write that declares no From:" \
  || fail "ledger does NOT record a write that declares no From:"

# --- The recorder marker (galactus#20 fix direction 2) ------------------------
# The ledger above records edges *traversed*. That leaves one thing unsaid: a
# session where nothing moved is byte-identical to a session where no recorder
# ran — the failure #20 hit, where the wrong copy of this hook won and recorded
# nothing at all. A once-per-session marker is what makes the difference legible.
#
# `run()` deliberately sends no session_id, which is why nothing above emitted a
# marker. That is itself the first property: no id, no marker — never an
# invented one.

# run_sid <session-id> <path> — the payload the harness actually supplies.
run_sid() {
  local sid="$1" p="$2" err
  err="$TMP/stderr.$$"
  set +e
  printf '{"session_id":"%s","tool_input":{"file_path":"%s"}}' "$sid" "$p" | bash "$HOOK" 2>"$err"
  LAST_RC=$?
  set -e
  LAST_MSG=$(cat "$err")
}

marker_count() {
  grep -c "\"kind\":\"session\",\"session\":\"$1\"" "$GALACTUS_TRANSITION_LOG" 2>/dev/null || true
}

[ "$(grep -c '"kind":"session"' "$GALACTUS_TRANSITION_LOG" 2>/dev/null || true)" -eq 0 ] \
  && pass "no session_id yields no marker — the hook never invents a session identity" \
  || fail "no session_id yields no marker"

# Marker fixtures need their own TMPDIR: the once-per-session latch is a sentinel
# file, and a stale one from an earlier run would silently suppress the marker,
# turning this section green for the wrong reason.
export TMPDIR="$TMP/sentinels"
mkdir -p "$TMPDIR"

# The case the marker exists for: a validate pass that moved nothing. Every
# assertion above this point involves an edge; this one has none, which is
# exactly why the edge ledger alone could not witness it.
: > "$GALACTUS_TRANSITION_LOG"
write_doc "m-prose.md" "Status: PLANNED\n\nProse only, no From: line.\n"
run_sid "SESS-A" "$PLANS/m-prose.md"
assert_exit0 "a no-transition write still passes"
[ "$(marker_count SESS-A)" -eq 1 ] \
  && pass "a pass with NO transition still marks the recorder alive" \
  || fail "a pass with NO transition still marks the recorder alive"
[ "$(grep -vc '"kind":"session"' "$GALACTUS_TRANSITION_LOG" 2>/dev/null || true)" -eq 0 ] \
  && pass "the marker is not an edge — it adds no transition record" \
  || fail "the marker is not an edge"

# Once per session, not once per write. The ledger is never rotated, so a marker
# on every write would bury the edges it exists to contextualize. This also
# covers the merged-settings double-fire: both hook copies run, one marker lands.
run_sid "SESS-A" "$PLANS/m-prose.md"
run_sid "SESS-A" "$PLANS/m-prose.md"
[ "$(marker_count SESS-A)" -eq 1 ] \
  && pass "the marker is latched — one per session, not one per write" \
  || fail "the marker is latched (got $(marker_count SESS-A))"

# A different session is a different marker: that is what makes a *gap* visible
# rather than inferred.
run_sid "SESS-B" "$PLANS/m-prose.md"
[ "$(marker_count SESS-B)" -eq 1 ] \
  && pass "a second session records its own marker" \
  || fail "a second session records its own marker"

# A rejected write means the recorder ran and disagreed. It was still alive, and
# the marker must say so — otherwise a session that only ever wrote invalid docs
# reads as no recorder at all.
run_sid "SESS-C" "$PLANS/t-reject.md"
assert_blocked "illegal edge still rejected under a session id"
[ "$(marker_count SESS-C)" -eq 0 ] \
  && pass "a blocked write records no marker — the doc never landed" \
  || fail "a blocked write records no marker"

# --- The backfill marker ------------------------------------------------------
# Reconciling a stranded doc with work already merged walks real edges. They are
# edits, not cycles, and the ledger they land in is the sole input to the
# loop-back rate — so the writer says which kind it wrote and the reader
# (review/transitions.py) excludes the reconciliation ones from every count.
#
# Two properties, and the second is the one that would silently break: the flag
# must not become part of the dedup key, or the same edge written once
# backfilled and once live would stop collapsing and re-open the double-count
# bug the tail -1 guard exists to prevent.

: > "$GALACTUS_TRANSITION_LOG"

write_doc "b-fill.md" "Status: EXECUTED\nFrom: IN_PROGRESS\nReview: pending\n"
GALACTUS_BACKFILL=1 run "$PLANS/b-fill.md"
assert_exit0 "a backfilled edge is still validated like any other"
[ "$(grep -c '"backfill":true' "$GALACTUS_TRANSITION_LOG" 2>/dev/null || true)" -eq 1 ] \
  && pass "GALACTUS_BACKFILL marks the edge it wrote" \
  || fail "GALACTUS_BACKFILL marks the edge it wrote"

: > "$GALACTUS_TRANSITION_LOG"
write_doc "b-live.md" "Status: EXECUTED\nFrom: IN_PROGRESS\nReview: pending\n"
run "$PLANS/b-live.md"
[ "$(grep -c '"backfill"' "$GALACTUS_TRANSITION_LOG" 2>/dev/null || true)" -eq 0 ] \
  && pass "an unflagged edge carries no backfill key — absence means live" \
  || fail "an unflagged edge carries no backfill key"

# The dedup guard is edge-scoped, so the merged-settings double-fire collapses
# whether or not the flag is set. Simulated here by running the hook twice on
# one doc, which is what two registered copies of it do on a single Write.
: > "$GALACTUS_TRANSITION_LOG"
write_doc "b-dedup.md" "Status: EXECUTED\nFrom: IN_PROGRESS\nReview: pending\n"
GALACTUS_BACKFILL=1 run "$PLANS/b-dedup.md"
GALACTUS_BACKFILL=1 run "$PLANS/b-dedup.md"
[ "$(wc -l < "$GALACTUS_TRANSITION_LOG")" -eq 1 ] \
  && pass "the backfill flag stays out of the dedup key" \
  || fail "the backfill flag stays out of the dedup key ($(wc -l < "$GALACTUS_TRANSITION_LOG") records)"

# --- The double-fire is CONCURRENT ---------------------------------------------
# Every dedup case above runs the hook in SERIES, which the `tail -1` read collapses
# on its own. Two registered copies fired on one Write overlap: both read the ledger
# before either appends, both miss the match, both write. That is not hypothetical —
# it produced two records for one edge at an identical timestamp in the real galactus
# ledger on 2026-08-15, which is the double count the guard exists to prevent
# occurring inside the guard. Series-only coverage is why it went unseen.

: > "$GALACTUS_TRANSITION_LOG"
write_doc "b-race.md" "Status: EXECUTED\nFrom: IN_PROGRESS\nReview: pending\n"
printf '{"tool_input":{"file_path":"%s"}}' "$PLANS/b-race.md" > "$TMP/race.json"
for _ in 1 2 3 4 5 6 7 8; do
  bash "$HOOK" < "$TMP/race.json" >/dev/null 2>&1 &
done
wait || true
RACE_N=$(wc -l < "$GALACTUS_TRANSITION_LOG")
[ "$RACE_N" -eq 1 ] \
  && pass "concurrent double-fire collapses to one record" \
  || fail "concurrent double-fire collapses to one record (got $RACE_N)"

# The lock must not outlive the call. A leaked lock directory makes every later write
# pay the full timeout and then append unlocked — the race back, plus a 1s stall on
# every plan-doc edit.
[ ! -d "${GALACTUS_TRANSITION_LOG}.lock" ] \
  && pass "the ledger lock is released, not leaked" \
  || fail "the ledger lock is released, not leaked"

echo "=== spike/* branches skip validation; other branches do not ==="
# Spikes carry no plan doc by design, so the state machine stands down there. The
# control case on a feature branch proves the skip is the branch, not the fixture.
SPIKE="$TMP/spike-repo"
mkdir -p "$SPIKE/.claude/docs/plans"
git -C "$SPIKE" init -q -b spike/try-a-thing
printf 'Status: BOGUS\n' > "$SPIKE/.claude/docs/plans/s.md"
run "$SPIKE/.claude/docs/plans/s.md"
assert_exit0 "invalid Status on a spike/* branch"
git -C "$SPIKE" checkout -q -b GAL-1-feature
run "$SPIKE/.claude/docs/plans/s.md"
[ "$LAST_RC" -eq 2 ] && pass "same doc on a feature branch is rejected" || fail "same doc on a feature branch exited $LAST_RC (must be 2)"

echo
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
