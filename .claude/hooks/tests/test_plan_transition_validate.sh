#!/usr/bin/env bash
# End-to-end tests for plan_transition_validate.sh — the real hook, real JSON payloads
# on stdin, real files in a temp dir. House pattern, mirroring test_plan_status_validate.sh.
#
# This suite must fail in BOTH directions, and that is the point:
#
#   - Stub the hook to `exit 0` and cases 2 and 6 break — it cannot go green on a
#     guard that never fires.
#   - Remove the restatement branch and cases 13-17 break — it cannot go green on a
#     guard that fires too often.
#
# The second property is the one this file exists for. The original 12-case design
# constructed every fragment as a transition *event*, so a hook that blocked every
# settled doc in the repo would have passed all twelve. Cases 15-16 therefore read
# REAL corpus docs rather than fixtures: a fixture drifts, and drift here restores
# exactly the blind spot that let the defect through.

set -euo pipefail

HOOKS="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$HOOKS/plan_transition_validate.sh"
REPO="$(cd "$HOOKS/../.." && pwd)"

PASS=0
FAIL=0
pass() { echo "PASS: $1"; (( PASS++ )) || true; }
fail() { echo "FAIL: $1"; (( FAIL++ )) || true; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Redirect the ledger into the temp dir. This hook does not write edges, but it
# sources lib.sh, which resolves ledger paths at source time. A suite that can
# increment the operator's real transition count measures the test run.
export GALACTUS_TRANSITION_LOG="$TMP/plan-transitions.jsonl"
export CLAUDE_TELEMETRY_DIR="$TMP"
PLANS="$TMP/.claude/docs/plans"
mkdir -p "$PLANS"

LAST_RC=0
LAST_MSG=""

# run_pre <file-path> <prior-doc-content> <fragment> [shape]
#
# Two inputs where the old harness had one: the PRIOR doc goes to disk first, then
# the FRAGMENT is fed as the tool payload. That split is the whole difference
# between PostToolUse and PreToolUse — `prior` is observed, not declared.
# shape: "edit" (default, .new_string) or "write" (.content).
run_pre() {
  local p="$1" prior="$2" frag="$3" shape="${4:-edit}" err key
  err="$TMP/stderr.$$"
  if [ -n "$prior" ]; then printf '%b' "$prior" > "$p"; else rm -f "$p"; fi
  key="new_string"; [ "$shape" = "write" ] && key="content"
  # Payload to a file, then redirect — NOT a pipe. A hook that exits without
  # draining stdin gives the writing `printf` a SIGPIPE, and a pipeline reports the
  # LAST command's status, so `printf | bash "$HOOK"` yields 141 (SIGPIPE) instead
  # of the hook's own exit code. That masks every result: under an `exit 0` stub
  # this harness reported exit 1 for all 22 cases, including the ones that should
  # have passed. A redirect has no second process to fail.
  printf '{"tool_input":{"file_path":"%s","%s":%s}}' \
    "$p" "$key" "$(printf '%b' "$frag" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')" \
    > "$TMP/payload.json"
  set +e
  bash "$HOOK" < "$TMP/payload.json" 2>"$err"
  LAST_RC=$?
  set -e
  LAST_MSG=$(cat "$err")
}

# run_pre_file <file-path> <prior-file> <fragment-file> [shape] — corpus cases.
run_pre_file() {
  local p="$1" priorfile="$2" fragfile="$3" shape="${4:-edit}" err key
  err="$TMP/stderr.$$"
  cp "$priorfile" "$p"
  key="new_string"; [ "$shape" = "write" ] && key="content"
  # Redirect, not a pipe — see the SIGPIPE note in run_pre.
  printf '{"tool_input":{"file_path":"%s","%s":%s}}' \
    "$p" "$key" "$(python3 -c 'import json,sys;print(json.dumps(open(sys.argv[1]).read()))' "$fragfile")" \
    > "$TMP/payload.json"
  set +e
  bash "$HOOK" < "$TMP/payload.json" 2>"$err"
  LAST_RC=$?
  set -e
  LAST_MSG=$(cat "$err")
}

assert_exit0()   { [ "$LAST_RC" -eq 0 ] && pass "exit 0 — $1" || fail "exit $LAST_RC (must be 0) — $1: $LAST_MSG"; }
assert_blocked() { [ "$LAST_RC" -eq 2 ] && pass "exit 2 (blocked) — $1" || fail "exit $LAST_RC (must be 2) — $1"; }

D="$PLANS/p.md"

echo "=== The core contract: truthful passes, the lie blocks ==="

# Case 1 — truthful single-fragment transition.
run_pre "$D" 'Status: IN_PROGRESS\nTrack: agent\n' 'Status: EXECUTED\nFrom: IN_PROGRESS\n'
assert_exit0 "case 1: truthful IN_PROGRESS -> EXECUTED"

# Case 2 — THE LIE. This is issue #14's "Done when": the doc is at PLANNED, the
# write claims it came from IN_PROGRESS. PostToolUse cannot catch this (the edge
# IN_PROGRESS -> EXECUTED is legal); only a pre-write observer can.
run_pre "$D" 'Status: PLANNED\nTrack: agent\n' 'Status: EXECUTED\nFrom: IN_PROGRESS\n'
assert_blocked "case 2: declares From: IN_PROGRESS but doc is at PLANNED"
case "$LAST_MSG" in
  *"on disk"*PLANNED*) pass "case 2: message names the observed state" ;;
  *) fail "case 2: message must name the observed state — got: $LAST_MSG" ;;
