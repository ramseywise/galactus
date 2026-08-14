#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/lib.sh"

path=$(claude_path)
[ -z "$path" ] && exit 0
[ -f "$path" ] || exit 0
echo "$path" | grep -q '/\.claude/docs/plans/.*\.md$' || exit 0

# `|| status=$?` keeps set -e from aborting here: the reject path still has to reach
# log_event below before the hook exits non-zero, so the block is recorded either way.
# The Python block is written to a temp file rather than piped through a heredoc
# inside `$(...)`. Command substitution processes backticks as legacy command
# substitution *before* the quoted heredoc protects them, so the fence regexes
# below (`{3,}` and friends) were mangled into a syntax error the moment this
# block started being captured. A file has no such layer.
_py=$(mktemp -t plan_status_validate) || exit 0
trap 'rm -f "$_py"' EXIT
cat > "$_py" <<'PY'
import re
import sys

STATES = {
    "RESEARCH", "RESEARCHED", "PLANNED", "REFINED", "READY",
    "IN_PROGRESS", "EXECUTED", "COMPLETE", "SUPERSEDED",
}

REVIEWS = {"pending", "passed", "failed", "blocked"}

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    raw_lines = fh.readlines()


def unfenced(src):
    """Drop fenced code blocks before any field scan.

    Front matter is never inside a fence. A doc that *documents* the state
    machine — a design doc showing `Status: COMPLETE` in a snippet — would
    otherwise be read as declaring it, because every scan below is
    first-match-wins over raw lines. This was observed: a `Status: RESEARCH`
    design doc was misread as EXECUTED from the corpus examples in its body.

    Fences are matched by *marker and width*, not by a bare toggle. A boolean
    flipped on any ``` desyncs on the standard idiom for documenting fences —
    a 4-backtick block wrapping a 3-backtick one toggles four times and leaks
    the inner content as front matter. Only a fence of the same marker and at
    least the opening width closes the block (CommonMark), and tilde fences
    count, so `~~~` cannot smuggle a `Status:` line past the filter.
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


# Every scan below reads the filtered view, including has_field().
lines = unfenced(raw_lines)

# Tolerant detection: leading whitespace and the bold key form (`**Status**:`)
# both occur in the corpus. Authoring form is bare `Status:` (spec, ## Mapping).
status_re = re.compile(r"^[ \t]*(?:\*\*)?Status(?:\*\*)?:[ \t]*(.*)$")

value = None
for line in lines:
    m = status_re.match(line)
    if m:
        value = m.group(1).strip()
        break


def has_field(name):
    return any(re.match(rf"^[ \t]*(?:\*\*)?{name}(?:\*\*)?:", ln) for ln in lines)


def field_value(name):
    pat = re.compile(rf"^[ \t]*(?:\*\*)?{name}(?:\*\*)?:[ \t]*(.*)$")
    for ln in lines:
        m = pat.match(ln)
        if m:
            return m.group(1).strip()
    return None


issues = []
token = ""  # stays empty when the doc has no Status: line; the state-specific
# checks below then simply do not fire.

# `Review:` — validate the value whenever the line is present; never require it.
# Absence means no review outcome is being claimed, which is honest; blocking on
# absence would make every doc predating this rule instantly unwritable.
#
# The four values are the outcomes /workflow-review can reach, and they are
# distinct on purpose: `pending` means *no review concluded*, so a concluded
# review never writes it. Collapsing "rejected" and "could not decide" into
# `pending` is the defect this enum exists to remove.
review_value = field_value("Review")
if review_value is not None:
    r = review_value.split()[0] if review_value.split() else ""
    if r not in REVIEWS:
        issues.append(
            f"  Review: '{r}' is not a valid outcome; expected one of: {', '.join(sorted(REVIEWS))}"
        )
    elif review_value[len(r):].strip():
        issues.append("  Review: must be exactly one token (pending | passed | failed | blocked)")

# `Track:` — same tolerant form as Status, and the same one-token rule.
#
# Validate the value; never require the line. Every plan doc that predates the
# router lacks it, and blocking on absence would make all of them instantly
# unwritable. Absence is valid; later phases backfill.
track_re = re.compile(r"^[ \t]*(?:\*\*)?Track(?:\*\*)?:[ \t]*(.*)$")
TRACKS = {"ml", "agent"}

track_value = None
for line in lines:
    m = track_re.match(line)
    if m:
        track_value = m.group(1).strip()
        break

if track_value is not None:
    t = track_value.split()[0] if track_value.split() else ""
    if t not in TRACKS:
        issues.append(f"  '{t}' is not a valid track; expected one of: {', '.join(sorted(TRACKS))}")
    elif track_value[len(t):].strip():
        issues.append("  Track: must be exactly one token (ml | agent)")

if value is not None:
    token = value.split()[0] if value.split() else ""
    suffix = value[len(token):].strip()

    if token not in STATES:
        issues.append(f"  '{token}' is not a canonical state; expected one of: {', '.join(sorted(STATES))}")
    if suffix:
        issues.append(
            f"  Status: carries a suffix ({suffix!r}) — it must be exactly one token. "
            "Move detail to Released:/Outstanding:/Review:/Evidence:/Superseded-by:/Completed:"
        )

if token == "EXECUTED" and not has_field("Review"):
    issues.append("  EXECUTED requires a 'Review:' line (pending | passed | failed | blocked)")

# COMPLETE is the one state that asserts an outcome rather than a position, so
# its companions are checked by value. Requiring only presence would let a doc
# land at COMPLETE carrying `Review: pending` — the state reads as "reviewed and
# accepted" while the hook guaranteed something strictly weaker, and the stuck-
# at-pending docs this rule exists to unstick are exactly that shape. Writing
# Status: and Review: is two Edits, so the intermediate file state is reachable.
if token == "COMPLETE":
    review = field_value("Review")
    if review is None:
        issues.append("  COMPLETE requires a 'Review:' line — and it must read 'passed'")
    elif (review.split()[0] if review.split() else "") != "passed":
        issues.append(
            f"  COMPLETE requires 'Review: passed'; found {review!r}. "
            "Resolve the review before recording the work as done"
        )
    if not has_field("Completed"):
        issues.append("  COMPLETE requires a 'Completed:' date")

if token == "SUPERSEDED" and not has_field("Superseded-by"):
    issues.append("  SUPERSEDED requires a 'Superseded-by:' line naming the replacing doc")

# `From:` — the declared prior state, validated against the legal-edge table.
#
# Same rule as Track:, and for the same reason: validate the value, never require
# the line. Every doc predating this lacks it; blocking on absence makes all of
# them instantly unwritable.
#
# LIMITATION: this is a self-report. PostToolUse reads the file *after* the write,
# so the hook cannot observe the prior value — a writer that lies about From:
# passes whenever the claimed edge is legal. This catches accidental skips, not
# deliberate ones. Hardening needs a PreToolUse hook and is deferred.
LEGAL_EDGES = {
    ("RESEARCH", "RESEARCHED"), ("RESEARCHED", "PLANNED"),
    ("RESEARCH", "PLANNED"), ("PLANNED", "REFINED"),
    ("PLANNED", "READY"), ("REFINED", "READY"),
    ("READY", "IN_PROGRESS"), ("IN_PROGRESS", "EXECUTED"),
    ("EXECUTED", "PLANNED"), ("EXECUTED", "COMPLETE"),
}

from_re = re.compile(r"^[ \t]*(?:\*\*)?From(?:\*\*)?:[ \t]*(.*)$")
from_value = None
for line in lines:
    m = from_re.match(line)
    if m:
        from_value = m.group(1).strip()
        break

if from_value is not None and token:
    prior = from_value.split()[0] if from_value.split() else ""
    if prior not in STATES:
        issues.append(
            f"  From: '{prior}' is not a canonical state; expected one of: {', '.join(sorted(STATES))}"
        )
    elif from_value[len(prior):].strip():
        issues.append("  From: must be exactly one token")
    # SUPERSEDED is reachable from any state — escalation has no fixed origin.
    elif token != "SUPERSEDED" and (prior, token) not in LEGAL_EDGES:
        issues.append(
            f"  '{prior}' → '{token}' is not a legal transition. Legal edges from "
            f"'{prior}': {', '.join(sorted(b for a, b in LEGAL_EDGES if a == prior)) or '(none)'}"
        )

# `Epistemic:` — the second axis: what is known about the work's soundness, as
# opposed to where the work is. READY is not the same as correct.
#
# Coherence, not presence. Requiring the field whenever Status: READY would
# rebuild the `Review: pending` failure — a mandatory field with an escape hatch
# becomes a field everyone sets to the escape hatch. Instead the hook rejects
# illegal *combinations*, and the writer (/proto-refine) guarantees freshness.
# UNTESTED + READY stays legal and visible: that is the "nothing checked it"
# state, and making it illegal is what creates override pressure.
EPISTEMIC = {"UNTESTED", "NO_CONFLICT", "CONFLICTED", "BLOCKED"}

epistemic_re = re.compile(r"^[ \t]*(?:\*\*)?Epistemic(?:\*\*)?:[ \t]*(.*)$")
epistemic_value = None
for line in lines:
    m = epistemic_re.match(line)
    if m:
        epistemic_value = m.group(1).strip()
        break

if epistemic_value is not None:
    e = epistemic_value.split()[0] if epistemic_value.split() else ""
    if e not in EPISTEMIC:
        issues.append(
            f"  '{e}' is not a valid epistemic state; expected one of: {', '.join(sorted(EPISTEMIC))}"
        )
    elif epistemic_value[len(e):].strip():
        issues.append("  Epistemic: must be exactly one token")
    elif token == "READY" and e in {"CONFLICTED", "BLOCKED"}:
        issues.append(
            f"  READY is not legal while Epistemic: is {e} — resolve the findings "
            "or record why they do not block, then advance"
        )

if issues:
    print(f"Plan-doc front matter is not conforming in {path}:", file=sys.stderr)
    for issue in issues:
        print(issue, file=sys.stderr)
    print(
        "  Write is blocked until Status: carries exactly one canonical state "
        "and Review:, if present, is exactly one of: pending | passed | failed | blocked.",
        file=sys.stderr,
    )
    sys.exit(10)

# The transition record (galactus step 4). The hook is the only component that sees
# every accepted edge, and until now it discarded that: the log said a write passed,
# never *which transition* passed. D10 — the loop-back count — was therefore
# unmeasurable even after `From:` gave every edge a name.
#
# Emitted on stdout for the shell to append. Only edges are recorded: a write that
# declares no `From:` is not a transition (most writes to a plan doc are prose
# edits), and recording those would bury the traversals in noise.
#
# Nothing is recorded on the reject path — a blocked write never landed, so the
# transition did not happen. Counting attempts as traversals would inflate exactly
# the number this exists to measure.
if from_value is not None and token:
    prior = from_value.split()[0] if from_value.split() else ""
    print(f"{prior}\t{token}\t{track_value or ''}\t{epistemic_value or ''}")
PY

status=0
# `|| status=$?` on the *substitution*, not inside it: a `$(...)` runs in a
# subshell, so an assignment made in there is discarded when it exits. An
# earlier form of this line always reported 0, which would have logged every
# rejection as a pass.
transition=$(python3 "$_py" "$path") || status=$?

if [ "$status" -eq 10 ]; then
  # Exit 2 is the PostToolUse blocking code: stderr is fed back so the writer sees the
  # reason and can fix it. Warn mode (#74) surfaced nothing in the tool result, which
  # made a silently-disagreeing hook indistinguishable from a passing one — see #79.
  log_event "plan_status_validate" 2 "reject: $path"
  exit 2
fi
log_event "plan_status_validate" 0 "pass: $path"

# Mark the recorder alive before recording any edge. Unconditional on this path:
# reaching here means a plan doc validated, which is proof a recorder ran whether
# or not the write moved a state. A marker emitted only alongside a transition
# would be absent in precisely the case it exists to disambiguate — see
# `log_recorder_session` in lib.sh (galactus#20 fix direction 2).
log_recorder_session "plan_status_validate"

# Record the traversal, not just the pass. `log_transition` is a no-op when the
# write declared no `From:` — see the emit site in the Python block above.
if [ -n "$transition" ]; then
  IFS=$'\t' read -r t_from t_to t_track t_epistemic <<<"$transition"
  log_transition "$path" "$t_from" "$t_to" "$t_track" "$t_epistemic"
fi
exit 0
