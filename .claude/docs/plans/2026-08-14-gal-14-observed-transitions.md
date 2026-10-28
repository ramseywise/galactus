# Harden `From:` with a PreToolUse hook — observed transitions, not self-reported

> A second hook that reads the plan doc *before* the write, so the declared `From:` is
> checked against the state that was actually there.

Status: PLANNED
Outstanding: Steps 1-3, 5-7 implemented and green; Step 4 registered but its live
  probe is deferred (hook not loaded in the executing session — needs a restart).
  Status stays PLANNED: the doc never cleared /proto-refine, so there is no legal
  edge to EXECUTED. Advancing it would require the REFINED -> READY -> IN_PROGRESS
  walk the gate owns.
Track: agent
Issue: #14
Branch: GAL-14-harden-from-pretooluse
Epistemic: BLOCKED
Epistemic-by: fog-advisor (CROSS, /proto-refine Stage 3)
Epistemic-at: 2026-08-14
Epistemic-findings: 6

## Plan
Date: 2026-08-14
Based on: direct codebase inspection (`.claude/hooks/`, `review/transitions.py`), plus
`2026-08-14-orchestrator-design.md` Open Question 4 and its `## Execution record`.

### Goal

Make `plan-transitions.jsonl` admissible evidence about D10 — so that "EXECUTED → PLANNED
traversed 0 times" means the edge was never traversed, not that no writer declared it.

### Open Questions

Resolved 2026-08-14 in the planning session, before any drafting:

1. **Fragment rule — what does PreToolUse validate?** → **Fragment-scoped, silent skip,
   plus a restatement branch (revised 2026-08-14, FA-001).**
   Validate only when the incoming fragment carries *both* `From:` and `Status:` — **and
   only when the pair describes a *move*.** A fragment whose `Status:` already equals the
   on-disk `Status:` is restating settled front matter, not declaring a transition, and
   passes. Any other write passes untouched. See "The restatement branch" below; the
   original two-way `declared != observed` comparison blocked every settled doc in the
   corpus.
   *Why:* PreToolUse sees `tool_input.new_string` / `.content` — an edit fragment, not the
   resulting file (verified: an `Edit` payload carries `file_path`, `old_string`,
   `new_string`, and nothing else). A rule that fires on a fragment it cannot fully read
   produces false rejects, and a false reject on a plan-doc write blocks the pipeline.
   *Accepted cost:* a writer that splits `From:` and `Status:` across two Edits evades the
   check. Recorded as a limitation in Step 5, not silently.

2. **Where does the check live?** → **A new hook file, PreToolUse only.**
   `plan_transition_validate.sh`. `plan_status_validate.sh` keeps every field-presence
   check it has today; only its `LIMITATION` comment changes.
   *Why:* the two hooks answer different questions and need different inputs. PreToolUse
   owns transitions because only it can see the prior state; PostToolUse owns field
   presence because only it can see the resulting file. Dual-registering one file and
   branching on `hook_event_name` would put two exit-code contracts in one script.

3. **The `plan_status_validate.sh:164` two-Edit tension.** → **Dissolved, not resolved.**
   The existing hook deliberately permits `Status:` and `Review:` to arrive as two separate
   Edits, so the intermediate file state is legal by design. Under the fragment rule the
   new hook never sees that pair as a transition unless the *same* fragment carries
   `From:` + `Status:` — so the `Review:`-only Edit is skipped, and nothing about
   `plan_status_validate.sh:164` changes. **This is the design tension the issue named;
   the fragment rule is what removes it.** No edit to that block is in scope.

4. **Doc creation / origin writes.** → **No file on disk, or no `Status:` on disk, is an
   origin.** An origin write with no `From:` passes. An origin write that *declares* a
   `From:` is rejected: it claims a prior state that never existed, which is exactly the
   lie this build exists to catch. `/proto-research` creating a doc at `RESEARCHED` writes
   no `From:` and is unaffected.

5. **Table drift between the two hooks.** → **Duplicate `LEGAL_EDGES`, with a test that
   asserts the copies are identical.** Not a shared sourced file: both hooks embed their
   Python as a heredoc written to a tempfile, so sharing means adding an import path and a
   third file to a directory the agent cannot edit without operator approval. A mechanical
   drift test buys the same guarantee for less structural cost.

6. **Do the pre-existing ledger records inherit the new credibility?** → **No — and that
   must be visible.** This is the one requirement the issue's "Done when" does not state
   but the *goal* does. Once the hook observes transitions, the ledger mixes verified and
   self-reported records with nothing distinguishing them, and a D10 count over the whole
   file would silently launder the old ones. Step 6 adds an `observed` field and teaches
   the reader to report the populations separately.
   *Revised 2026-08-14:* `observed` is **three-valued**, not boolean, and its signal is
   **per-write**, not per-session. A session-latched sentinel would have re-created the
   laundering this question exists to prevent, and a boolean would have collapsed "the
   observer could not run" into "the observer found nothing" — the same mistake
   `transitions.py:114-167` already corrects for `attested`. See Step 6.