esac

echo "=== The fragment rule: partial fragments pass untouched ==="

# Case 3 — Status: without From:. Most writes look like this.
run_pre "$D" 'Status: PLANNED\n' 'Status: REFINED\n'
assert_exit0 "case 3: Status: without From: (fragment rule)"

# Case 4 — the two-Edit Status:/Review: pair. plan_status_validate.sh:164 permits
# this by design, so the intermediate state is legal and must stay legal.
run_pre "$D" 'Status: PLANNED\n' 'Review: passed\n'
assert_exit0 "case 4: Review:-only Edit (the two-Edit pair)"

echo "=== Origin writes ==="

# Case 5 — no file on disk, no From: declared.
run_pre "$D" '' 'Status: RESEARCHED\n'
assert_exit0 "case 5: origin write with no From:"

# Case 6 — origin write DECLARING a prior state that never existed.
run_pre "$D" '' 'Status: PLANNED\nFrom: RESEARCHED\n'
assert_blocked "case 6: origin write declares From: RESEARCHED"

echo "=== Fenced content is not a declaration ==="

# Case 7 — a fenced example containing From: must not be read as declaring one.
run_pre "$D" 'Status: PLANNED\n' 'Status: REFINED\n\n```\nFrom: EXECUTED\n```\n'
assert_exit0 "case 7: From: inside a fence is not a declaration"

# Case 8 — the prior doc's real Status: follows a fenced decoy.
run_pre "$D" '```\nStatus: COMPLETE\n```\nStatus: PLANNED\n' 'Status: REFINED\nFrom: PLANNED\n'
assert_exit0 "case 8: fenced Status: in prior doc ignored, real one used"

echo "=== Tolerant field forms and both payload shapes ==="

# Case 9 — bold markers are the same declaration.
run_pre "$D" '**Status**: PLANNED\n' '**From**: PLANNED\n**Status**: REFINED\n'
assert_exit0 "case 9: bold **Status**: / **From**: forms"

# Case 10 — Write payload (.content) rather than Edit (.new_string). Step 2.
run_pre "$D" 'Status: PLANNED\n' 'Status: REFINED\nFrom: PLANNED\n' write
assert_exit0 "case 10: Write payload shape (.content)"

# Case 10b — the lie must block through the Write shape too, or Step 2's
# coalescing is only half-verified.
run_pre "$D" 'Status: PLANNED\n' 'Status: EXECUTED\nFrom: IN_PROGRESS\n' write
assert_blocked "case 10b: the lie blocks through the Write shape"

echo "=== Path guard ==="

# Case 11 — a non-plan path is not this hook's business, even with a lying From:.
NONPLAN="$TMP/src-x.md"
run_pre "$NONPLAN" 'Status: PLANNED\n' 'Status: EXECUTED\nFrom: IN_PROGRESS\n'
assert_exit0 "case 11: non-plan path passes (path guard)"

echo "=== D10: the loop-back must survive ==="

# Case 12 — EXECUTED -> PLANNED is the edge the entire D10 measurement exists to
# count. A hook that rejected it would destroy the measurement rather than harden it.
run_pre "$D" 'Status: EXECUTED\n' 'Status: PLANNED\nFrom: EXECUTED\n'
assert_exit0 "case 12: EXECUTED -> PLANNED loop-back (D10)"

echo "=== FA-001 regression: settled docs stay writable ==="

# Case 13 — a settled doc rewritten with its own unmodified front matter. `From:`
# persists after the write, so this pair is the RESTING STATE, not an event.
run_pre "$D" 'Status: COMPLETE\nFrom: EXECUTED\nReview: passed\n' \
             'Status: COMPLETE\nFrom: EXECUTED\nReview: passed\n'
assert_exit0 "case 13: settled doc restated verbatim (Edit)"

# Case 14 — same, as a Write payload. A full-file rewrite is the common shape here.
run_pre "$D" 'Status: COMPLETE\nFrom: EXECUTED\nReview: passed\n' \
             'Status: COMPLETE\nFrom: EXECUTED\nReview: passed\n' write
assert_exit0 "case 14: settled doc restated verbatim (Write)"

# Cases 15-16 — REAL corpus docs, not fixtures. These are the two docs that carry a
# persistent From:; both were false-rejected by the pre-revision logic.
#
# The corpus is a SEPARATE root from the hook. This file is vendored into every repo
# that carries the hook, but only some of those repos hold plan docs — the operator's
# `~/.claude` deliberately holds none. Defaulting the root to $REPO and hard-failing
# when it is absent would make the global copy permanently red for a corpus it is not
# supposed to have; skipping silently would restore the blind spot cases 15-16 exist
# to close. So: no corpus is an announced SKIP, an EMPTY corpus is a failure, and a
# corpus missing one of the two named docs is drift and still fails.
CORPUS_DIR="${PLAN_CORPUS_ROOT:-$REPO}/.claude/docs/plans"
CORPUS_A="$CORPUS_DIR/2026-08-14-gal-17-customer-segmentation.md"
CORPUS_B="$CORPUS_DIR/2026-08-14-orchestrator-design.md"

