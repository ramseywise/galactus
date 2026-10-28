#!/usr/bin/env bash
#
# PreToolUse guard: verify a declared `From:` against the state actually on disk.
#
# `plan_status_validate.sh` (PostToolUse) owns field presence and the legal-edge
# table. It cannot see the prior state — it reads the file *after* the write — so a
# writer that lies about `From:` passes there whenever the claimed edge is legal.
# This hook is the other half: it runs BEFORE the write, when the file on disk is
# still the prior state, and blocks a `From:` that contradicts it.
#
# Scope is deliberately narrow. It validates only a fragment that carries BOTH
# `From:` and `Status:` AND whose `Status:` differs from the one on disk. Anything
# else passes untouched. See the RESTATEMENT note in the Python block: `From:`
# persists in the doc after the write, so a fragment carrying both fields is the
# resting state of every settled doc, not the signature of a transition.

set -euo pipefail

source "$(dirname "$0")/lib.sh"

path=$(claude_path)
[ -z "$path" ] && exit 0
echo "$path" | grep -q '/\.claude/docs/plans/.*\.md$' || exit 0
on_spike_branch "$path" && exit 0

# The fragment being written. Write carries .content, Edit carries .new_string;
# claude_content() coalesces both (verified against lib.sh:27).
fragment=$(claude_content)
[ -z "$fragment" ] && exit 0

# Deliberate divergence from plan_status_validate.sh:9, which exits 0 when the file
# does not exist. Here a missing file is the ORIGIN case, and an origin write that
# declares a `From:` is claiming a prior state that never existed — exactly the lie
# this hook exists to catch. It is handled in Python as an empty prior, not skipped.
prior_doc=""
[ -f "$path" ] && prior_doc=$(cat "$path")

# The Python block goes to a temp file rather than a heredoc inside `$(...)`.
# Same reason recorded at plan_status_validate.sh:14-18: command substitution
# processes backticks as legacy command substitution *before* the quoted heredoc
# protects them, which mangles the fence regexes below into a syntax error.
_py=$(mktemp -t plan_transition_validate) || exit 0
trap 'rm -f "$_py"' EXIT
cat > "$_py" <<'PY'
import os
import re
import sys

# Read prior doc and fragment as a NUL-delimited pair on stdin. Not argv: a
# fragment is arbitrarily long and can contain anything, including NUL-adjacent
# binary from a botched write.
raw = sys.stdin.read()
prior_doc, _, fragment = raw.partition("\0")


def unfenced(src):
    """Drop fenced code blocks before any field scan.

    Copied verbatim from plan_status_validate.sh:37-69, deliberately. A
    transition validator that disagreed with the field validator about what a
    `Status:` line *is* would be a new class of defect — one hook blocking a
    write the other considers well-formed.

    Fences are matched by marker and width, not a bare toggle: a 4-backtick
    block wrapping a 3-backtick one toggles four times under a boolean and
    leaks the inner content as front matter.
    """
    out = []
    opener = None
    fence_re = re.compile(r"^[ \t]*(`{3,}|~{3,})")
    for ln in src:
        m = fence_re.match(ln)
        if m:
            marker = m.group(1)
            if opener is None:
                opener = marker
                continue
            if marker[0] == opener[0] and len(marker) >= len(opener):
                opener = None
                continue
            # A shorter or different-marker fence is content inside the block.
        if opener is None:
            out.append(ln)
    return out


def field_value(lines, name):
    """First-match-wins scan for `Field:`, tolerant of bold markers.

    Same tolerant form as plan_status_validate.sh — `**Status**: X` and
    `Status: X` are the same declaration, and a hook that accepted one but not
    the other would reject docs the other hook wrote.
    """
    pat = re.compile(r"^[ \t]*(?:\*\*)?" + name + r"(?:\*\*)?:[ \t]*(.*)$")
    for ln in lines:
        m = pat.match(ln)
        if m:
            v = m.group(1).strip()
            # One token, matching the field validator: `READY (pending)` is not READY.
            return v.split()[0] if v.split() else ""
    return None


frag_lines = unfenced(fragment.splitlines(keepends=True))
prior_lines = unfenced(prior_doc.splitlines(keepends=True))

to = field_value(frag_lines, "Status")
declared = field_value(frag_lines, "From")

# THE FRAGMENT RULE. The single most load-bearing branch in this hook: it is what
# keeps the two-Edit `Status:`/`Review:` pair legal (plan_status_validate.sh:164
# permits it by design), and what keeps every prose edit untouched.
#
# PreToolUse sees an edit *fragment*, not the resulting file. A rule that fired on
# a fragment it cannot fully read would produce false rejects, and a false reject
# on a plan-doc write blocks the pipeline for every session in the repo.
#
# Accepted cost, recorded not hidden: a writer that splits `From:` and `Status:`
# across two Edits evades this check. Measured 2026-08-14 — current writers emit
# both in one operation (7 of 7 passing writes on gal-17 produced one edge each),
# so the gap is latent, not active.
if not to or not declared:
    sys.exit(0)