7. **Does a fragment carrying both fields always mean a transition?** → **No.** `From:`
   persists after the write, so the pair is the resting state of every settled doc.
   Resolved 2026-08-14 by the restatement branch (Open Question 1, Step 1 logic step 6),
   after a corpus sweep showed the original logic false-rejecting 3 of 14 docs.

8. **Is the fragment-scoped coverage claim actually true of current writers?** → **Yes,
   measured.** 7 of 7 passing writes on `gal-17` produced exactly one ledger edge each,
   timestamps aligned one-to-one. Writers emit `Status:` and `From:` in a single
   operation, so the hook sees the transition and the build is not inert. Previously
   asserted from reading the skills; now evidence. See Approach.

### Approach

Add a second, narrower hook rather than extending the existing one. `plan_transition_validate.sh`
registers on `PreToolUse` / `Write|Edit`, reads the *current* `Status:` from disk (the file
is still pre-edit at that moment), extracts `From:` and `Status:` from the incoming
fragment, and blocks when the declared prior contradicts the observed one. It reuses
`plan_status_validate.sh`'s proven parsing shape — `unfenced()` and the tolerant
`(?:\*\*)?Field(?:\*\*)?:` regexes — because a transition validator that disagrees with the
field validator about what a `Status:` line *is* would be a new class of defect.

The tradeoff accepted: coverage is fragment-scoped (Open Question 1). This closes the
lying-`From:` hole for every write that declares an edge in one operation.

**That coverage claim is now measured, not asserted** (2026-08-14; it was previously
asserted, which is what this revision fixes). Evidence, from
`.claude/logs/hook-log.jsonl` (73 real plan-doc writes) cross-referenced against
`.claude/logs/plan-transitions.jsonl`:

| Doc | Plan-doc writes | Ledger edges |
|---|---|---|
| `2026-08-14-gal-17-customer-segmentation.md` | 8 (7 pass, 1 reject) | 7 |

Every one of the 7 passing writes produced exactly one transition, timestamps aligning
one-to-one (`16:57:15`, `17:02:31`, `17:19:40`, `17:19:59`, `17:20:34`, `17:31:24`,
`17:34:41`), and each edge's `from:` chains exactly to the previous edge's `to:` across
the full `RESEARCH → RESEARCHED → PLANNED → REFINED → READY → IN_PROGRESS → EXECUTED →
COMPLETE` walk. The one `exit_code: 2` write (`17:34:20`) produced no edge, and the
corrected retry 21 seconds later did.

**Conclusion**: writers emit `Status:` and `From:` in a *single* operation. If they split
across two Edits, the second Edit would carry `From:` without `Status:`, the fragment rule
would skip it, and the ledger would show fewer edges than passing writes — it does not.
The hook will therefore see the transition, and Steps 1-7 are not inert. This was the
open question that determined whether the build was worth doing at all.

### Out of Scope

