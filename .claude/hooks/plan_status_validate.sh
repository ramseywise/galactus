#!/usr/bin/env bash

set -euo pipefail

source "$(dirname "$0")/lib.sh"

path=$(claude_path)
[ -z "$path" ] && exit 0
[ -f "$path" ] || exit 0
echo "$path" | grep -q '/\.claude/docs/plans/.*\.md$' || exit 0

# `|| status=$?` keeps set -e from aborting here: the reject path still has to reach
# log_event below before the hook exits non-zero, so the block is recorded either way.
status=0
python3 - "$path" <<'PY' || status=$?
import re
import sys

STATES = {
    "RESEARCH", "RESEARCHED", "PLANNED", "REFINED", "READY",
    "IN_PROGRESS", "EXECUTED", "COMPLETE", "SUPERSEDED",
}

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    lines = fh.readlines()

# Tolerant detection: leading whitespace and the bold key form (`**Status**:`)
# both occur in the corpus. Authoring form is bare `Status:` (spec, ## Mapping).
status_re = re.compile(r"^[ \t]*(?:\*\*)?Status(?:\*\*)?:[ \t]*(.*)$")

value = None
for line in lines:
    m = status_re.match(line)
    if m:
        value = m.group(1).strip()
        break

if value is None:
    sys.exit(0)

issues = []
token = value.split()[0] if value.split() else ""
suffix = value[len(token):].strip()

if token not in STATES:
    issues.append(f"  '{token}' is not a canonical state; expected one of: {', '.join(sorted(STATES))}")
if suffix:
    issues.append(
        f"  Status: carries a suffix ({suffix!r}) — it must be exactly one token. "
        "Move detail to Released:/Outstanding:/Review:/Evidence:/Superseded-by:/Completed:"
    )


def has_field(name):
    return any(re.match(rf"^[ \t]*(?:\*\*)?{name}(?:\*\*)?:", ln) for ln in lines)


if token == "EXECUTED" and not has_field("Review"):
    issues.append("  EXECUTED requires a 'Review:' line (pending | passed)")
if token == "SUPERSEDED" and not has_field("Superseded-by"):
    issues.append("  SUPERSEDED requires a 'Superseded-by:' line naming the replacing doc")

if issues:
    print(f"Plan-doc Status is not conforming in {path}:", file=sys.stderr)
    for issue in issues:
        print(issue, file=sys.stderr)
    print("  Write is blocked until Status: carries exactly one canonical state.", file=sys.stderr)
    sys.exit(10)
PY

if [ "$status" -eq 10 ]; then
  # Exit 2 is the PostToolUse blocking code: stderr is fed back so the writer sees the
  # reason and can fix it. Warn mode (#74) surfaced nothing in the tool result, which
  # made a silently-disagreeing hook indistinguishable from a passing one — see #79.
  log_event "plan_status_validate" 2 "reject: $path"
  exit 2
fi
log_event "plan_status_validate" 0 "pass: $path"
exit 0