observed = field_value(prior_lines, "Status")

# ORIGIN. No file, or a file with no `Status:`, is an origin write. Declaring a
# `From:` there claims a prior state that never existed.
if not observed:
    sys.stderr.write(
        "\nplan_transition_validate: origin write declares a prior state\n\n"
        f"  {os.path.basename(sys.argv[1] if len(sys.argv) > 1 else 'doc')}\n"
        f"  declares  From: {declared}\n"
        "  but the doc has no prior Status: on disk — there is no state to come from.\n\n"
        "  An origin write (new doc, or one with no Status:) must not carry From:.\n"
    )
    sys.exit(10)

# RESTATEMENT. `From:` PERSISTS in the doc after the write — it is not consumed by
# the transition it records. Verified in the corpus: gal-17-customer-segmentation
# sits permanently at `Status: COMPLETE` / `From: EXECUTED`. So a fragment carrying
# both fields is the RESTING STATE of every settled doc, not an event.
#
# Without this branch, any Write of a settled doc (or any Edit spanning both lines)
# re-presents the already-consumed `From:` beside the already-current `Status:`,
# and the mismatch check below is then GUARANTEED to fire — because the transition
# already happened. Swept across the corpus: 3 of 14 docs false-rejected without
# this branch, 0 with it, and the blocked set grows as more docs acquire `From:`.
#
# Keyed on `to == observed`, NOT on `declared == prior's From:`. Both hold in the
# restatement case, but only this one is safe: a writer that lies about `From:`
# while leaving `Status:` unchanged has declared no edge, so there is nothing to
# catch; keying on the prior's `From:` would wrongly pass a genuine move whose
# prior doc happened to carry a matching value.
#
# MUST precede the mismatch check. The restatement case and the lying-From: case
# are distinguished ONLY by whether `to` moved.
if to == observed:
    sys.exit(0)

# MISMATCH — the lie. Reached only on a genuine move.
if declared != observed:
    sys.stderr.write(
        "\nplan_transition_validate: declared From: contradicts the doc on disk\n\n"
        f"  declares  From: {declared}\n"
        f"  on disk   Status: {observed}\n"
        f"  writing   Status: {to}\n\n"
        f"  The doc was at {observed} before this write, not {declared}.\n"
        f"  If the intended edge is {observed} -> {to}, write From: {observed}.\n"
        "  If it is not, the state this write assumes never happened.\n"
    )
    sys.exit(10)

# Truthful move. Note this hook does NOT re-check the edge against LEGAL_EDGES:
# plan_status_validate.sh:215 already does that, on the resulting file. Duplicating
# the enforcement would mean two hooks blocking the same write for the same reason.
#
# Emit the verdict so the shell can drop a per-write observation token. Printed ONLY
# here — every skip path above exits without it, so a token can never stand for an
# edge this hook did not actually compare.
sys.stdout.write(f"verified\t{declared}\t{to}")
sys.exit(0)
PY

status=0
verdict=""
# `|| status=$?` on the *substitution*, not inside it — a `$(...)` runs in a
# subshell, so an assignment made in there is discarded when it exits. This exact
# bug made plan_status_validate.sh log every rejection as a pass.
verdict=$(printf '%s\0%s' "$prior_doc" "$fragment" | python3 "$_py" "$path") || status=$?

if [ "$status" -eq 10 ]; then
  # Exit 2 is the blocking code for PreToolUse as well as PostToolUse: stderr is fed
  # back so the writer sees the reason. Matches lib.sh's block() convention.
  log_event "plan_transition_validate" 2 "reject: $path"
  exit 2
fi

# Drop a per-write token when — and only when — this run actually compared a
# declared `From:` against the observed state and they matched. `verdict` is
# "verified<TAB>from<TAB>to" on that path and empty on every skip path.
#
# PER-WRITE, NOT PER-SESSION. The obvious implementation is the TMPDIR sentinel
# `log_recorder_session` uses, and it is wrong: that sentinel LATCHES once per
# session (lib.sh:194, `[ -e "$sentinel" ] && return 0`), so it can only answer
# "did the observer run at some point," never "was THIS edge observed." One
# truthful write early in a session would stamp every later record as verified,
# including the split-Edit writes the fragment rule skipped without comparing
# anything — the exact laundering this field exists to prevent, occurring inside
# the mechanism built to prevent it.
#
# Keying on (session, doc, from, to) means a skipped or crashed check produces no
# token for that edge, so a record cannot inherit another write's credibility.
if [ -n "$verdict" ]; then
  IFS=$'\t' read -r v_kind v_from v_to <<<"$verdict"
  if [ "$v_kind" = "verified" ]; then
    write_observation_token "$path" "$v_from" "$v_to"
  fi
fi

log_event "plan_transition_validate" 0 "pass: $path"
exit 0