- Changing the `From:` field format or the legal-edge table — both work (issue #14).
- Requiring `From:` presence on any write — explicitly out of scope per #14, and it would
  break the 11-of-12 corpus docs that carry no `From:`.
- Simulating the edit (`old_string` → `new_string`) to derive the resulting file. Rejected
  in Open Question 1: it means reimplementing `Edit` semantics (`replace_all`, uniqueness)
  and diverging on `Write` vs `Edit`.
- Any change to `plan_status_validate.sh`'s field-presence logic, including the
  `Status:`/`Review:` two-Edit allowance at `:164`.
- The galactus#20 telemetry work (`lib.sh`, `review/transitions.py`), which is **committed
  at `0a4ce35`** on this branch — not uncommitted, and the working tree is clean
  (corrected 2026-08-14; the earlier draft described a working-tree state that no longer
  exists). **The plan builds on the committed tree**, it does not revise it — except
  Step 6, which extends `_parse` additively. Steps 2 and 6 both target `lib.sh` as
  committed; no rebase is needed and none should be attempted mid-build.
- Backfilling `observed` onto existing ledger records. Absence means "written before the
  observer existed", which is the honest reading and needs no migration.

### Steps

**Operator gate.** `.claude/hooks/` is permission-denied to the agent, and Step 4 edits
`.claude/settings.json`. Steps 1, 2, 3, 5 and 7 write files under `.claude/hooks/` and will
each need approval; Step 4 needs it for settings. Nothing here can be executed unattended.

**Ordering constraint.** Step 4 (registration) must not land before Steps 1–3 are green. A
hook registered before its tests pass is live on every plan-doc write in the repo, and a
false reject there blocks the pipeline for every session, not just this one.

**Step 6 last, deliberately.** It is the only step that writes to a permanent, unrotated,
un-backfillable file. Running Steps 1–5 in front of real sessions first means a defect
found in that window costs nothing — there is no `observed` field yet to be wrong. Do not
promote Step 6 ahead of Step 5 to "get the ledger work done early."

---

#### Step 1: The transition validator hook

**Files**: `.claude/hooks/plan_transition_validate.sh` (new, ~150 lines)

**What**: A `PreToolUse` hook that reads the pre-edit `Status:` from disk and compares it
against the `From:` declared in the incoming fragment.

Guard clauses first, mirroring `plan_status_validate.sh:7-10` — but note the one deliberate
divergence: that hook exits 0 when the file does not exist (`[ -f "$path" ] || exit 0`);
this one must *not*, because a missing file is the origin case and an origin write carrying
`From:` has to be rejected.

**Snippet** (shape, not final text):

```bash
path=$(claude_path)
[ -z "$path" ] && exit 0
echo "$path" | grep -q '/\.claude/docs/plans/.*\.md$' || exit 0

# The fragment being written. Write carries .content, Edit carries .new_string;
# claude_content() already coalesces both.
fragment=$(claude_content)
[ -z "$fragment" ] && exit 0

# The file as it stands BEFORE the write. This is the whole point of PreToolUse:
# `prior` is observed, not declared. A missing file is the origin case, handled
# in Python as an empty prior rather than an early exit.
prior_doc=""
[ -f "$path" ] && prior_doc=$(cat "$path")
```

The Python block is written to a tempfile via the same `mktemp` + `trap` pattern as
`plan_status_validate.sh:19-21`, and for the same recorded reason: command substitution
mangles backticks in the fence regexes before a quoted heredoc can protect them. It takes
the prior doc and the fragment on **stdin separated by a NUL-delimited pair**, not as argv
— a fragment can be arbitrarily long and contain anything.

Logic, in order:

1. `unfenced()` both the prior doc and the fragment — copied verbatim from
   `plan_status_validate.sh:37-69`. A fragment that adds a fenced example containing
   `Status:` must not be read as declaring one.
2. Extract `to` = `Status:` from the fragment, `declared` = `From:` from the fragment.
3. **If either is absent → exit 0.** The fragment rule (Open Question 1). This is the
   single most load-bearing line in the hook: it is what keeps the two-Edit
   `Status:`/`Review:` pair legal and what keeps prose edits untouched.
4. Extract `observed` = `Status:` from the prior doc (empty if the file did not exist),
   and `observed_from` = `From:` from the prior doc.
5. **Origin case** — `observed` empty: block if `declared` is non-empty
   ("declares From: X but the doc has no prior Status:"), else pass.
6. **Restatement branch (FA-001) — `to == observed`: pass, unconditionally.**
   Nothing is moving. The fragment names the state the doc is already in, so no edge is
   being declared and there is nothing to verify. See "The restatement branch" below.
7. **Mismatch case** — `declared != observed`: block, naming both. Reached only when
   `to != observed`, i.e. only on a genuine move.
8. Otherwise pass. Note the hook does **not** re-check the edge against `LEGAL_EDGES` on
   the pass path — `plan_status_validate.sh:215` already does, on the resulting file.
   `LEGAL_EDGES` is needed here only for the error message in Step 3.

**The restatement branch.** `From:` **persists** in the doc after the write — it is not
consumed by the transition it records. Verified in the corpus:
`2026-08-14-gal-17-customer-segmentation.md:4-5` sits permanently at `Status: COMPLETE` /
`From: EXECUTED`, and `2026-08-14-orchestrator-design.md:6-7` at `Status: EXECUTED` /
`From: IN_PROGRESS`. So a fragment carrying both fields is **the resting state of every
settled doc**, not the signature of an event.

Without step 6, any `Write` of a settled doc — or any `Edit` whose fragment spans both
lines — re-presents the already-consumed `From:` next to the already-current `Status:`,
and the step-7 comparison is then *guaranteed* to mismatch, because the transition already
happened. Simulated against the real corpus doc before this revision:

```
fragment Status: (to)      = COMPLETE
fragment From:   (declared)= EXECUTED
disk     Status: (observed)= COMPLETE
RESULT: exit 2  <-- BLOCKED: declares From: EXECUTED but doc is at COMPLETE
```

Nothing was transitioning. That is the plan's own highest-severity risk ("a false reject
blocks every plan-doc write in the repo") arriving *through* the fragment rule that was
supposed to prevent it. Ordering matters: step 6 must precede step 7, because the
restatement case and the lying-`From:` case are distinguished **only** by whether `to`
moved.

Swept across all 14 docs in `.claude/docs/plans/`, feeding each doc's own front matter
back as its fragment:

| Logic | False rejects |
|---|---|
| With the restatement branch | **0 of 14** |
| Without it (original spec) | **3 of 14** — `gal-17-customer-segmentation`, `orchestrator-design`, `track-routing` |

The three blocked docs are exactly the three that carry a persistent `From:`. That set
grows monotonically: `From:` is only ~2 days old, 11 of 14 docs predate it, and every
future transition adds one. The original logic would have failed *more* over time, and
the corpus sweep is now Test Plan step 7 so a regression cannot land quietly.

Note the branch keys on `to == observed`, not on `declared == observed_from`. Both hold
in the restatement case, but only the former is safe: a writer that lies about `From:`
while *also* leaving `Status:` unchanged has declared no edge, so there is nothing to
catch; whereas keying on `observed_from` would wrongly pass a genuine move whose prior
doc happened to carry a matching `From:`. `observed_from` is extracted for the error
message only.

Exit code is **2** on block (PreToolUse blocking code, same as PostToolUse) with the reason
on stderr, and `log_event "plan_transition_validate" 2 "reject: $path"` before exiting —
matching `plan_status_validate.sh:289-295`. On pass: `log_event ... 0`.

**Test**: `bash .claude/hooks/tests/test_plan_transition_validate.sh` (written in Step 3)

**Done when**: the hook exists, is `chmod +x`, and `bash -n` parses it clean. Two manual
probes, both required:

- a doc on disk at `Status: PLANNED`, a fragment declaring `Status: EXECUTED` +
  `From: IN_PROGRESS` → exits 2 (the lie);
- the real `gal-17` doc, its own front matter as the fragment → exits 0 (the restatement).

The second probe is not optional: a hook that passes the first and fails the second blocks
every settled doc in the repo.

---

#### Step 2: `claude_content()` covers the Write path

**Files**: `.claude/hooks/lib.sh:28` (read-only verification; edit only if the probe fails)

**What**: Confirm `claude_content()` returns the fragment for both tool shapes. It already
coalesces `.tool_input.new_string // .tool_input.content` — verified by reading, but the
hook's correctness rests on it, so it gets an explicit probe rather than an assumption.

**Snippet**:

```bash
printf '{"tool_input":{"file_path":"/p.md","new_string":"Status: READY\nFrom: REFINED\n"}}' \
  | ... # Edit shape  -> must yield the fragment
printf '{"tool_input":{"file_path":"/p.md","content":"Status: READY\nFrom: REFINED\n"}}' \
  | ... # Write shape -> must yield the same
```

**Test**: covered by the Step 3 suite (both payload shapes are asserted there).

**Done when**: both shapes yield the fragment. **Already verified 2026-08-14** — probed
directly against `lib.sh` as committed:

```
$ printf '{"tool_input":{"file_path":"/p.md","new_string":"Status: READY\nFrom: REFINED\n"}}' | claude_content
Status: READY
From: REFINED
$ printf '{"tool_input":{"file_path":"/p.md","content":"Status: READY\nFrom: REFINED\n"}}'    | claude_content
Status: READY
From: REFINED
```

Both shapes yield the identical fragment, so this step is a confirmation and no `lib.sh`
edit is needed. If a future change makes `Write` diverge, that edit lands on the committed
tree (galactus#20 is committed at `0a4ce35`) — not `origin/main`, and no rebase mid-build.

---

#### Step 3: The test suite

**Files**: `.claude/hooks/tests/test_plan_transition_validate.sh` (new)

**What**: End-to-end tests against the real hook with real JSON on stdin and real files in
a temp dir — the house pattern from `test_plan_status_validate.sh:1-56`, including the
`GALACTUS_TRANSITION_LOG` redirect (this hook does not write the ledger, but it sources
`lib.sh`, which resolves ledger paths at source time).

The harness needs one addition over the existing `run()`: it must write the **prior** doc
to disk first, then feed a **fragment** — two inputs, where the old harness had one.

**Snippet**:

```bash
# run_pre <file-path> <prior-doc-content> <fragment>
run_pre() {
  local p="$1" prior="$2" frag="$3"
  if [ -n "$prior" ]; then printf '%b' "$prior" > "$p"; else rm -f "$p"; fi
  printf '{"tool_input":{"file_path":"%s","new_string":%s}}' "$p" "$(jq -Rs . <<<"$(printf '%b' "$frag")")" \
    | bash "$HOOK" 2>"$err"
}
```

Cases, each an assertion the goal depends on:

| # | Prior on disk | Fragment | Expect |
|---|---|---|---|
| 1 | `Status: IN_PROGRESS` | `Status: EXECUTED` + `From: IN_PROGRESS` | exit 0 — truthful |
| 2 | `Status: PLANNED` | `Status: EXECUTED` + `From: IN_PROGRESS` | **exit 2** — the lie |
| 3 | `Status: PLANNED` | `Status: REFINED`, no `From:` | exit 0 — fragment rule |
| 4 | `Status: PLANNED` | `Review: passed`, no `Status:` | exit 0 — the two-Edit pair |
| 5 | *(no file)* | `Status: RESEARCHED`, no `From:` | exit 0 — origin |
| 6 | *(no file)* | `Status: PLANNED` + `From: RESEARCHED` | **exit 2** — origin lie |
| 7 | `Status: PLANNED` | fenced block containing `From: EXECUTED` | exit 0 — unfenced |
| 8 | prior `Status:` inside a fence, real one after | truthful `From:` vs the real one | exit 0 |
| 9 | `**Status**: PLANNED` (bold) | `From: PLANNED` + `Status: REFINED` | exit 0 — tolerant form |
| 10 | `Status: PLANNED` | `Write` payload (`.content`) shape | exit 0 — Step 2 |
| 11 | non-plan path (`src/x.md`) | anything | exit 0 — path guard |
| 12 | `Status: EXECUTED` | `Status: PLANNED` + `From: EXECUTED` | exit 0 — D10 loop-back |
| 13 | `Status: COMPLETE` + `From: EXECUTED` | **the doc's own front matter verbatim** (`Edit`) | exit 0 — restatement |
| 14 | `Status: COMPLETE` + `From: EXECUTED` | same, as a `Write` `.content` payload | exit 0 — restatement, both shapes |
| 15 | **the real `gal-17` doc**, unmodified | its own first 10 lines | exit 0 — corpus, not a fixture |
| 16 | `Status: EXECUTED` + `From: IN_PROGRESS` | **the real `orchestrator-design` doc's** own front matter | exit 0 — second corpus doc |
| 17 | `Status: PLANNED` + `From: RESEARCHED` | `Status: PLANNED` + `From: EXECUTED` (lying, but no move) | exit 0 — restatement precedes mismatch |

Case 2 is the issue's "Done when". Cases 3, 4 and 12 are the regression guards: 4 is the
`plan_status_validate.sh:164` tension, and 12 is the edge the whole measurement exists for
— a hook that rejected the loop-back would destroy D10 rather than harden it.

**Cases 13-17 are the FA-001 guards, and 15-16 are deliberately not fixtures.** They feed
*real corpus docs* back to the hook as their own fragment, because the defect they catch
was invisible to a suite built entirely from hand-written transition events: every one of
cases 1-12 constructs a fragment as a *move*, so a hook that blocks every settled doc in
the repo passes all twelve. A fixture that drifts from the corpus reintroduces exactly
that blind spot, so these two read the checked-in files.

Case 17 pins the branch **ordering** — it is the one case that fails if steps 6 and 7 are
swapped. The fragment declares a false `From:`, but `Status:` does not move, so no edge is
being asserted and there is nothing to catch. Reversed ordering blocks it, and that block
would fire on any settled doc whose `From:` is being corrected by hand.

**Test**: `bash .claude/hooks/tests/test_plan_transition_validate.sh`

**Done when**: all 17 cases pass; the suite fails if the hook is stubbed to `exit 0`
(cases 2 and 6 must break) — the same "cannot go green on a guard that never fires"
property asserted at `test_plan_status_validate.sh:8-10`; **and** the suite fails if the
restatement branch is removed (cases 13-17 must break), which is the mirror property: it
cannot go green on a guard that fires too often.

---

#### Step 4: Register the hook (operator approval)

**Files**: `.claude/settings.json` — the `PreToolUse` / `Write|Edit` block that currently
holds only `secrets_scan.sh`

**Snippet**:

```json
{
  "matcher": "Write|Edit",
  "hooks": [
    { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/secrets_scan.sh" },
    { "type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/plan_transition_validate.sh" }
  ]
}
```

Ordering after `secrets_scan.sh` is deliberate: a fragment containing a secret should be
blocked for that reason first, and the transition hook should never be the thing that
reports on a payload the secrets guard would have rejected.

**Test**: `jq -e '.hooks.PreToolUse[] | select(.matcher=="Write|Edit") | .hooks | length == 2' .claude/settings.json`,
then a live probe: edit a scratch plan doc with a lying `From:` and confirm the block
surfaces in the tool result.

**Done when**: the live probe blocks. This is the step that proves the wiring, not the
logic — Step 3 proved the logic. Both are needed: galactus#20 was precisely a hook whose
logic was right and whose registration was not.

---

#### Step 5: Replace the accepted-limitation comments

**Files**: `.claude/hooks/plan_status_validate.sh:181-188` (the `LIMITATION` block —
line numbers corrected 2026-08-14; `LEGAL_EDGES` follows at `:190`, and the edge check
at `:215`), `.claude/hooks/tests/test_plan_status_validate.sh:214-216` (the mirroring
comment)

**What**: Both currently say the self-report is unverifiable and hardening is deferred.
That becomes false the moment Step 4 lands. Issue #14's "Done when" names this explicitly.

**Snippet** (before → after, hook):

```
# LIMITATION: this is a self-report. PostToolUse reads the file *after* the write,
# so the hook cannot observe the prior value — a writer that lies about From:
# passes whenever the claimed edge is legal. This catches accidental skips, not
# deliberate ones. Hardening needs a PreToolUse hook and is deferred.
```
→
```
# `From:` is verified against the OBSERVED prior state by `plan_transition_validate.sh`
# (PreToolUse), which reads the doc before the write. This hook still cannot see the
# prior value and does not try to — it owns the legal-edge table and field presence;
# the PreToolUse hook owns "was that prior state actually there".
#
# Residual gap, deliberate: the observer is fragment-scoped. It validates only a write
# whose fragment carries BOTH From: and Status: AND whose Status: differs from the one
# on disk — a restatement of settled front matter is not a transition and is not
# checked. So a writer that splits the pair across two Edits is still unchecked.
# Narrowing that means requiring From: presence, which #14 places out of scope — it
# belongs at the writer. Measured 2026-08-14: current writers emit both fields in one
# operation (7 of 7 passing writes on gal-17 produced one edge each), so the gap is
# latent, not active.
#
# What `observed: verified` certifies, exactly: the From: named in the write matched
# the Status: on disk at that moment. It does NOT certify that the phase actually ran.
# A writer told "declares From: READY but the doc is at PLANNED" can retry with
# From: PLANNED and pass — correctly labelled, having skipped whatever the operator
# thought happened. The edge table (:190) is what catches the illegal ones; this field
# is about file state, not phase execution.
```

The test-file comment gets the matching correction, and its `From:` cases keep their
existing assertions — they test the *edge table*, which is still this hook's job.

**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh` — must still report
102 passed, 0 failed (the recorded baseline; comment-only changes must not move it).

**Done when**: no comment in either file claims the limitation still stands, and the
residual fragment-scoped gap is written down where the next reader will find it.

---

#### Step 6: Mark observed edges in the ledger

**Files**: `.claude/hooks/lib.sh` (`log_transition`), `review/transitions.py` (`_parse`
and its caller)

**What**: The goal is a trustworthy D10. After Step 4 the ledger contains two populations —
records written before an observer existed (self-reported) and records written after
(observed) — and nothing distinguishes them. A count over the whole file would launder the
old ones into the new credibility. This is Open Question 6.

`log_transition` gains an `observed` field.

**The signal is per-write, not per-session (FA-002).** The obvious implementation —
reusing the `log_recorder_session` TMPDIR sentinel — is wrong, and wrong in the exact way
this step exists to prevent. That sentinel **latches once per session** by construction
(`lib.sh:194`: `[ -e "$sentinel" ] && return 0`), so it can only ever answer "did the
observer run at some point in this session," never "was *this* edge observed." One
truthful single-fragment write early in a session would stamp `observed: true` on every
later record — including split-Edit writes the fragment rule caused PreToolUse to skip
without comparing anything. That is Open Question 6's laundering, reappearing inside the
mechanism built to prevent it, and worse than the status quo: legacy records are honestly
unmarked, while these would carry a false attestation.

Instead the PreToolUse hook writes a **per-write token keyed to the doc and the declared
edge** — the two facts it has and the sentinel does not:

```
${TMPDIR:-/tmp}/claude-observed-$(printf '%s%s%s%s' "$sid" "$path" "$declared" "$to" | cksum | tr -d ' \t')
```

`plan_status_validate.sh` consumes it: token present for *this* `(doc, from, to)` →
`observed: "verified"`, and it **unlinks the token on read** so it cannot certify a second
write. No token → `observed: "unverified"`. Because the key includes the edge, a skipped
or crashed check produces no token for that edge and the record cannot inherit another
write's credibility.

**`observed` is three-valued, matching `attested` (FA-003, item 3).**
`review/transitions.py:114-167` already made exactly this decision for the recorder, and
documented why: *"Deliberately not folded into a boolean. A two-valued answer here would
reintroduce the collapse one level up."* Introducing `observed` as a boolean into the same
file would repeat the mistake that function exists to correct — because a PreToolUse crash
exits non-2 (every guard clause exits 0 on absence; `mktemp` failure exits 0 as at
`plan_status_validate.sh:19`) and is otherwise **indistinguishable from a pass**.

| Value | Meaning |
|---|---|
| `"verified"` | The observer ran on this exact edge and the declared prior matched disk |
| `"unverified"` | The observer ran but did not check this edge — the fragment rule skipped it |
| *absent* | No observer, or the observer could not run. **Never read as verified** |

`_parse` treats absent as *absent*, never as verified and never silently as "unverified" —
the same three-way distinction, for the same reason. `read_ledger` reports the populations
separately so a reader cannot quote a blended D10 without seeing the split.

**Snippet**:

```
{"ts":"…","repo":"galactus","doc":"…","from":"IN_PROGRESS","to":"EXECUTED","observed":"verified","observer":"1",…}
```

**`observed` is appended OUTSIDE `record` (FA-004).** `record` is built at `lib.sh:135`
and matched as a **substring** against `tail -1` for dedup (`lib.sh:148-152`). Putting
`observed` inside it would make dedup edge-*and*-verification-scoped, so the same edge
logged once verified and once not would stop deduplicating — turning the double-count bug
that guard exists to prevent back on. `record` keeps its current four fields exactly;
`observed` joins the outer `printf` alongside `track` and `epistemic`.

**`observer` is a version stamp (FA-005).** A single integer, bumped whenever the hook's
comparison logic changes. It is what makes a defective vintage separable after the fact in
an append-only file that `lib.sh:98-102` deliberately does not rotate and that this plan
declines to backfill — without it, records written during a period when the observer was
wrong are permanent and indistinguishable from correct ones. See Risks & Rollback.

**Test**: `cd ~/workspace/galactus && uv run pytest review/ -k transition -q`

**Done when**: a ledger mixing `verified`, `unverified` and unmarked records reports all
three distinctly; an unmarked legacy record is never counted as verified; a second write
reusing a consumed token is not marked verified; and dedup still collapses a doubled edge
that differs only in `observed`.

---

#### Step 7: Drift test for the duplicated edge table

**Files**: `.claude/hooks/tests/test_plan_transition_validate.sh` (append)

**What**: Open Question 5 accepted duplicating `LEGAL_EDGES`. That is only safe with a
mechanical check, otherwise the two tables diverge the first time an edge is added and the
error messages start disagreeing with the enforcement.

**Snippet**:

```bash
# Extract the LEGAL_EDGES literal from both hooks and compare. Not a semantic
# comparison — byte equality of the normalized block. A divergence is a bug even
# if the two tables happen to describe the same set.
a=$(sed -n '/^LEGAL_EDGES = {/,/^}/p' "$HOOKS/plan_status_validate.sh"    | tr -d ' \n')
b=$(sed -n '/^LEGAL_EDGES = {/,/^}/p' "$HOOKS/plan_transition_validate.sh" | tr -d ' \n')
[ "$a" = "$b" ] && pass "LEGAL_EDGES identical across both hooks" || fail "…"
```

**Test**: `bash .claude/hooks/tests/test_plan_transition_validate.sh`

**Done when**: the assertion passes, and manually perturbing one table makes it fail.
That second half is the actual verification — an extractor whose `sed` range misses would
compare two empty strings and pass vacuously.

### Test Plan

1. `bash .claude/hooks/tests/test_plan_status_validate.sh` → **102 passed, 0 failed**
   (baseline re-verified 2026-08-14 against the committed tree, before any change).
2. `bash .claude/hooks/tests/test_plan_transition_validate.sh` → 17 cases + drift test.
3. `cd ~/workspace/galactus && uv run pytest review/ -k transition -q` (Step 6).
4. Live probe (Step 4): a lying `From:` on a scratch plan doc must surface a block in the
   tool result, not merely exit 2 in isolation.
5. Negative control A (fires too little): stub the new hook to `exit 0`; cases 2 and 6
   must fail.
6. Negative control B (fires too much): remove the restatement branch; cases 13-17 must
   fail. Both controls are required — the first proves the guard works, the second proves
   it does not block the corpus, and the original suite could pass while failing the
   second.
7. Corpus sweep, the cheapest whole-system check: run the finished hook against **every**
   doc in `.claude/docs/plans/` using each doc's own front matter as the fragment. All
   must exit 0. Any block is a false reject on a file already in the repo.

The `pocs/ai/marketing-comms` conftest ImportError is pre-existing and unrelated — do not
fix it here (carried forward from the orchestrator design doc's Out of Scope).

### Risks & Rollback

| Risk | Mitigation |
|---|---|
| **A false reject blocks every plan-doc write in the repo.** The highest-severity failure here: this hook is on `PreToolUse Write\|Edit`, so a bad guard clause stops the pipeline for all sessions. | The fragment rule makes the default path exit 0, **and the restatement branch (Step 1 logic step 6) keeps settled docs writable** — the failure mode that fired *through* the fragment rule. Cases 13-17 guard it against real corpus docs. Step 4 is gated on Steps 1–3 green. Rollback is removing one line from `.claude/settings.json`. |
| Fragment-scoped coverage is mistaken for total coverage later. | Step 5 writes the residual gap into the hook and the test file, where the next reader looks. |
| `LEGAL_EDGES` tables diverge. | Step 7, with a perturbation check so it cannot pass vacuously. |
| Step 6 changes `lib.sh`, which the galactus#20 work also modifies. | That work is committed (`0a4ce35`) and the tree is clean; build on the committed tree. Do not rebase mid-build. |
| The ledger's old records get read as verified. | Step 6: `observed` is three-valued and absent is never verified; populations reported separately. |
| **A PreToolUse crash is indistinguishable from a pass.** Every guard clause exits 0 on absence, and `mktemp` failure exits 0 (`plan_status_validate.sh:19`), so a hook that could not run looks like one that approved. | The per-write token is keyed to `(doc, from, to)` and written only on the verified path: a crash produces no token, so the record is *absent*, not `verified`. Three-valued `observed` keeps "could not run" distinct from "ran and skipped". |
| **The ledger is contaminated by a defective observer vintage.** Unlike the hook, the ledger is append-only, unrotated (`lib.sh:98-102`) and not backfilled — bad records are permanent and inseparable. | The `observer` version stamp (Step 6) makes a vintage selectable after the fact. See the ledger rollback below. |
| The `observed` field changes dedup behaviour and reintroduces double-counting. | `observed` is appended **outside** `record`, whose substring match at `lib.sh:148-152` is unchanged. Asserted in Step 6's "Done when". |

**Rollback — the hook**: unregister in `.claude/settings.json` (Step 4). The hook becomes
inert immediately, and no plan doc carries a field that depends on it. Steps 5–6 are
independently revertable; Step 6's ledger field is additive and older readers ignore it.

**Rollback — the ledger** (FA-005). The hook is reversible in one line; **its output is
not reversible at all**, and the original plan reasoned only about the reversible half.
Records written while the observer was wrong stay in an append-only file forever. The
`observer` integer is what makes them separable: to retract a vintage, bump `observer` and
have `read_ledger` report per-vintage counts, so a known-bad range is excluded by
selection rather than by editing history. Retraction is therefore a **read-side filter,
not a file edit** — hand-editing the JSONL is explicitly not the rollback path, since it
destroys the audit trail this build exists to create.

Step 6 is also **ordered last on purpose**: Steps 1-5 put the observer in front of real
sessions before anything it emits is written to a permanent file. A defect found in that
window costs nothing, because no `observed` field exists yet to be wrong.

### Open Questions

All eight resolved above. Questions 1–6 were resolved 2026-08-14 before drafting; questions
7 and 8 were opened and resolved the same day by the `/proto-refine` failure pass, which
also revised 1 and 6. None outstanding for the executor.

**What the refinement pass changed**, so the executor knows which parts are load-bearing:

| # | Finding | Change |
|---|---|---|
| FA-001 | Persistent `From:` made every settled doc a false reject (3 of 14 corpus docs) | Restatement branch, Step 1 logic step 6; cases 13-17; corpus sweep |
| FA-002 | Session-latched sentinel certified sessions, not transitions | Per-write token keyed to `(doc, from, to)`, consumed on read |
| FA-003 | A crashed observer was indistinguishable from a passing one | `observed` three-valued, mirroring `attested` |
| FA-004 | `observed` inside `record` would have broken dedup | Appended outside `record`; asserted in Step 6 |
| FA-005 | Ledger contamination was permanent and unrollbackable | `observer` version stamp; read-side retraction; Step 6 ordered last |
| FA-006 | `observed` would be read as certifying phase execution | Step 5 comment states what it does and does not certify |

Two of these (FA-001, FA-002) were rated fatal and both were verified by simulation
against the real corpus, not accepted on argument.

One flagged for the operator at execute time, not a blocker: Steps 1, 3, 5 and 7 write
under `.claude/hooks/`, which is permission-denied to the agent, and Step 4 edits
`.claude/settings.json`. Each will prompt. An unattended `/proto-execute` run will stall on
the first of them.