if [ ! -d "$CORPUS_DIR" ]; then
  echo "SKIP: cases 15-16 + corpus sweep — no plan corpus at $CORPUS_DIR"
  echo "      re-run with PLAN_CORPUS_ROOT=/path/to/a/repo to exercise them"
  CORPUS_DIR=""
fi

if [ -z "$CORPUS_DIR" ]; then
  :
elif [ -f "$CORPUS_A" ]; then
  head -12 "$CORPUS_A" > "$TMP/frag_a.md"
  run_pre_file "$D" "$CORPUS_A" "$TMP/frag_a.md"
  assert_exit0 "case 15: real gal-17 doc, own front matter as fragment"
else
  fail "case 15: corpus doc missing — $CORPUS_A"
fi

if [ -z "$CORPUS_DIR" ]; then
  :
elif [ -f "$CORPUS_B" ]; then
  head -12 "$CORPUS_B" > "$TMP/frag_b.md"
  run_pre_file "$D" "$CORPUS_B" "$TMP/frag_b.md"
  assert_exit0 "case 16: real orchestrator-design doc, own front matter as fragment"
else
  fail "case 16: corpus doc missing — $CORPUS_B"
fi

# Case 17 — branch ORDERING. The fragment declares a false From:, but Status: does
# not move, so no edge is asserted and there is nothing to catch. This is the one
# case that fails if the restatement branch is placed after the mismatch check.
run_pre "$D" 'Status: PLANNED\nFrom: RESEARCHED\n' 'Status: PLANNED\nFrom: EXECUTED\n'
assert_exit0 "case 17: false From: with no move (restatement precedes mismatch)"

echo "=== Whole-corpus sweep: no doc in the repo is false-rejected ==="

# The cheapest whole-system check, and the one that would have caught FA-001 with no
# reasoning at all. Every plan doc, fed its own front matter. Any block here is a
# false reject on a file already committed to the repo.
SWEPT=0
BLOCKED_DOCS=""
if [ -n "$CORPUS_DIR" ]; then
  for f in "$CORPUS_DIR"/*.md; do
    [ -f "$f" ] || continue
    head -12 "$f" > "$TMP/frag_sweep.md"
    run_pre_file "$D" "$f" "$TMP/frag_sweep.md"
    SWEPT=$(( SWEPT + 1 ))
    [ "$LAST_RC" -ne 0 ] && BLOCKED_DOCS="$BLOCKED_DOCS $(basename "$f")"
  done
fi
if [ -z "$CORPUS_DIR" ]; then
  :
elif [ "$SWEPT" -eq 0 ]; then
  # A corpus directory with no docs in it passes the loop trivially. That is the
  # vacuous green the sweep is least able to survive: it reads identically to
  # "every doc was checked" in the RESULT line.
  fail "corpus sweep: $CORPUS_DIR exists but holds no plan docs — sweep proved nothing"
elif [ -z "$BLOCKED_DOCS" ]; then
  pass "corpus sweep: $SWEPT docs, 0 false rejects"
else
  fail "corpus sweep: false-rejected —$BLOCKED_DOCS"
fi

echo "=== Step 7: LEGAL_EDGES drift between the two hooks ==="

# Open Question 5 accepted duplicating the table rather than sourcing a shared file
# (both hooks embed their Python as a heredoc; sharing means a third file in a
# permission-denied directory). That is only safe with a mechanical check, or the
# tables diverge the first time an edge is added and the error messages start
# disagreeing with the enforcement.
#
# Byte equality of the normalized block, not a semantic comparison: a divergence is
# a bug even if the two tables happen to describe the same set.
extract_edges() {
  sed -n '/^LEGAL_EDGES = {/,/^}/p' "$1" | tr -d ' \n'
}
a=$(extract_edges "$HOOKS/plan_status_validate.sh")
b=$(extract_edges "$HOOK")

# This hook deliberately does NOT carry LEGAL_EDGES: it never re-checks the edge
# (plan_status_validate.sh:215 owns that on the resulting file), so duplicating the
# table would be dead code that can drift. The drift test therefore asserts the
# table exists in exactly one place — which is a stronger guarantee than keeping
# two copies identical, and is why Open Question 5's concern does not apply.
if [ -n "$a" ]; then
  pass "drift: LEGAL_EDGES present in plan_status_validate.sh (the owner)"
else
  fail "drift: extractor found no LEGAL_EDGES in plan_status_validate.sh — sed range is wrong"
fi

if [ -z "$b" ]; then
  pass "drift: plan_transition_validate.sh carries no duplicate table (cannot diverge)"
else
  fail "drift: plan_transition_validate.sh now carries LEGAL_EDGES — two tables can diverge"
fi

echo
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
