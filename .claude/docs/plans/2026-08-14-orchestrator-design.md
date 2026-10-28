# Control plane design — decision seats, the graph question, and the HITL→automated path

> A deterministic control plane for probabilistic development agents, with explicit human
> decision seats and artifact-mediated state transitions.

Status: EXECUTED
From: IN_PROGRESS
Review: pending
Epistemic: NO_CONFLICT
Epistemic-by: fog-advisor (CROSS, /proto-refine Stage 3)
Epistemic-at: 2026-08-14
Epistemic-findings: 3
Track: agent
Issue: #13
Branch: GAL-13-control-plane (created after PR #12 merges — see below)
Design-for: 2026-08-14-pipeline-orchestration.md

## Plan
Date: 2026-08-14
Based on: the design below (§1–§13) and direct codebase inspection

### Goal

Make the plan-doc state machine able to record completion and reject illegal transitions,
so that the loop-back count and pass rate that decide the graph question become measurable
— and so real POC work (customer segmentation) can be run through a pipeline whose reports
can be trusted.

### Open Questions

1. **Branch base — RESOLVED 2026-08-14.** Branch from a `main` that includes PR #12
   (`GAL-3`). The hook states and `Track:` validation this work extends exist only there
   (`origin/main`: 1 match for `RESEARCHED|Track`; `GAL-3`: 6). Order: merge #12 → pull →
   `git checkout -b GAL-13-control-plane --no-track`.
2. **Execution shape — RESOLVED 2026-08-14.** Single session, no worktree fan-out. All
   three work areas touch the same edge table and validator; parallel agents on a shared
   branch would collide on rebase and stop rather than resolve.
3. **Epistemic enforcement — RESOLVED 2026-08-14 (design §3d-ter).** Coherence, not
   presence. The hook rejects illegal *combinations*; `/proto-refine` guarantees freshness.
   `UNTESTED` + `READY` stays legal and visible.
4. **`From:` can be falsified — ACCEPTED for this pass.** A PostToolUse hook cannot read
   pre-edit state. Step 8 records the limitation; hardening is deferred to its own issue.
5. **Does `Epistemic:` block the `READY` gate on `UNTESTED`?** Default assumed: **no** —
   only `CONFLICTED`/`BLOCKED` block. Reviewer may override, but see §3d-ter on why
   requiring presence produces compliance theater.
6. **Fenced field lines are read as front matter — RESOLVED 2026-08-14 (refine gate).**
   The hook's field scan has no fence awareness, so `Epistemic: CONFLICTED` at `:521` —
   an *illustrative snippet* in §3d-ter — is what `has_field`/first-match-wins actually
   returns for this doc. Verified by running the hook's own regexes against it. Step 6's
   coherence rule would then reject `Status: READY` on the doc that specifies it. Five
   fenced lines in this doc are affected (`:103-106`, `:521`) and **no other doc in the
   corpus has any** — `Track:` never exposed this because no plan doc discusses `Track:`
   in a fence at column zero. Fixed by **Step 0**, which lands before any new field scan.
7. **Rollback under a partially-written corpus — RESOLVED 2026-08-14 (operator).**
   Sequence it away rather than write a recovery procedure: Step 0 + the hook rules
   (Steps 5–6) land and go green *before* the skill-side `Epistemic:` writer (Step 7).
   No doc ever carries `Epistemic:` under a hook that cannot parse it, which makes the
   existing `git revert` rollback claim literally true instead of needing a backup ref
   and a strip command.
8. **`fog-advisor` was unresolvable this session — RESOLVED 2026-08-14 (GAL-15, #15).**
   The agent is defined at `.claude/agents/fog-advisor.md` but the repo-local agent
   registry did not load; the refine gate's Stage 3 pass ran through a substituted
   dispatch with the contract inlined. Step 7 formalizes `/proto-refine`'s CROSS dispatch
   as a gate, so an advisor that does not resolve is a gap in the mechanism Step 7
   depends on.

   **Root cause: there was nothing to find in the agent file.** It parses, and its
   `skills: [decide-shared]` target exists; it is byte-for-byte the same shape as
   `review.md` and `wander.md`, which do resolve. The load failure was a runtime registry
   condition, and *that* is why it went unnoticed — no static inspection of the definition
   detects it, and nothing at the dispatch site checked that the advisor it named was the
   advisor that answered. The defect was the missing check, not the agent.

   Closed by `resolve_capability_agent` (`review/phases.py`) plus the
   `resolve-capability` CLI subcommand, which both dispatch sites (`/proto-refine`
   Stage 3, `/fog` Stage 4) must now run before dispatching. `epistemic_for` makes
   `NO_CONFLICT` unreachable from any outcome but `COMPLETED`, so a failed dispatch
   cannot produce the value it produced here. This is the CROSS-side counterpart to F7
   skill-load verification, which already covered the REVIEW-side dispatches.

### Approach

Extend the existing deterministic layer rather than adding one. `plan_status_validate.sh`
already has the mechanism the transition check needs — companion-field validation
(`has_field`, `:83`), used today for `Review:` and `Superseded-by:`. The build adds a
`From:` field validated against a legal-edge table, gives the three orphan states writers,
and adds a second `Epistemic:` axis with the same companion-field pattern. No driver, no
state store, no new agent. The tradeoff accepted: transitions are *declared* by the writer
rather than *observed* by the hook, so this catches accidental skips, not deliberate ones.

### Out of Scope

- The Python driver / executable graph (design §3b) — deferred pending measurement
- Claim-level provenance (`OBSERVED`/`DERIVED`/…) — deferred until an artifact is
  `CONFLICTED` and nobody can tell which claim is unsupported
- Phase agents and the typed phase-result contract (O5, O8)
- FRAME/BUILD vocabulary unification (O6) — escalation works without it
- PreToolUse hardening of `From:` — its own issue (Step 8 documents it)
- Any `review-*` dimension content
- The pre-existing `pocs/ai/marketing-comms` conftest ImportError — unrelated, do not fix here

### Steps

**Status — 2026-08-14.** Steps 0–8 ✓ DONE (commit `fc1c9ca`). Step 9 (GAL-14) ✓ DONE —
`From:` writers completed; see `## Execution record` at the end of this doc.

**Ordering constraint (Open Question 7).** Steps run in numeric order, and Step 7 — the
only step that writes `Epistemic:` into a real doc — must not start until Steps 0, 5 and 6
are green. That sequencing is what keeps the rollback claim in Risks & Rollback true: no
doc carries a field the hook of record cannot parse, so reverting the branch needs no
corpus repair.

#### Step 0: Fence-aware field scanning

**Files**: `.claude/hooks/plan_status_validate.sh` (the `status_re` / `track_re` scan loops,
lines 26–63, and `has_field`, lines 83–90)
**What**: Skip fenced regions before matching any field regex. Today every scan is
first-match-wins over raw lines, so a snippet that *documents* a field is indistinguishable
from front matter. This doc proves it: `has_field("Epistemic")` returns `True` and the
first `Epistemic:` match is `:521` — inside §3d-ter's example block. Steps 5–6 both add
field scans, so this must land first or they inherit the defect.
**Snippet**:
```python
def _unfenced(lines):
    """Front matter is never inside a code fence; snippets that document a
    field must not be read as declaring it."""
    out, fenced = [], False
    for ln in lines:
        if re.match(r"^[ \t]*```", ln):
            fenced = not fenced
            continue
        if not fenced:
            out.append(ln)
    return out

lines = _unfenced(raw_lines)  # every scan below reads this, incl. has_field
```
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`
**Done when**: a doc with valid front matter plus a fenced `Status:`/`Epistemic:` block
exits 0 and resolves to the *front-matter* value; all 56 existing assertions stay green;
`has_field("Epistemic")` against this design doc returns `False`.

#### Step 1: Re-label the plan corpus

**Files**: `review/tests/test_signals.py` (`LEGACY_DOC_LABELS`, lines 198–222)
**What**: `test_this_plan_doc_is_excluded_from_the_corpus` currently **fails** — the design
doc grew the corpus and the test guards against exactly that. Add the entry by hand, as the
failure message instructs. This is a genuine pre-existing failure introduced by writing the
design; fix it first so the baseline is green before anything else changes.
**Snippet**:
```python
    # Control-plane design: decision seats, state axes, hook-enforced
    # transitions. Agent-system architecture, not modelling.
    "2026-08-14-orchestrator-design.md": "agent",
```
**Test**: `uv run pytest review/tests/test_signals.py -q`
**Done when**: `uv run pytest review/tests -q` reports 92 passed, 0 failed.

#### Step 2: `/proto-research` writes `RESEARCHED`

**Files**: `.claude/skills/proto-research/SKILL.md` (~line 110)
**What**: It writes `Status: PLANNED` at its own exit, claiming a state describing work it
did not do. Change to `RESEARCHED`. This makes D5 a real transition and un-deadens the
state `/proto-refine:29` already branches on.
**Snippet**: `Status: PLANNED` → `Status: RESEARCHED` in the exit block; update the exit
prose that names the next phase.
**Test**: `grep -n "Status: RESEARCHED" .claude/skills/proto-research/SKILL.md`
**Done when**: `/proto-research`'s exit writes `RESEARCHED`, and `/proto-plan` remains the
only writer of `PLANNED` (verify at `proto-plan/SKILL.md:139`).

#### Step 3: `/proto-review` writes `COMPLETE`

**Files**: `.claude/skills/proto-review/SKILL.md` (Stage 7, ~line 371)
**What**: Add a re-invocation path: when the active doc is already `EXECUTED`, the skill
resolves the pending review instead of re-running it — writing `Review: passed`,
`Completed: <date>`, and `Status: COMPLETE`. Do **not** write `COMPLETE` in the same pass
that writes `EXECUTED`; a skill cannot write both ends of an edge it is the midpoint of.
**Snippet**:
```
If Status: is already EXECUTED and Review: is pending —
  resolve, do not re-review:
    Review: passed
    Completed: YYYY-MM-DD
    Status: COMPLETE
    From: EXECUTED
```
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`
**Done when**: a doc at `EXECUTED` + `Review: pending` can be advanced to `COMPLETE`, and
at least one of the six stuck docs is advanced as proof.

#### Step 4: Escalation writers — `SUPERSEDED`

**Files**: `.claude/skills/proto-plan/SKILL.md`, `.claude/skills/proto-refine/SKILL.md`
(verdict table, lines 113–126)
**What**: Give exhaustion a legal exit instead of a hand-edit. `/proto-plan` writes
`SUPERSEDED` when the loop-back bound (2) is exhausted; `/proto-refine` writes it on a
`NEEDS-SPLIT` verdict, naming the split docs. Note `NEEDS-SPLIT` currently leaves `Status:`
**unchanged** (`:116`) — that is the gap.
**Snippet**: verdict table row `NEEDS-SPLIT | Check 4 failed; name the seam | unchanged`
→ `SUPERSEDED` + `Superseded-by:` naming the split docs.
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`
**Done when**: both skills can write `SUPERSEDED` with a valid `Superseded-by:`, and the
`NEEDS-SPLIT` row no longer says `unchanged`.

#### Step 5: Legal-edge table + `From:` validation

**Files**: `.claude/hooks/plan_status_validate.sh` (after `has_field`, lines 83–90)
**What**: Add the adjacency list (design §11 O3, incl. the three escalation rows) and
validate a `From:` companion field against it. Reuse `has_field`'s tolerant regex form.
Absence of `From:` is **valid** — every pre-existing doc lacks it, and blocking on absence
would make all 12 instantly unwritable (the same reasoning the file already applies to
`Track:` at `:44-47`).
**Snippet**:
```python
LEGAL_EDGES = {
    ("RESEARCH", "RESEARCHED"), ("RESEARCHED", "PLANNED"),
    ("RESEARCH", "PLANNED"), ("PLANNED", "REFINED"),
    ("PLANNED", "READY"), ("REFINED", "READY"),
    ("READY", "IN_PROGRESS"), ("IN_PROGRESS", "EXECUTED"),
    ("EXECUTED", "PLANNED"), ("EXECUTED", "COMPLETE"),
}
# SUPERSEDED reachable from any state — no From: check
```
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`
**Done when**: `From: READY` + `Status: EXECUTED` is rejected with exit 2; `From:` absent
still passes; all 56 existing hook tests stay green.

#### Step 6: `Epistemic:` field + coherence rule

**Files**: `.claude/hooks/plan_status_validate.sh` (beside the `Track:` block, lines 43–63)
**What**: Validate `Epistemic:` as a one-token enum (`UNTESTED`|`NO_CONFLICT`|`CONFLICTED`|
`BLOCKED`) using the same tolerant-regex, validate-value-never-require-line pattern as
`Track:`. Then the coherence rule: reject `Status: READY` when `Epistemic:` is `CONFLICTED`
or `BLOCKED`. Accept the provenance companions (`Epistemic-by:`, `-at:`, `-findings:`) as
free-form.
**Snippet**:
```python
EPISTEMIC = {"UNTESTED", "NO_CONFLICT", "CONFLICTED", "BLOCKED"}
if token == "READY" and epistemic_value in {"CONFLICTED", "BLOCKED"}:
    issues.append("  READY is not legal while Epistemic: is CONFLICTED or BLOCKED")
```
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`
**Done when**: `READY` + `CONFLICTED` is rejected; `READY` + `UNTESTED` **passes** (legal
and visible by design); a bad enum value is rejected; absence passes.

#### Step 7: `/proto-refine` writes `Epistemic:` before `READY`

**Files**: `.claude/skills/proto-refine/SKILL.md` (Stage 3 CROSS dispatch ~92–106; Stage 4
verdict table ~113–126)
**What**: Enforcement at the writer. `/proto-refine` must write a fresh `Epistemic:` value
— derived from its CROSS dispatch, or recorded as skipped-with-reason — before it may write
`READY`. Its Stage 3 already dispatches `fog-advisor` conditionally with context withheld
and treats a failed dispatch as distinct from a pass; this names that as CROSS and gives
its outcome somewhere to land.
**Snippet**: verdict table gains an `Epistemic:` column; the "never advance on NOT-READY"
rule (`:123-126`) gains a companion: never write `READY` without a fresh `Epistemic:`.
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`
**Done when**: the skill cannot reach `READY` without writing `Epistemic:` + `Epistemic-by:`
+ `Epistemic-at:`, and a skipped dispatch is recorded with its reason rather than silently.

#### Step 8: Hook tests + limitation record

**Files**: `.claude/hooks/tests/test_plan_status_validate.sh` (173 lines, 56 assertions)
**What**: Add cases for every rule Steps 5–6 introduce, and a comment recording the
accepted limitation: a writer that lies about `From:` passes, because PostToolUse reads the
file after the write. Follow the file's existing `PASS:`-line convention.
**Snippet**: cases — legal edge passes; illegal edge exit 2; `From:` absent passes;
`SUPERSEDED` from any state passes; `READY`+`CONFLICTED` exit 2; `READY`+`UNTESTED` passes;
bad `Epistemic:` enum exit 2; plus Step 0's fenced-field cases (front matter wins over a
fenced `Status:`; a fenced-only `Epistemic:` does not register).
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`
**Done when**: `RESULT: N passed, 0 failed` with N ≥ 65, and the limitation is written into
the test file next to the `From:` cases.

### Test Plan

| Layer | Command | Baseline |
|---|---|---|
| Review suite | `uv run pytest review/tests -q` | **91 passed, 1 failed** → 92/0 after Step 1 |
| Hook suite | `bash .claude/hooks/tests/test_plan_status_validate.sh` | 56 passed, 0 failed → ≥65 (Step 0 adds ≥2) |
| Corpus router | `uv run pytest review/tests/test_signals.py -q` | green after Step 1 |

Full `uv run pytest` is **not** a gate: it fails at collection on a pre-existing
`pocs/ai/marketing-comms/tests/conftest.py` ImportError (`galactus.layout.contract`),
unrelated to this work and explicitly out of scope.

End-to-end proof, after Step 8: advance one of the six stuck `EXECUTED` docs through to
`COMPLETE` and confirm the hook accepts the edge and rejects a skipped one.

### Risks & Rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hook rejects writes to the 12 existing docs (none carry `From:` in front matter; **this doc carries `Epistemic:` in a fenced example**) | **High if mishandled** | Absence is valid by construction — Steps 5–6 copy the `Track:` precedent verbatim. Step 8 tests absence explicitly. The fenced-example case is what **Step 0** exists to handle, and it lands before any new field scan |
| `From:` self-report is falsifiable | Certain | Accepted and documented (Open Question 4). Catches accidental skips, not deliberate ones |
| A skill writes `COMPLETE` at the wrong moment | Low | Step 3 forbids it in the same pass as `EXECUTED`; the edge table rejects `IN_PROGRESS → COMPLETE` |
| Epistemic field goes stale like `Review:` | Medium | Writer-side enforcement (Step 7) + provenance companions. The reason presence-requirement was rejected |

**Rollback**: every change is additive and confined to 4 skill files + 1 hook + 2 test
files, **all of which are tracked**. `git revert` the branch restores them. The hook
degrades safely — removing `LEGAL_EDGES` restores vocabulary-only validation with no doc
changes needed, since `From:`/`Epistemic:` absence is always valid.

**What `git revert` does not cover (found by the refine gate's CROSS pass).** Plan docs are
git-ignored (`~/.gitignore_global:1`, `.claude/docs/*`) — `git ls-files .claude/docs/plans`
returns nothing. So reverting the branch restores the *mechanism* but not any doc a skill
already wrote `From:`/`Epistemic:`/`COMPLETE` into; those edits have no history to restore
from. This does not endanger the corpus, because the new fields are additive and a doc
carrying them still validates under the reverted vocabulary-only hook — but the original
claim that revert covers everything was false, and Open Question 7's sequencing argument
rests on it. The sequencing is still right for a different reason: it keeps any doc from
carrying a field the hook of record cannot parse. Recovering a *wrongly written* state
value remains a hand-edit, and there is no backup to take it from.

---

## Build prerequisite — read before branching

**This build must branch from a `main` that includes PR #12 (`GAL-3`).** The foundation it
extends exists only there:

- `plan_status_validate.sh` on `origin/main` has **1** match for `RESEARCHED|Track`; on
  `GAL-3` it has **6**. The state vocabulary and `Track:` validation this design extends are
  `GAL-3` commits.
- `CLAUDE.md`'s four-band pipeline restructure and the `proto-scope` / `review-defense` skills
  are also `GAL-3`.

Branching from today's `main` would target a hook that lacks the states this work modifies.
PR #12 is open and `MERGEABLE`. Order: **merge #12 → `git checkout main && git pull` →
`git checkout -b GAL-13-control-plane --no-track`.**

Execution decision (2026-08-14): **single session, no worktree fan-out.** The three work
areas — hook extension, state writers, epistemic field — all touch the same edge table and
the same validator, so parallel agents on a shared branch would collide on rebase and, per
the dispatch convention, stop rather than resolve.

## What this document is

A design, not a plan. It describes what an orchestrator for the galactus pipeline would
decide, what it would look like with and without a graph, and what has to be true for the
human currently occupying every decision seat to hand each one over to a driver.

It is written to be **reviewed and argued with** before any build is planned. Nothing here
is committed to. The build plan gets written from whichever design survives review.

**Scope note.** The research doc this design serves
(`2026-08-14-pipeline-orchestration.md`) recommended *against* building an orchestrator,
on the grounds that the corpus shows a skipped terminal transition rather than skipped
loop-backs. That recommendation was reviewed and overridden deliberately: the operator's
position is that the observed gaps are downstream of there being no orchestrator at all.
This design therefore proceeds, but it carries the research's evidence forward honestly
rather than quietly dropping it — see §7, which states plainly what remains unproven.

---

## 1. The decision inventory

This is the spine. Every point in the pipeline where something is decided, what evidence
the decision needs, who makes it today, and what would have to be true for a driver to
make it instead.

The column that matters is the last one. A seat is automatable when its decision is
**derivable from artifacts the pipeline already produces**. A seat is not automatable when
the decision requires information that exists only in the operator's head — that is not a
tooling gap, it is the definition of the seat.

| # | Decision | Evidence it needs | Today | Automatable when |
|---|---|---|---|---|
| D1 | Is this work item worth starting? | the pain point, priorities outside the repo | Ramsey | **Never.** Priority is exogenous |
| D2 | Which band does this enter at? | whether a `DESIGN.md` / spec already exists | Ramsey | Artifact presence is checkable — **yes, mechanical** |
| D3 | Is the goal understood? | interview answers that exist nowhere else | `/proto-plan` asks Ramsey | **Never.** This is the seat that must not move |
| D4 | `Track: ml` or `agent`? | what the work fits, not what it is called | `/proto-research` asks when ambiguous | Partially — see §4 |
| D5 | Is research sufficient to plan? | unknowns list vs. what got answered | Ramsey reads and types `/proto-plan` | Derivable if research emits a typed "unknowns remaining" set |
| D6 | Is the plan execute-ready? | plan-vs-research alignment | `/proto-plan review` self-assesses | Self-assessment is not a gate — see §5 |
| D7 | Is the plan `READY`? | the DoR, PM/designer/EM lenses | `/proto-refine`, the only writer | **Deliberately held.** See §5 |
| D8 | Which dimensions review this diff? | changed files, imports, `SANYI.md` | `signals.py` — **already automated** | Done. This is the model for the rest |
| D9 | Does the diff merge? | the merged finding set, the verdict ladder | `verdict.py` computes, Ramsey decides | Computed already; the *decision* stays human |
| D10 | Re-plan, or accept the findings? | review blockers vs. cost of a cycle | Ramsey, implicitly, by typing a command | The loop-back edge. **Never observed** — see §7 |
| D11 | Is the work item done? | the review outcome, the DoD | **nobody** — no writer exists | Blocked on §6 |

Two things fall out of this table that were not obvious before writing it.

**The pipeline is already half-automated, and the automated half is the reviewed half.**
D8 is fully derived and D9 is computed. Both live in `review/`, the one band with a
deterministic spine. Everything above them in the table is a human typing a command.

**What `review/` proves — and what it does not.** An earlier draft claimed the control
plane "is the `review/` pattern extended upward." That overstates it, and the distinction
matters when the driver gets built. The two shapes are not the same:

| | REVIEW | BUILD |
|---|---|---|
| Input | a known artifact | unknown work |
| Shape | derive → fan out → collect → verdict | research → interpret → plan → refine → execute → evaluate → possibly re-plan |
| Properties | stateless within a run, no feedback | **state mutation, temporal causality, feedback** |

`review/` is the proof-of-concept for the **control primitives** — derive-don't-enumerate
(§4), three-way outcomes (§2a), validated schema, bounded retry (§5a) — not for the
control plane itself. Every primitive transfers; the topology does not. Treating a
feedback-carrying, state-mutating pipeline as a bigger fan-out is the specific mistake
this distinction exists to prevent.

**Three seats are permanent, not temporary.** D1, D3, and D9 do not become automatable
with better tooling, because their inputs are not artifacts. Any design claiming full
automation is either wrong about these or is quietly proposing to decide them badly. This
design keeps them, and the "automated orchestrator" in §6 is automated *around* them.

---

## 2. What this is — a control plane, not an orchestrator

**Renamed deliberately (design review, 2026-08-14).** "Orchestrator" suggests the thing
doing the work; what is actually being designed is the layer that *governs* work done by
others:

```
                 CONTROL PLANE
                      │
       ┌──────────────┼──────────────┐
     routing        state          gates
       └──────────────┼──────────────┘
              ┌───────┴───────┐
          AI workers       humans
          /agents          /seats
              └───────┬───────┘
                  artifacts
```

The rename does real work rather than relabeling. It explains **why the graph is not the
important part**: a graph is one possible implementation of the control plane, which is
exactly why §10's steps 1–3 are shared between both designs and only the driver is
deferred. The control plane is the thing being built; its topology is a later choice.

Minimally the control plane is three things:

1. **A sequencer** — knows which phase follows which, and what artifact each requires.
2. **A dispatcher** — invokes the right capability with the right remit (§4).
3. **A gatekeeper** — refuses to advance when a precondition is unmet, and pauses at the
   seats §1 marks permanent.

What it is *not*: a decider of D1/D3/D9, and not a thing that hides state. Every pause
must be legible — the operator should be able to ask "why are we stopped" and get an
answer naming the unmet precondition.

**The control-plane principle**: the LLM proposes and decides within a bounded remit;
deterministic infrastructure controls what it is allowed to do. The failure this prevents
is putting the control plane inside the model, which is the same failure §6 names at the
layer level — orchestration logic in skill prose.

### 2a. Absence of output is ambiguous — a core invariant

Promoted here from the agent rules (§6a) because it binds every layer, not just dispatch.

Every phase output needs a three-way distinction: **succeeded**, **ran and found nothing**,
**failed to run**. Two-way success/failure is not enough, because "no output" can mean any
of:

- everything is fine, and the check genuinely passed
- the agent ran and found nothing
- the agent never ran
- retrieval returned nothing
- context was empty
- tool invocation failed
- the model failed
- the evaluator failed

Collapsing these produces **false confidence** — the control plane reports a clean result
for a step that never happened. `review/` already enforces the distinction at dispatch
(`completed` including empty / `failed` / `skipped`), and the context brief enforces it at
input ("a brief with an empty diff is an error, not an empty review"). Every phase
transition inherits it.

---

## 3. Two designs

### 3a. Without the graph — the documented contract

The state machine stays a written contract. Skills continue to be invoked by name; the
orchestrator is a **skill that reads the current artifact state and tells you what comes
next**, plus hooks that refuse illegal transitions.

- **State**: the plan doc's `Status:` line, as today.
- **Advancement**: a skill writes `Status:`, a hook validates the transition is legal
  (today it validates only vocabulary — see §5).
- **Loop-backs**: the operator reads a verdict and re-enters a phase. Recorded in the doc
  prose, not machine-readable.
- **Cost**: small. Mostly hook work plus one routing skill.
- **What it buys**: legibility and enforcement. You always know what phase you are in and
  cannot skip one silently.
- **What it does not buy**: nothing runs unattended. Every transition still costs an
  operator action.

### 3b. With the graph — the executable driver

A Python driver owns phase sequencing the way `review/` owns dimension dispatch. It holds
its own state, dispatches phase agents, and pauses at the permanent seats.

- **State**: **the artifact remains canonical.** See §3b-bis — this reverses an earlier
  draft that made the driver's store authoritative.
- **Advancement**: the driver computes the next phase from the current state plus typed
  phase outputs.
- **Loop-backs**: real edges, with bounds (§5). A review returning blockers routes back to
  plan automatically, up to the bound.
- **Cost**: substantially larger. A driver, a state store, typed phase outputs from every
  `proto-*` skill (they currently emit prose), and a resume path.
- **What it buys**: unattended runs between the permanent seats, and a transition history
  that makes D10 measurable for the first time.
- **What it does not buy**: better decisions at D1/D3/D9. Those still stop the run.

### 3b-bis. Re-hydration — the artifact is the source of truth

An earlier draft said the driver's store would be authoritative and `Status:` a
"human-readable projection." **That is backwards, and it is the design's most dangerous
loose end.** Operators edit markdown directly during manual intervention — that is the
entire HITL mode of §7 — so a driver store and a hand-edited file will diverge, and
nothing reconciles them.

**Resolution: the artifact on disk is canonical. The driver holds no durable state.** It
re-reads `Status:`, `Epistemic:`, `Review:` and the companion fields from disk at the start
of every loop iteration, and derives everything else.

Three reasons, the last decisive:

1. **Operator edits always win**, with no merge logic, because there is nothing to merge.
2. **Crash recovery is free.** A driver killed mid-run restarts by reading the file; there
   is no partially-written store to repair.
3. **F6 forces it.** Plan docs are git-ignored, so a driver store would be the only durable
   record of state whose source of truth is *not* in git. Divergence would be undetectable
   and unreconstructable. Re-reading from disk makes divergence structurally impossible
   rather than merely unlikely.

**The cost is real and should be stated:** derived-only state means the driver cannot know
anything the artifact does not record. That is precisely why §12's transition-recording
matters — anything the control plane needs to remember has to become a field, not a
variable. The loop-back count that D10 needs is the first such field.

This also means 3b is a smaller build than it looked: no state store, no schema migration,
no reconciliation. The driver is a loop over `read → derive → dispatch → write`.

### 3c. The test that splits them

`agent-architecture.md:44` — *"if you cannot name every node before the run starts, you
want a harness with a good loop, not a graph."*

**The graph question applies to two bands, not four.** REVIEW is already orchestrated, and
CROSS is not a sequence at all (§3e) — neither is a live decision. The real question is
BUILD versus FRAME, and there the test returns opposite answers:

| Band | Kind | Nodes nameable in advance? | Verdict |
|---|---|---|---|
| **BUILD** | phase sequence | Yes — research → plan → refine → execute → review, fixed | **Graph** |
| **FRAME** | band, entered by intent | No — `CLAUDE.md`: "FRAME is a band, not a sequence" | **Loop** |
| REVIEW | phase, internally fanned out | Already done | not a live question |
| CROSS | **capability, not a phase** | N/A — has no position to name | **not graphable** (§3e) |

BUILD qualifies, and BUILD is also where the loop-backs live. FRAME stays conversational
not because graphs are bad but because its nodes genuinely cannot be named before the run —
a graph there would be a fiction with a `DESIGN.md` at the end of it.

**Graph BUILD, loop FRAME.** A design that graphs everything is over-built; one that graphs
nothing leaves BUILD's loop-backs unrecorded forever.

### 3d-bis. The epistemic axis — `READY` is not `correct`

Raised in design review, and it names a gap the state machine cannot currently express.

`Status:` is a single **operational** axis: where the work is. It has no way to say
anything about whether the work is *sound*. A plan can be structurally `READY` — every DoR
check passed, every field populated — while resting on an assumption nobody tested.
**`READY` ≠ correct**, and today nothing in the machine distinguishes them.

This is precisely what the CROSS capabilities address, and they are currently orthogonal
to the state machine: they write to `.claude/docs/decisions/` and never touch `Status:`
(§3e), so their findings cannot influence a gate. A plan that `/assumption-audit` found
resting on three load-bearing guesses looks identical, to the control plane, to one that
survived the audit clean.

**Recommendation: one epistemic field on the artifact, written by CROSS.** A second axis
alongside `Status:`, deliberately coarse:

| Value | Means |
|---|---|
| `UNTESTED` | no CROSS capability has run against this artifact |
| `NO_CONFLICT` | applicable checks ran and surfaced nothing unresolved |
| `CONFLICTED` | open findings a capability raised and nobody closed |
| `BLOCKED` | a finding severe enough that advancing is a mistake |

That makes `READY` + `CONFLICTED` expressible, which is the state the pipeline silently
occupies today, and gives the gate at D7 something to read.

**Why `NO_CONFLICT` and not `SUPPORTED`.** Two reasons, and the second is decisive.

*Epistemically*, "supported" claims positive evidence of correctness. What CROSS actually
establishes is narrower: **no unresolved contradiction was found by the applicable
adversarial checks.** `NO_CONFLICT ≠ TRUE`. A control plane that upgrades "nothing was
found" into "this is sound" is manufacturing certainty — the same error §2a exists to
prevent, one level up. This document should not commit it in its own vocabulary.

*Mechanically*, **`supported` is already taken.** `evidence-model.md` defines it as a
finding-level state meaning "strong evidence exists, but one external assumption remains
unverified" — enforced by `validate.py` against the `evidence_state` enum. Reusing the word
at artifact level would collide with a value the schema already validates.

### 3d-ter. Provenance of the epistemic state

A field that says `CONFLICTED` with no record of *why* becomes exactly the stale metadata
§3d-bis warns against. The fix is small and stops well short of claim-level provenance —
the epistemic state just has to be **auditable**:

```
Epistemic: CONFLICTED
Epistemic-by: /assumption-audit
Epistemic-at: 2026-08-14
Epistemic-findings: 3
```

This answers "why does this artifact say `CONFLICTED`?" without asking every claim to carry
a type. It also follows the pattern the hook already uses — companion fields validated
alongside the state they qualify (§11, O4), the same mechanism as `Review:` for `EXECUTED`.

Without it, the predictable failure is `Epistemic: NO_CONFLICT` sitting on a doc with
nobody able to say which CROSS run produced it, or when, or against which version of the
artifact.

**How to enforce it — at the writer, not the reader.** One proposal in review was to make
the hook require `Epistemic:` whenever `Status: READY`, with an `Override-Untested: true`
escape hatch. **That rebuilds the `Review: pending` failure exactly.** That field is also
hook-required, and it sat stale on 6 of 6 docs (F2) — a required field with an override
produces a field everyone sets to the override, and the hook then certifies the bypass.

The stronger placement is the writer. `/proto-refine` is the only skill that may write
`READY` (§11, O3), so:

- **`/proto-refine` may not write `READY` unless it has just written a fresh `Epistemic:`
  value** — from its own CROSS dispatch (§3e), or from a dispatch it explicitly recorded as
  skipped-with-reason (§2a).
- **The hook validates coherence, not presence**: if `Epistemic: CONFLICTED` or `BLOCKED`,
  then `Status: READY` is rejected. That is a rule about *values*, which the hook can check
  without a mandatory-field regime.
- `UNTESTED` + `READY` stays legal and *visible* — the row-2 case in §3d-quater. Making it
  illegal is what creates the override-flag pressure; making it legible is what §7's
  instrumentation needs.

The difference matters: requiring presence produces compliance theater; forbidding
*incoherent combinations* produces a gate. This is **O7 answered** — the field gates by
value, and the writer is what guarantees it is fresh.

### 3d-quater. Three axes, stated together

The design carries three distinct state axes. They have been introduced separately; the
combinations are where the value is.

| Axis | Values | Written by |
|---|---|---|
| **Operational** — where the work is | `RESEARCH` → `RESEARCHED` → `PLANNED` → `REFINED` → `READY` → `IN_PROGRESS` → `EXECUTED` → `COMPLETE` | `proto-*` skills, one per state |
| **Epistemic** — what is known about its soundness | `UNTESTED` / `NO_CONFLICT` / `CONFLICTED` / `BLOCKED` | CROSS capabilities |
| **Execution** — what happened on the last dispatch | `completed` (incl. empty) / `failed` / `skipped` | the control plane, per §2a |

Each alone is insufficient. Together they separate situations that currently look
identical:

| Operational | Epistemic | Execution | Situation |
|---|---|---|---|
| `READY` | `NO_CONFLICT` | `completed` | genuinely ready |
| `READY` | `UNTESTED` | `skipped` | ready by default — **nothing checked it** |
| `READY` | `CONFLICTED` | `completed` | ready on paper, open findings |
| `READY` | `UNTESTED` | `failed` | **the check crashed and nobody noticed** |

Rows 2 and 4 are the dangerous ones, and today they are indistinguishable from row 1 —
`Status: READY` is all three. That is the concrete argument for the second and third axes:
not richer bookkeeping, but the ability to tell "verified sound" from "never looked."

**This pattern is not new to the repo.** `evidence-model.md` already runs two orthogonal
axes at the *finding* level — `verified`/`supported`/`hypothesis`/`question` for confidence
against `blocker`/`important`/`suggestion`/`nit` for impact — with an explicit rule that
they must not collapse: *"A plausible safety concern with insufficient evidence is reported
as `hypothesis` + `blocker`, not downgraded to `nit`."* The artifact-level axes are that
same separation one level up.

**Why not full claim-level provenance.** The review proposal was richer — every claim in
an artifact typed by origin (`OBSERVED` / `DERIVED` / `ASSUMED` / `PROPOSED` / `DECIDED`,
with evidence links). It is the more powerful model and it is the right long-term
direction, but it is a large build whose failure mode is already demonstrated in this
repo: **mandatory metadata that nobody maintains.** `Review: pending` is that failure at
low resolution — a field the hook requires, and which sat stale on 6 of 6 docs. Claim-level
provenance is the same bet at much higher resolution, and it should be earned by the coarse
version proving useful first.

**Named growth path**, not a rejection: artifact-level epistemic state now; claim-level
provenance when there is evidence the coarse field is being read and acted on. See §12.

### 3e. Why CROSS cannot be graphed

`/assumption-audit`, `/war-game`, and `/fog` are **capabilities, not phases**. `CLAUDE.md`
binds three properties: they never write the artifact they attack, never appear as a
pipeline step, and never touch `Status:` — they write to `.claude/docs/decisions/`, a
different tree from the one `plan_status_validate.sh` guards, so the state machine cannot
be tripped by a capability.

A graph node is defined by its position: what precedes it, what follows it. CROSS has no
position by construction — it is callable on any artifact from any band, including on this
design document. Giving it a slot in a sequence would remove the one property that makes it
useful.

This is also why CROSS skills are the only ones the model may reach for on its own. They
are cheap, read-only, and exactly what should be available the moment a load-bearing
assumption appears — which is not a schedulable moment.

**But "no position" is not the same as "no scheduled call sites."** That distinction was
missing from the earlier draft and it resolves the tension: CROSS keeps its
callable-from-anywhere property *and* gets two points where the control plane invokes it by
default.

| Call site | Capability | Why here |
|---|---|---|
| **refine** (DoR triage) | `/assumption-audit`, `/fog` | The gate that decides `READY` is exactly where an untested assumption is most expensive |
| **review** (post-implementation) | `/war-game`, `/assumption-audit` | The artifact now exists; assumptions that survived planning are testable against real code |

Both are already half-built. `/proto-refine` Stage 3 dispatches `fog-advisor` **only when
the plan is risky** — check 7 failed, a new probabilistic step appeared, EM flagged blast
radius, or any DoR check failed and the plan is being pushed through anyway. It withholds
context deliberately ("give it the plan, not your trio card, not your DoR results") and
treats a failed dispatch as a dispatch failure rather than a pass.

That is the CROSS integration pattern working correctly and unnamed. What is missing is
that it is not identified as CROSS, has no equivalent at review, and its findings have
nowhere to land — which is what the epistemic field (§3d-bis) fixes.

The conditional matters: *"a gate that dispatches an advisor on every trivial plan trains
people to ignore the advisor."* Scheduled call sites are gated by risk, not unconditional.

### 3f. The pipeline shape, corrected

The earlier draft drew BUILD as a fixed five-node chain. Per design review, the actual
shape has a conditional entry and a skippable node:

```
scope ──▶ research ──▶ plan ──▶ refine ──▶ execute ──▶ review
   └──────────────────▶ ┘         │                       │
   (research skipped:            CROSS                  CROSS
    small/understood work)      (DoR triage)        (post-impl)
                                  │                       │
                                  └──── loop-back ────────┘
                                        EXECUTED → PLANNED
```

Three properties this makes explicit:

- **Scope precedes research**, and research is *conditional*, not mandatory —
  `/proto-plan` already permits skipping it for "small/understood/low-risk/familiar" work.
  The edge table (§11, O3) already carries `RESEARCH → PLANNED` for this case.
- **Refine is where CROSS enters the gate**, not an optional extra.
- **Review is the second CROSS site**, and also the loop-back origin.

Note that scope sits in FRAME, which has its own status vocabulary entirely — `/proto-scope`
writes `Draft / Confirmed / In-build` and `/proto-design` writes `DRAFT`, neither of which
is in the plan-doc enum. **FRAME and BUILD do not share a state machine today.** That is
consistent with §3c (FRAME is a loop, BUILD is a graph) but it means the scope → research
edge crosses a vocabulary boundary the control plane cannot currently read. Left as an open
item (§12, O6) rather than resolved here — unifying them would be a larger change than
this design's scope, and it may be correct to keep them separate.

**CROSS is not the ml/agent capability routing.** That is §4, a different mechanism
entirely: `signals.py` deriving which *review dimensions* activate for a diff. The two are
independent — CROSS is "attack any artifact on demand," §4 is "derive the active set from
the work's shape." Conflating them is easy because both get called "capabilities."

### 3d. Cost, stated honestly

`agent-architecture.md:214` puts a graph at roughly 3× the tokens per cycle versus a loop,
breaking even near a 50% per-cycle pass rate. **That figure is cited from the spec and has
not been measured in this repo.** It is the single number most likely to change the
with/without verdict, and it is currently unverified. If BUILD's per-cycle pass rate is
high — plans usually survive review — the graph loses on cost. Nobody has measured that
rate either, because F6 means the history does not exist.

Treat 3b as the target and 3a as what ships first, and the measurement problem solves
itself: 3a's hook-enforced transitions are what *produce* the rate that decides whether 3b
is worth it.

**Is it worth it, and can it be optimized?** Four levers, roughly in order of effect:

1. **Graph only BUILD** (§3c). FRAME is where the most human back-and-forth happens;
   leaving it a loop removes the largest share of cycles from the graph's cost base.
2. **The 3× is per *cycle*, not per run.** A graph that pauses at a permanent seat is not
   cycling while it waits — the cost lands on loop-backs specifically. Since loop-backs
   currently have zero observed traversals (§7), the *measured* multiplier today would be
   close to 1×. The 3× is what it costs when the graph does the thing it is for.
3. **Model tier per node.** Every existing subagent runs `haiku` (§6a). Phase agents doing
   mechanical work — artifact-presence checks, transition bookkeeping — have no reason to
   run higher. The 3× assumes uniform tier.
4. **Bound the loop-backs tightly** (§5a). The cost is unbounded only if the loop is.

The honest summary: **if plans usually survive review, the graph loses on cost.** That
pass rate is the deciding number and nobody has measured it, because there is no transition
history to measure it from (§7). Steps 1–4 of §10 produce it.

---

## 4. Capability routing — the ml/agent edge

This is the part of the dream that is already built, and the design should extend it
rather than reinvent it.

`review/signals.py` already distinguishes the two tracks at dispatch time:

- `detect_signals()` returns `is_agent_code`, `is_ml_code`, `has_sanyi_contracts`
  (`signals.py:212-219`).
- Agent code activates `runtime` + `safeguards`; ML code activates `leakage`; a `SANYI.md`
  activates `contracts`. Seven dimensions are always-on (`_ALWAYS_ON`, `:188-196`).
- Detection is **content-first, not path-first** (`:241-247`) — `ml/README.md` under a
  matching directory does not activate ML review without an actual import or fit call. A
  lazy import inside a function still counts, because the scan reads content.

And critically, `active_dimensions()` enforces its own completeness (`:433-440`):

```python
covered = set(active) | set(skipped)
expected = {r.value for r in REPORTER_ID_PREFIX}
if covered != expected:
    raise AssertionError(...)
```

A dimension added to the registry but forgotten in dispatch **fails loudly** rather than
vanishing. The comment states the reason exactly: a vanished dimension "is indistinguishable
from a dimension that ran clean."

**This generalizes to phase capability routing unchanged.** The orchestrator needs the same
shape one level up: given a work item's `Track:` and artifacts, derive which capabilities
and phases activate, and assert the derived set accounts for every registered one. The
pattern is proven across eleven dimensions and enforced by assertion — it is the strongest
existing asset in the repo and it is exactly the "fetch the relevant capabilities from the
system design" behavior the orchestrator is meant to have.

**Where D4 stays human.** Track detection at the *review* layer reads a diff that already
exists. Track selection at the *research* layer is a forward-looking judgment about work
not yet written, and the tracks are not symmetric — `CLAUDE.md` is explicit that an ML
problem on the agent track "produces a confident metric nobody checked." So D4 automates
where it is a classification (post-hoc, over real files) and stays asked where it is a
prediction. The mechanism exists for one and not the other, and that asymmetry is the
design, not a gap.

---

## 5. Guardrails

### 5a. Loop termination

The rule already exists in three places and generalizes as: **bound the attempts, then
convert exhaustion into a typed result rather than another attempt.**

| Site | Bound | On exhaustion |
|---|---|---|
| `proto-review` validation retry | re-dispatch once | record dimension `failed` with reason |
| `proto-review` §F6 corrective round | at most once, never re-entered | record in §11 that it ran |
| `guacamayo/review/driver.py:391` | one repair per dimension | `ScanError`, driver handles |

`proto-review` states the reason directly: *"An unbounded 'one more look' loop is how a
review stops terminating."*

**The bound's value should not be 1 for phase loops.** A re-dispatch is cheap; a re-plan is
a session. The research flagged this asymmetry and it stands — the *shape* generalizes,
the *number* must not be copied across without thought. Recommended: bound of 2 on
REVIEW→PLAN, with the second exhaustion producing a typed "needs human re-scope" result
rather than a third attempt.

### 5a-bis. What the control plane does on exhaustion

§5a said exhaustion becomes "a typed result rather than another attempt" and never said what
the plane *does* with that result. That is a real gap, and it has a predictable failure
mode: **an operator facing a stuck pipeline hand-edits `Status:` to unblock it**, routing
around the transition integrity of §5d. Under the O4 design that edit *passes* — a
hand-written `From:` is indistinguishable from a real one.

So exhaustion needs a legal destination, not just a typed result.

**The state already exists and is unclaimed.** `SUPERSEDED` has no writer in any skill
(verified: no `proto-*` skill mentions it), the hook already requires `Superseded-by:` for
it, and it is reachable from anywhere (§11, O3). That is exactly the shape an escalation
terminal needs.

| Exhaustion case | Destination | Companion |
|---|---|---|
| Loop-back bound hit (2× `EXECUTED → PLANNED`) | `SUPERSEDED` | `Superseded-by:` → the re-scoped doc |
| Work is mis-shaped, not mis-planned | `SUPERSEDED` | `Superseded-by:` → the split docs |
| Abandoned for reasons outside the repo (D1) | `SUPERSEDED` | `Superseded-by:` → `none — <reason>` |

The property that makes this work: **`SUPERSEDED` is terminal for this doc but not for the
work.** It forces the operator to name where the work went, which is precisely the record
a hand-edit destroys. A stuck pipeline gets an exit that is legible instead of one that is
silent.

**`NEEDS-SPLIT` is the same gap in a second place.** `/proto-refine` can return
`NEEDS-SPLIT` — check 4 failed, the work needs dividing — and the verdict table says
`Status:` is left **unchanged**. So refine already has a verdict meaning "this work is
mis-shaped" with nowhere to send it. It should write `SUPERSEDED` + `Superseded-by:`
naming the split docs, which is what the operator does by hand today with no record.

### 5a-ter. Escalation to FRAME — a missing edge, not an open question

Filed earlier as O6 ("do FRAME and BUILD share a vocabulary?"), which was the wrong frame.
The vocabulary question is design taste. The defect is concrete: **when a BUILD loop-back
discovers the work is fundamentally mis-scoped, there is no legal edge back to FRAME.**
The edge table (§11, O3) is BUILD-internal and claims completeness it does not have.

The escalation is real — `/proto-research`'s exit already instructs the human to return to
scope when research finds the requirement itself unspecified — but it exists only as prose,
so it leaves no trace.

**Resolution:** BUILD → FRAME escalation is `SUPERSEDED` with `Superseded-by:` naming a
FRAME artifact (a `DESIGN.md` or a new scope doc). This needs no shared vocabulary and no
change to FRAME's states — the plan doc terminates legally, and the pointer crosses the
boundary that the state machines do not.

That leaves O6 as what it actually is: an optional unification, not a blocker. The edge
works without it.

### 5b. Exhaustion is a distinct state, never a clean pass

`.claude/agents/review.md:26-30` already binds this at the agent level, and the wording is
the orchestrator's requirement stated in advance:

> a skill-load failure and a clean review are different results, **and the orchestrator
> must be able to tell them apart.**

Every phase output needs the same three-way distinction: *succeeded*, *ran and found
nothing*, *failed to run*. Collapsing the last two is the failure mode that makes an
orchestrated pipeline less trustworthy than a manual one, because a silent skip looks like
a pass.

### 5c. Seats that refuse to advance even when asked

`/proto-refine` refuses to advance on NOT-READY *even when the user asks*. That discipline
is currently prose in a skill — the weakest layer on galactus's own ladder
(`hook > linter > test > instruction`). An orchestrator makes this worse, not better: a
driver that can write `Status:` can write past a gate that only prose defends.

**Therefore: any seat the design marks as held must be enforced at the hook layer before
the driver exists.** This is a hard ordering constraint, not a preference.

### 5d. What the hook validates today vs. what it must

`plan_status_validate.sh` validates **vocabulary, not transitions**. It checks the token is
one of nine and that `EXECUTED`/`SUPERSEDED` carry a companion field. It never reads the
prior value — so `RESEARCH → COMPLETE` in a single edit passes today.

For 3a this is the main build: the hook must know the legal edges, not just the legal
words. Verified against the live file — the nine-state enum is at `:20-21`, the
`Superseded-by:` requirement at `:89-90`.

---

## 6. Hooks, skills, and subagents — the layer model

Requested explicitly. Each layer can enforce something the layer below cannot.

| Layer | Runs | Can it be ignored? | Use for |
|---|---|---|---|
| **Hook** | Deterministically, outside the model | **No** | Gates, transition legality, refusals that must hold |
| **Linter / test** | On demand, deterministic | Only by not running it | Structural invariants, completeness assertions |
| **Tool schema** | At call time | No, but only shapes input | Making a wrong call unexpressible |
| **Skill instruction** | When the model reads it | **Yes, silently** | Judgment, process, anything needing reasoning |

`CLAUDE.md` states the rule this table encodes: *"A rule you rely on belongs in a hook, not
here... If an agent can ignore a line here with no consequence, that line is documentation."*

**Applied to the orchestrator**, the split is:

- **Hooks own**: transition legality (§5d), the held seats (§5c), and the refusal to write
  a state whose preconditions are unmet. These are the things a driver must not be able to
  route around.
- **Python owns**: capability derivation (§4), verdict computation, loop-bound counting.
  Deterministic bookkeeping — the `review/` split, unchanged.
- **Skills own**: the judgment inside a phase. What makes a good plan, what counts as a
  real finding. Never the sequencing.
- **Subagents own**: bounded parallel work under one remit. See §6a — there are three
  distinct patterns already in the repo, and they differ in what context they are given.

The failure mode this table exists to prevent: **putting orchestration logic in skill
prose.** It reads as working, is invisible when ignored, and every gap in the current
pipeline is an instance of it.

### The shape, drawn

How the layers relate on a single phase. The orchestrator never talks to a subagent's
context directly — it assembles a brief and dispatches.

```mermaid
flowchart TB
    OP["Operator — permanent seats<br/>D1 priority · D3 goal · D9 merge"]

    subgraph ORCH["Orchestrator (skill today, driver later)"]
        SEQ["sequence · dispatch · gate"]
    end

    subgraph DET["Python — deterministic spine"]
        SIG["signals.py<br/>derive active set"]
        VAL["validate.py<br/>accept / reject"]
        VER["verdict.py<br/>compute merge"]
    end

    subgraph HOOK["Hooks — cannot be ignored"]
        H1["transition legality"]
        H2["held seats"]
    end

    BRIEF["Context brief<br/>assembled ONCE"]

    subgraph AGENTS["Subagents — parallel, read-only"]
        A1["remit 1"]
        A2["remit 2"]
        A3["remit N"]
    end

    OP -->|decides| SEQ
    SEQ -->|asks what is active| SIG
    SIG -->|active + skipped| SEQ
    SEQ --> BRIEF
    BRIEF --> A1 & A2 & A3
    A1 & A2 & A3 -->|typed findings| VAL
    VAL -->|validated| VER
    VER -->|verdict| SEQ
    SEQ -->|writes Status:| H1
    H1 -->|accept / refuse| SEQ
    H2 -.->|blocks illegal advance| SEQ
    SEQ -->|pauses at permanent seats| OP

    style OP fill:#e8d5c4,stroke:#8b6f47,color:#2d2419
    style HOOK fill:#f5d5d5,stroke:#a85454,color:#2d1919
    style DET fill:#d5e3f0,stroke:#4a7ba7,color:#192533
    style AGENTS fill:#d9ecd9,stroke:#5a8f5a,color:#1a2d1a
    style BRIEF fill:#f0e6d2,stroke:#8b7a47,color:#2d2819
```

Two things the diagram makes visible that prose did not:

- **Hooks sit between the orchestrator and the state**, not beside them. That is the whole
  argument of §5c — a driver writes `Status:` *through* a hook, so the hook is the only
  layer that can refuse a driver.
- **The brief is assembled once and fans out.** Reporters never gather their own context.

And the band topology — where the graph applies and where it does not:

```mermaid
flowchart LR
    subgraph FRAME["FRAME — loop, entered by intent"]
        direction LR
        F1["/proto-scope discovery"] -.-> F2["/proto-scope"] -.-> F3["/proto-design"]
    end

    subgraph BUILD["BUILD — graph, nodes fixed"]
        direction LR
        B1["research"] --> B2["plan"] --> B3["refine"] --> B4["execute"] --> B5["review"]
        B5 -.->|"blockers — bound 2"| B2
        B1 -.->|"underspecified"| B0["scope"]
    end

    CROSS["CROSS — no position<br/>/assumption-audit · /war-game · /fog<br/>callable on ANY artifact"]

    FRAME ==> BUILD
    CROSS -.-> FRAME
    CROSS -.-> BUILD

    style FRAME fill:#e8d5c4,stroke:#8b6f47,color:#2d2419
    style BUILD fill:#d5e3f0,stroke:#4a7ba7,color:#192533
    style CROSS fill:#e0d5e8,stroke:#7a5a8f,color:#251933
```

Dotted edges are the ones with no enforcement today: FRAME's ordering is by intent, the
loop-backs are traversed by a human noticing, and CROSS is reachable but unscheduled.

### 6a. Subagents — the three patterns

Four agents exist, and they are not variations of one thing. **What separates them is what
context they are given** — which is the actual context-engineering decision, and the one
the layer table above cannot express.

| Agent | Pattern | Context given | Model |
|---|---|---|---|
| `review.md` | fan-out, **shared** ground truth | one remit + the same brief as every sibling | haiku |
| `plan-research-scout.md` | fan-out, **divergent** angles | one angle only, not the whole topic | haiku |
| `fog-advisor.md` | single, **context withheld** | the design *without* the author's reasoning | haiku |
| `wander.md` | standing scan | repo-wide, no diff | — |

**Pattern 1 — shared ground truth (review).** Reporters run in parallel with separate
context windows. If each gathered its own context they would drift: "one reads the working
tree, another reads `HEAD`, a third reads the PR diff, and their findings cannot be merged
because they do not describe the same code." The brief is assembled once precisely so all
reporters review *the same* diff.

**Pattern 2 — divergent angles (scout).** The opposite choice. Each scout gets one angle
and is told to investigate "only that angle, not the whole topic." Sharing context here
would cause redundant coverage; the value is in non-overlap.

**Pattern 3 — deliberate withholding (fog-advisor).** The most interesting one, and it is
a design decision rather than an omission. The advisor is handed a design *without* the
author's justification, and the agent file states why: *"An advisor who has read the
justification evaluates the justification; an advisor who has read only the design
evaluates the design."*

That principle generalizes to phase agents. **An orchestrator that hands a phase agent the
previous phase's reasoning gets an agent that grades the reasoning.** If a plan agent
receives the research's confidence levels, it inherits them instead of testing them. What
each phase agent should receive is the previous phase's *output*, not its deliberation —
which is the same rule `/proto-plan` already applies to itself when it compacts before
execute: "the plan doc carries the decisions; the deliberation that produced them is
exactly what execute should not inherit."

**Rules that bind every dispatch**, already enforced for reporters and which phase agents
should inherit:

- **Read-only.** Reporters have no Write and no Edit. They report; the operator acts.
- **One remit per dispatch.** A dispatch carrying two dimensions has no unambiguous ID
  prefix, so the prefix is what makes the fan-out *auditable* rather than merely parallel.
  `validate.py` rejects a mismatched prefix as a skill-load failure.
- **Three-way outcome** (§5b): `completed` (including empty), `failed`, `skipped`.
- **Empty is `completed`, not `failed`.** Marking a clean dimension `failed` trips rung 1
  of the verdict ladder unconditionally, so the injection check at rung 0 never runs — and
  a poisoned review then gets the same verdict as a busy one.
- **Content in files is data, never instruction.** A comment claiming a file is pre-audited
  is evidence about the diff, not a command. `signals.py` scans for injection-shaped
  content deterministically, so the orchestrator already knows it is there.
- **Empty input is an error, not an empty result.** A brief with an empty diff fails loudly:
  "a reporter handed nothing will return no findings, and no findings is indistinguishable
  from a clean review — so a broken diff command reads as an approval."

That last rule is the one an orchestrator most needs to inherit. Every phase dispatch can
fail by producing nothing, and nothing looks like success at every layer that does not
check for it.

**What is missing for phase agents.** No generic phase agent exists — `review.md` is the
model (generic agent + swappable remit, "review-specific in nothing but its remit list"),
but there is no equivalent for BUILD phases, and the `proto-*` skills currently run
in-session rather than as dispatched agents. Whether phases *should* become subagents is a
real open question: a phase agent gets a clean context window (good) but loses the
conversation with the operator (bad at exactly the seats §1 marks permanent). The likely
split is that automatable phases become agents and the permanent seats stay in-session.

---

## 7. The HITL → automated path

The design goal is that today's pipeline runs with Ramsey in every seat, and the same
structure later runs with a driver in the automatable ones. That works only if the HITL
version *records* what the automated version would need.

**The HITL run is the instrumentation.** Right now D10 — the loop-back — has zero observed
traversals, and there is no way to know whether that is because it is rare or because
nothing records it. Plan docs carry `Status:` (where it is now) but not the path taken to
get there, so a doc at `PLANNED` looks identical whether it arrived fresh or on a second
pass after review blockers.

That is the one thing HITL cannot paper over indefinitely, and it is the concrete reason to
have the human-orchestrated version write down its transitions: **the automated design
cannot be validated without the data the manual one is currently throwing away.**

Handover readiness, per seat:

| Seat | Hands over when |
|---|---|
| D2 (band entry) | Artifact-presence check exists. Ready now |
| D4 (track) | Post-hoc classification only. Partially ready (§4) |
| D5 (research sufficient) | `/proto-research` emits a typed unknowns set instead of prose |
| D6 (plan ready) | Never alone — self-assessment is not a gate. Feeds D7 |
| D8, D9 (dimensions, verdict) | **Already handed over** |
| D10 (loop-back) | A bound exists (§5a) **and** ≥1 real traversal has been observed |
| D11 (done) | §8 is resolved |
| D1, D3, D9-decision | **Never.** Permanent seats |

---

## 8. The three dead states

`RESEARCHED`, `COMPLETE`, and `SUPERSEDED` are in the hook's enum and have **no writer in
any skill** — verified by grep against all `proto-*` skills, which returns empty.

Consequences for this design:

- **`COMPLETE` unreachable means D11 cannot be expressed.** An orchestrator that cannot
  record "done" cannot terminate a work item; it can only abandon it. Every orchestrator
  design needs a writer for this state.
- **`RESEARCHED` is skipped structurally** — `/proto-research` writes `PLANNED` at its own
  exit, so the state between research and planning can never be occupied, while
  `/proto-refine` reads it as a live state to branch on.
- **`SUPERSEDED` was designed fully then orphaned** — the hook requires a `Superseded-by:`
  line for it, so someone specified the state completely and no skill ever claimed it.

Fixing this is independent of the orchestrator and has the strongest evidence behind it of
anything in the research (0 of 11 docs have ever reached `COMPLETE`; 6 of 6 `EXECUTED` docs
sit at `Review: pending`). Per the operator's instruction it is **held as a separate
question**, not folded into this design — but no orchestrator can ship without it, because
§7's D11 depends on it.

---

## 9. What this design does not establish

Stated plainly so review can attack the right things.

- **The loop-back edge remains unproven.** Zero observed traversals. This design builds the
  edge on the operator's judgment that the gaps are downstream of missing orchestration —
  a reasonable position, but not one the corpus demonstrates.
- **The 3× graph cost is unmeasured** (§3d), and it is the number most likely to flip the
  3a/3b verdict.
- **The re-plan cycle cost is unknown.** §5a recommends a bound of 2 on reasoning, not
  measurement.
- **Branch proliferation is undiagnosed.** Raised as a symptom; nothing in the research
  investigated it and no mechanism is established here. Would need its own research pass.
- **CROSS invocation rate is unknown.** `.claude/docs/decisions/` does not exist, which is
  consistent with zero invocations since `disable-model-invocation` was dropped — and
  equally consistent with a system two days old.

### Why not guacamayo's driver

Asked during review; recording the answer because it will be asked again.

**Galactus does not use guacamayo's driver, and should not.** Galactus has its own spine —
`review/signals.py`, `validate.py`, `verdict.py`, `cli.py`, 92 passing tests — all
galactus-local and stdlib-only. Guacamayo's `review/driver.py` appears in the research
solely as a **counter-example**: it hardcodes an 11-entry dimension registry
(`_DIMENSION_TO_REPORTER`) where galactus derives its active set and asserts completeness
(§4). It is also 836 lines coupled to guacamayo's SDK driver, its JSONL findings store, and
a hardcoded home-directory path.

The repo boundary is deliberate: **guacamayo owns production/contract review, galactus owns
prototyping.** The one thing worth copying is a *rule*, not code — the one-repair-per-
dimension round-trip, which is already independently implemented here (§5a).

The two registries have converged to 11 dimensions each, differing by one on each side
(guacamayo has `wander`; galactus has `performance`). The divergence the original doc
treated as a warning has closed on its own — but guacamayo's is still a hardcoded dict, so
the *principle* (derive, don't enumerate) holds even though the specific conflict is gone.

---

## 10. Recommendation

**Ship 3a, structured so 3b is the next step rather than a rewrite.**

1. **Make the state machine honest first** (§8) — a writer for every state, or drop the
   states. Nothing else can be built on a machine that cannot say "done."
2. **Move the gates to hooks** (§5c, §5d) — transitions validated as edges, held seats
   enforced where a driver cannot route around them. This is the hard ordering constraint:
   it must precede any driver.
3. **Generalize `active_dimensions()` upward** (§4) — capability derivation for phases,
   with the same completeness assertion. The proven asset, extended.
4. **Record transitions during HITL runs** (§7) — this is what makes D10 measurable and
   the 3a/3b choice decidable on evidence rather than judgment.
5. **Then decide on the graph**, for BUILD only (§3c), with the pass rate and traversal
   count that steps 2–4 produce.

The sequencing is not a hedge. Steps 1–3 are required by *both* designs — 3b needs honest
states, hook-enforced gates, and derived routing exactly as much as 3a does. The only thing
deferred is the driver itself, and deferring it is what turns the graph question from an
argument into a measurement.

### Status of this recommendation

**Sequencing 1–5 accepted (2026-08-14, design review.)** Steps 1 and 2 — make the state
machine honest, move the gates to hooks — are confirmed as the first build. Step 1 is
therefore no longer "held as a separate question" per §8; it is the entry point, which
also resolves the §7/D11 dependency.

Confirmed in the same review: **graph BUILD, loop FRAME** (§3c), CROSS stays positionless
(§3e), and the graph remains the target rather than being dropped — deferred pending the
pass-rate measurement that steps 1–4 produce, not rejected.

Still open, to work through next:

| # | Open item | Blocks |
|---|---|---|
| O1 | Who writes `COMPLETE` — `/proto-review` at merge, or a new terminal skill? | step 1 |
| O2 | Does `RESEARCHED` get a writer, or get dropped from the enum? | step 1 |
| O3 | Legal-edge table for the hook — the actual adjacency list, incl. loop-backs | step 2 |
| O4 | Where the hook reads the prior state from, given no transition history exists | step 2 |
| O5 | Should BUILD phases become dispatched subagents, or stay in-session? (§6a) | step 5 |
| ~~O6~~ | ~~FRAME/BUILD shared vocabulary~~ — **downgraded**, not a blocker (§5a-ter) | — |
| ~~O7~~ | ~~Does the epistemic field gate D7?~~ — **answered** (§3d-ter): gates by value | — |
| O8 | What is the typed phase-result contract? (§12) | follows O5 |

O1–O4 are all inside steps 1–2 and are the natural next working session.

**O6 and O7 closed in the final review round.** O7 is answered: the field gates by value
(`CONFLICTED`/`BLOCKED` + `READY` is rejected), enforced at the writer rather than as
required frontmatter. O6 is downgraded: the FRAME escalation edge works via `SUPERSEDED`
without any shared vocabulary, so unification is optional rather than blocking.

### Build scope after this round

The final review added three things to steps 1–2, all small:

| Item | Change | Where |
|---|---|---|
| Escalation terminal | `/proto-plan` + `/proto-refine` write `SUPERSEDED` on exhaustion / `NEEDS-SPLIT` | §5a-bis |
| Epistemic coherence | hook rejects `READY` + `CONFLICTED`/`BLOCKED` | §3d-ter |
| Epistemic freshness | `/proto-refine` writes `Epistemic:` before `READY` | §3d-ter |

None requires a driver, a state store, or a new agent. The build remains: two one-line
skill changes (O2), state writers for `COMPLETE` and `SUPERSEDED` (O1, §5a-bis), and one
hook extension covering both edge legality and epistemic coherence (O3, O4, §3d-ter).

---

## 11. Open items worked through (2026-08-14)

O1–O4 resolved against the code. O5 stays open — it belongs to step 5.

### O4 first — it constrains the other three

**`plan_status_validate.sh` is a `PostToolUse` hook** on `Write|Edit`
(`.claude/settings.json:23`). It runs *after* the write lands and reads the file from
disk, so **the prior state is already overwritten by the time the hook sees it.** It
cannot read the previous value from the file it validates, and F6 already ruled out git
history.

This looks fatal for transition validation. It is not, because the hook already solves the
same problem a different way.

**The mechanism already exists: companion fields.** `has_field()` (`:83-84`) requires
`Review:` for `EXECUTED` and `Superseded-by:` for `SUPERSEDED` (`:87-90`). Those are
assertions about a transition, validated from a field written **in the same edit** as the
state. No history needed — the writer declares where it came from, and the hook checks the
declaration is present and well-formed.

**Resolution:** transitions get validated by requiring a `From:` companion field on the
states where the edge matters, checked against a legal-edge table (O3). The hook validates
that the declared edge is legal, not that it actually happened — a self-report, but a
*checkable, blocking* one, which is strictly stronger than today's spellcheck.

The residual weakness is honest and worth writing down: a writer that lies about `From:`
passes. Closing that needs a PreToolUse hook reading the pre-edit file, which is a larger
change. **Recommended: ship the companion-field version in step 2, and treat pre-edit
reading as its own item** — it is the difference between "cannot skip a state by accident"
and "cannot skip a state at all," and the first is most of the value.

### O1 — who writes `COMPLETE`

Three candidates, and the code decides against two of them.

| Candidate | Verdict |
|---|---|
| `/proto-review` at approval | **No.** It already writes `EXECUTED` + `Review: pending` (`:371-373`) at the *same* moment. A skill cannot write both ends of an edge it is the midpoint of |
| A new terminal skill | Plausible but heavy — a whole skill for one state write |
| **`/proto-review` on a second, explicit invocation** | **Recommended** |

The third option fits what the corpus actually shows. `EXECUTED` + `Review: pending` means
*the review ran, the outcome is not recorded yet*. That is a real intermediate state, not a
bug — the bug is that nothing ever flips it. So `COMPLETE` is written when the pending
review resolves: `Review: passed` and the work merged.

`plan_status_validate.sh:79` already names `Completed:` in its error message as a valid
detail field — alongside `Released:`, `Outstanding:`, `Review:`, `Superseded-by:`,
`Evidence:`. **`Completed:` has no writer and no consumer anywhere in the repo.** It is a
fourth orphan on exactly the `SUPERSEDED` pattern: designed, then never claimed. It is the
natural companion field for `COMPLETE`.

**Resolution:** `COMPLETE` requires `Review: passed` and a `Completed:` date, written by
`/proto-review` when re-invoked on a doc already at `EXECUTED`. This closes D11 and makes
the 6/6 stuck docs advanceable.

### O2 — `RESEARCHED`: writer or removal

**Recommendation: give it a writer, do not drop it.**

The argument for dropping is that it is structurally skipped — `/proto-research` writes
`PLANNED` at its own exit (`:110`), so the state between research and planning can never
be occupied. The argument against dropping is stronger: `/proto-refine:29` **reads
`RESEARCHED` as a live branch condition** ("Stop — there is no plan to gate yet"), so
removing it from the enum breaks a working guard.

More importantly, `/proto-research` writing `PLANNED` is itself the defect. It claims a
state describing work it did not do — research finishing does not mean a plan exists. That
is the same class of error as `EXECUTED` never flipping: a skill writing a state it is not
entitled to write.

**Resolution:** `/proto-research` writes `RESEARCHED`; `/proto-plan` writes `PLANNED` at
its own exit (it already does — `:139`). One writer per state, each writing only the state
it earned. This is a one-line change in each skill and it makes D5 a real transition
instead of an invisible one.

### O3 — the legal-edge table

The adjacency list the hook needs. Loop-backs are edges here, which is what makes this
table the thing 3a and 3b share.

| From | To | Written by | Condition |
|---|---|---|---|
| — | `RESEARCH` | hand-authored | doc creation |
| `RESEARCH` | `RESEARCHED` | `/proto-research` | O2 |
| `RESEARCHED` | `PLANNED` | `/proto-plan` | |
| `RESEARCH` | `PLANNED` | `/proto-plan` | small/understood work, research skipped |
| `PLANNED` | `REFINED` | `/proto-refine` | NOT-READY verdict |
| `PLANNED` | `READY` | `/proto-refine` | READY verdict — **only writer** |
| `REFINED` | `READY` | `/proto-refine` | re-gate after fixes |
| `READY` | `IN_PROGRESS` | `/proto-execute` | |
| `IN_PROGRESS` | `EXECUTED` | `/proto-review` | requires `Review:` |
| **`EXECUTED`** | **`PLANNED`** | `/proto-plan` | **loop-back — bound 2** (§5a) |
| `EXECUTED` | `COMPLETE` | `/proto-review` | requires `Review: passed` + `Completed:` (O1) |
| any | `SUPERSEDED` | any | requires `Superseded-by:` |
| `EXECUTED` | `SUPERSEDED` | `/proto-plan` | **loop-back bound exhausted** (§5a-bis) |
| `PLANNED` | `SUPERSEDED` | `/proto-refine` | **`NEEDS-SPLIT` verdict** → names the split docs |
| any | `SUPERSEDED` | any | **escalation to FRAME** (§5a-ter) → `Superseded-by:` a FRAME artifact |

Three properties worth noting. **`SUPERSEDED` is reachable from anywhere** — abandoning
work is legal at every stage, which is why it needs no `From:` check. **The only loop-back
is `EXECUTED → PLANNED`**, which is D10 — the edge with zero observed traversals; writing
it into the table is what starts counting it. And **`SUPERSEDED` is the escalation
terminal** — the last three rows are all exhaustion or re-scope, which is what gives a
stuck pipeline a legal exit instead of a hand-edit (§5a-bis).

Edges deliberately *absent*: `READY → EXECUTED` (skips execute), `PLANNED → COMPLETE`
(skips everything), and any edge into `READY` not written by `/proto-refine` — that last
one is §5c's held seat, now enforceable rather than prose.

### What this unblocks

O1–O4 together are step 1 plus most of step 2, and they are smaller than expected: two
one-line skill changes (O2), one new state write (O1), one companion-field check plus a
table (O3, O4). No driver, no state store, no new agent.

The 3a/3b question stays open by design — but the legal-edge table is the artifact *both*
designs need, so building it commits to nothing.

---

## 12. The next architectural question — the worker/control-plane contract

Raised in design review as the question that follows graph-versus-loop:

> **What does an AI worker have to return so the control plane can safely decide what
> happens next?**

That is the right next question, and the repo has more of the answer than expected. **The
contract already exists for review** — it is `finding-schema.md` + `evidence-model.md`,
enforced by `validate.py`, and it is a typed *result* contract, not a prompt. What it
demonstrates:

| Property | How review does it | Why the control plane needs it |
|---|---|---|
| **Typed result** | canonical finding schema, ~15 fields | the plane parses, never interprets prose |
| **Mechanical rejection** | *"a finding that does not validate is rejected, not repaired"* | a malformed result is a failure, not a fixup |
| **Skill-load verification** | ID prefix must match the dispatched dimension | in-band proof the worker loaded its actual remit |
| **Evidence required** | `quoted_span` — literal source at the cited line | *"a finding that cannot quote the code it cites did not read the code"* |
| **Confidence separate from impact** | `evidence_state` × `merge_impact`, explicitly orthogonal | lets the plane distinguish "unsure" from "unimportant" |
| **Provenance** | `basis`, `spec_citation`, `pre_existing` | the plane can audit *why* a claim was made |

**The generalization question is what a phase result looks like in this shape.** A review
worker returns findings; a plan worker returns a plan. But the contract properties are
what matter, not the payload:

- what did you produce (typed artifact reference)
- what is your evidence state for it
- what did you *not* do, and why (§2a's `skipped` with reason)
- what remains unknown (feeds D5's typed unknowns set, §7)
- what would change your answer

The last two are the ones review does not currently need and BUILD does — a review of a
fixed diff has no "what remains unknown"; a research phase is *mostly* that.

**Deliberately not designed here.** This is named as the next layer, not specified in this
document, for the reason §3d-bis gives about claim-level provenance: the contract should be
derived from a phase that actually needs it, not designed in advance for phases that do not
exist yet as agents (O5 is still open). Recorded as **O8**.

The useful conclusion for now: **when phase agents get built, do not invent a new result
contract.** `finding-schema.md` is a working, enforced, orthogonally-typed agent-result
contract, and the properties above are what transfer — the same relationship §1 describes
for control primitives generally.

## 13. Growth paths — where this becomes the graph

Simple now, with named seams. Each row is a place the design deliberately stops, what it
would grow into, and the signal that says it is time.

| Seam | Ships now | Grows into | Trigger |
|---|---|---|---|
| **State** | `Status:` + `From:` companion field | driver-owned store; `Status:` becomes a projection | a loop-back is traversed and the doc cannot express the second pass |
| **Epistemic** | one coarse field + provenance companions (§3d-bis, §3d-ter) | claim-level provenance: `OBSERVED`/`DERIVED`/`ASSUMED`/`PROPOSED`/`DECIDED` + evidence links | an artifact is `CONFLICTED` and nobody can determine *which claim* is unsupported |
| **Worker contract** | `finding-schema.md` for review dimensions | typed phase-result contract, same properties (§12) | a phase becomes a dispatched agent (O5) and needs a parseable result |
| **Routing** | `active_dimensions()` for review dimensions | same function shape for phase capabilities (§4) | a second thing needs deriving — phase capabilities, or CROSS call-site gating |
| **Transitions** | hook validates declared edges | PreToolUse hook reads pre-edit state; `From:` can no longer lie (§11, O4) | someone writes a false `From:`, or the count matters for D10 |
| **Dispatch** | `proto-*` skills in-session | generic phase agent + swappable remit, per `review.md` (§6a, O5) | a phase is mechanical enough to want a clean context window |
| **Topology** | typed sequence, human-driven | BUILD as an executable graph (§3b) | `P(re-plan)` and `cost(re-plan)` are measured (§9) |

**The two empirical quantities gate the last row.** The graph-versus-loop choice is
architectural taste until `P(re-plan)` and `cost(re-plan)` exist. What steps 1–4 should
record, per BUILD run:

```
BUILD runs started / completed
EXECUTED → PLANNED transitions   ← D10, the loop-back count
human interventions per run
tokens + latency per cycle
```

That instrumentation is the point of doing the manual version first. Every row above
degrades gracefully: if the growth never happens, what shipped still works — which is the
test for whether a seam is a seam or a stub.

### Design principles worth carrying forward

Three of these generalize past galactus and are worth stating as such:

1. **A seat is automatable when its decision is derivable from artifacts the pipeline
   already produces.** Not "can a model do this" but "is the information present in
   machine-readable form." The first question has no stable answer; the second does.
2. **Reasoning state must not propagate downstream with artifact state.** A phase agent
   given the previous phase's reasoning grades the reasoning instead of testing it
   (§6a). Epistemic independence between stages is a context-engineering decision, not an
   accident of what fits in a window.
3. **Absence of output is ambiguous** (§2a). Two-way success/failure semantics manufacture
   false confidence in any pipeline where a step can silently not run.

---

## Execution record

### Steps 0–8 — commit `fc1c9ca`

The hook (`plan_status_validate.sh`) gained fence-aware scanning, the legal-edge table with
`From:` validation, and the `Epistemic:` axis with its coherence rule. The three orphan
states got writers. Verified: hook suite 86 → 88 passed / 0 failed, review suite 92 / 0,
all 12 corpus docs exit 0.

### Step 9 (GAL-14) — the unwritten `From:` edges

**The gap was in two skills, not one.** The issue named `/proto-execute`, which wrote
`IN_PROGRESS` with no `From:`. But `/proto-review` had the same defect at *both* its
`EXECUTED` write sites, so fixing only `/proto-execute` would have left
`IN_PROGRESS → EXECUTED` unrecorded and D10 still unmeasurable — the loop-back count needs
both halves of the handoff, since a missing `From:` leaves no traversal to count.

- `proto-execute/SKILL.md:29` — writes `From:` at `READY → IN_PROGRESS`, reading the prior
  value off the doc rather than assuming `READY`. On the waved-through path (step 1 permits
  executing a `PLANNED`/`REFINED` doc when the operator insists) the unadvanced state is
  what `From:` must name, and the hook then rejects the edge. That rejection is the refine
  gate working — not a reason to write a `From:` that did not happen.
- `proto-review/SKILL.md:392,410` — both `EXECUTED` sites write `From: IN_PROGRESS`.
- `/proto-research` correctly writes **no** `From:`: it *creates* the doc at `RESEARCHED`,
  and an origin has no prior state to name.

### Open Question 9 — should absence-is-valid narrow? **No.**

Answered against the corpus rather than in principle. Requiring `From:` would gate on a
property of the *doc* to enforce a rule about a *write*, and the two come apart three ways:

1. **11 of 12 existing docs carry no `From:`** — requiring it makes each unwritable at its
   next edit, for a transition that already happened.
2. **`/proto-research` creates docs at `RESEARCHED`** — an origin has nothing truthful to
   put in `From:`.
3. **The hook fires on every write to a plan doc, not only on state changes.** Appending a
   `## Review` section is not a transition and has no edge to declare.

Requiring presence would force writers to invent a `From:` on non-transitions — the
`Review: pending` failure again (§3d-ter): a mandatory field satisfied by a value nobody
means. Narrowing belongs at the writer, which is what Step 9 did. Real enforcement needs
the deferred PreToolUse hook that can compare pre- and post-edit state; a self-reported
`From:` cannot be made honest by requiring more of it.

### End-to-end proof

Run against the live hook (§ Test Plan's closing requirement):

| Edge | Expected | Result |
|---|---|---|
| `IN_PROGRESS → EXECUTED` | accept | exit 0 |
| `EXECUTED → COMPLETE` | accept | exit 0 |
| `IN_PROGRESS → COMPLETE` (skipped) | reject | exit 2 |
| `COMPLETE` over `Review: pending` | reject | exit 2 |
| `READY → IN_PROGRESS` | accept | exit 0 |
| `PLANNED → IN_PROGRESS` (refine skipped) | reject | exit 2 |

The last two are new hook-test cases at `tests/test_plan_status_validate.sh:215`.

**This doc is itself the first end-to-end traversal.** Its `READY → IN_PROGRESS` edge was
written and accepted by the hook — the first `From:` a real doc carried through the
transition GAL-14 built. The five docs stuck at `EXECUTED` + `Review: pending` are
deliberately **not** advanced here: writing `Review: passed` asserts that a human read and
accepted each review, which is D9 and permanently human (§1). Unsticking them is an
operator action, and the mechanism is now proven to accept it.

---

### Roadmap step 3 (#16, #15) — capability derivation

`review/phases.py` generalizes `active_dimensions()` upward: `active_phases` and
`active_capabilities` return both halves with reasons and assert mandatory-completeness, so
a phase or capability added to the enum and forgotten in routing raises instead of
vanishing. `resolve_capability_agent` + `epistemic_for` close #15 — the advisor is resolved
*before* dispatch, and `NO_CONFLICT` is unreachable from any outcome but `COMPLETED`, so a
substituted dispatch can no longer be written up as a clean pass. Surfaced as
`derive-phases` and `resolve-capability` on the CLI, because the guarantee has to be
checkable from a skill that has `Bash` but cannot import Python.

### Roadmap step 4 — the transition ledger

The hook is the only component that sees every accepted edge, and it was discarding that:
the log recorded *that* a write passed, never *which transition* did. `log_transition`
(`lib.sh:99`) now appends one JSONL record per accepted edge to
`.claude/logs/plan-transitions.jsonl`, and `review/transitions.py` reads it back as the §13
metrics.

Three properties, each a way the count could have lied:

| Property | Why it matters |
|---|---|
| Accepted edges recorded | otherwise the count undercounts |
| **Rejected** edges not recorded | a blocked write never landed; counting attempts inflates the number the ledger exists to measure |
| Non-transition writes not recorded | most writes to a plan doc are prose edits; recording them buries the traversals in noise |

**Two defects found and fixed while verifying.** Neither was visible from the code alone:

1. **The test suite was writing into the real ledger.** `_HOOK_LOG_DIR` resolves through
   `git rev-parse` from the *cwd*, not from the doc under validation, so every hook-test run
   appended five synthetic edges to the operator's measurement file. D10 counts human
   decisions; a count a test suite can increment measures the test suite. Fixed with
   `GALACTUS_TRANSITION_LOG`, which the harness now exports to its temp dir.
2. **The ledger held 18 records and not one was real** — 15 test fixtures plus 3 from a
   `zz-step4-proof.md` manual proof. Truncated to zero (backup outside the repo), so the
   ledger now starts from an honest baseline with the mechanism proven by *assertion*
   rather than by leftover fixture data.

That second point is what makes the zero meaningful. Before it, "no loop-backs observed"
was ambiguous between *rare* and *nothing records it* — the exact ambiguity §7 names as the
one thing HITL cannot paper over. It now means what it says.

Verified: hook suite **88 → 94** passed / 0 failed (6 new ledger assertions, including the
`EXECUTED → PLANNED` loop-back itself); review suite **142 → 153** passed / 0 failed; ruff
clean; `transition-metrics` exits 1 on an absent ledger and 0 with `loop_backs: 0` on an
empty one.

**What the ledger cannot answer, stated rather than estimated.** §13 lists four quantities
and the ledger supplies two. `tokens_per_cycle` and `latency_per_cycle` need an instrumented
dispatch — ledger timestamps span operator think-time, so an inter-edge delta measures the
human, not the cycle. `human_interventions` is not yet *distinguishable*, because every edge
in the ledger is currently written by a human-invoked skill; the count equals the transition
count until a driver writes some of them. All three are named in every
`transition-metrics` payload rather than omitted, and a test asserts they stay named — a
metrics payload silent about its own gaps reads as complete.

### Roadmap step 5 — the graph decision: **DEFERRED, and the deferral is now a measurement**

Step 5 is *"then decide on the graph, for BUILD only, with the pass rate and traversal count
that steps 2–4 produce."* Steps 2–4 are done; the quantities they produce are `runs = 0,
loop_backs = 0` as of 2026-08-14, because the ledger began today.

**The decision is not made, and making it now would be exactly the error this design was
built to prevent.** §13's trigger for the topology row is `P(re-plan)` and `cost(re-plan)`
*existing*, not being zero; §3d puts the graph at ~3× tokens per cycle, breaking even near a
50% per-cycle pass rate. Deciding from an empty ledger would be choosing an architecture
from a number the pipeline has not yet produced — judgment dressed as evidence, which is
what step 4 exists to replace.

What changed today is nonetheless real: **the deferral moved from unfalsifiable to
instrumented.** Before, D10 had zero observed traversals and no mechanism could have
observed one. Now the mechanism exists, is asserted by test, and is recording. The
difference between "we do not know" and "we have not measured yet" is the whole point.

**The decision criterion, fixed in advance** — written now so the verdict is not chosen
retroactively once the numbers arrive:

| Observation | Verdict |
|---|---|
| `loop_backs_per_run` ≥ ~0.5 over ≥ 5 real BUILD runs | build the graph for BUILD (§3b) — loop-backs are common enough that the 3× cost pays back |
| `loop_backs_per_run` < ~0.2 over ≥ 5 real BUILD runs | keep 3a permanently; the graph's motivating edge is rare, and the routing skill is sufficient |
| Between those, or fewer than 5 runs | keep measuring; do not decide |

Five runs is the minimum at which unanimity stops being an accident of small numbers — the
same weakness the research flagged in its own 11-doc corpus (Assumption 3, Confidence:
Medium). The rate threshold is set from §3d's break-even, not from taste.

**Next action is not a build.** It is to run real work items through the pipeline — the
customer-segmentation POC the Goal names — and re-read `transition-metrics` at 5 runs.
`cost(re-plan)` still needs one measured cycle (§9), and nothing in the ledger will supply
it; that is its own instrumentation task, and it gates the same decision.

#### Measurement 1 of 5 — 2026-08-14

The customer-segmentation POC ran end to end through BUILD
(`2026-08-14-gal-17-customer-segmentation.md`, issue #17). **The decision remains
deferred**, per the third row of the table above: 1 real run is fewer than 5.

```
transitions: 10   runs_started: 3   runs_completed: 2
loop_backs: 0     loop_backs_per_run: 0.0
```

**Real-run count: 1, not 3.** The ledger's `runs_started: 3` counts distinct docs, and two
of them (`orchestrator-design`, `track-routing`) are this tooling's own meta-work — the
ledger instrumenting itself while being built. Counting them would repeat in miniature the
error step 4 fixed by truncating the test fixtures: a measurement contaminated by the
apparatus. The operator confirmed this reading on 2026-08-14. **4 more real runs to go.**

The GAL-17 run contributed the first complete traversal the ledger has ever held — all
seven forward edges, `RESEARCH → RESEARCHED → PLANNED → REFINED → READY → IN_PROGRESS →
EXECUTED → COMPLETE`. The prior two docs contributed only fragments (`READY →
IN_PROGRESS`, `EXECUTED → COMPLETE`), which is itself why `runs_completed` (2) exceeded the
number of docs that had actually been through the pipeline.

**Zero loop-backs in run 1, and the zero is now meaningful in a way it was not.** No
`EXECUTED → PLANNED` edge was traversed: the plan survived execution without re-planning.
Worth stating precisely, because this run had a live opportunity to loop back and did not
take it — the `fog-advisor` pass raised six findings, two rated fatal, and all six were
absorbed at `PLANNED → REFINED` rather than after execution. **That is evidence for 3a, not
merely absence of evidence for 3b**: the refine gate caught what would otherwise have
become a post-execution re-plan. One run cannot distinguish "the gate works" from "this
plan was lucky", which is exactly why the threshold is 5.

**A caveat that belongs in the record.** The hook did not fire on this session's `Write`/
`Edit` calls, though it is correctly registered in `.claude/settings.json` and fires
correctly when invoked directly. All seven edges were recorded by invoking
`plan_status_validate.sh` explicitly with the same stdin payload the harness supplies, so
the ledger content is accurate — but it was not *automatically* captured. Until that is
diagnosed (issue filed separately), the ledger under-counts by however many transitions
happen in sessions where the hook is silent, and a low `loop_backs` reading could reflect
missed edges rather than absent ones. **The step-4 property "accepted edges are recorded"
is currently guaranteed by the writer's diligence, not by the mechanism** — which is the
precise ambiguity §7 says HITL cannot paper over, reappearing one level up.
