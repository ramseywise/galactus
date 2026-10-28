# Pipeline orchestration — loops, graphs, and the deterministic spine

Status: PLANNED
Track: agent
Issue: #4 (phase 3, follow-on)
Branch: TBD

## Purpose

The four bands are now wired (`CLAUDE.md` routing table, 2026-08-14) but the pipeline is
**typed, not orchestrated**: a human runs `/proto-research`, reads the output, decides it
is good, and types `/proto-plan`. Every transition is a human decision, every loop-back is
a human noticing. This doc asks what should become a graph, what should stay typed, and
what the deterministic layer under it looks like.

Opened as the follow-on to the flat-skill cleanup, deliberately **not** folded into it —
that was a naming and reachability change; this is an architecture change.

---

## The question

**Which parts of the pipeline are a graph, and which are a conversation?**

The temptation is to make the whole thing a graph — one driver that runs
scope → design → research → plan → refine → execute → review with automatic loop-backs.
That is probably wrong, and the reason is already written down in this repo:
`/proto-plan`'s goal-elicitation step exists because *"a task description is not a goal"*
and the goal is *"the one thing you can never infer from the codebase."* A graph that
routes around the human at that seam produces a confident plan for the wrong goal.

So the real question is narrower: **where is the human load-bearing, and where are they
just a message bus?**

---

## What already works — the precedent

REVIEW is the one band that is genuinely orchestrated, and it is worth copying rather
than reinventing:

- **One generic agent, N swappable remits.** `.claude/agents/review.md` loads exactly one
  `review-*` dimension per dispatch, all dispatched in a single message so they run in
  parallel and the fan-in waits for all of them.
- **A deterministic spine in Python.** `review/` is not advisory prose — `signals.py`
  decides which dimensions activate, `validate.py` accepts or rejects findings against the
  schema, `verdict.py` computes the merge decision. `cli.py` exposes four subcommands,
  stdlib only, JSON in / JSON out / exit code.
- **The ID prefix proves which skill loaded.** One dimension per dispatch, because a
  dispatch carrying two has no unambiguous prefix — the mechanism is what makes the
  fan-out auditable rather than merely parallel.

That is the shape: **the model does judgment, Python does bookkeeping, and the contract
between them is a validated schema.** 88 tests currently pass against it.

## What does not exist

- **No driver above REVIEW.** Nothing sequences the bands. `Status:` is validated by a
  hook (`plan_status_validate.sh`) but nothing *advances* it except a skill choosing to.
- **No loop-back edges.** When `/proto-review` returns blockers, the human reads them and
  decides whether to re-run `/proto-plan`. That edge is real and traversed often; it is
  just not written down anywhere.
- **No FRAME/BUILD seam.** `/proto-design` writes a spec, `/proto-research` reads it, and
  nothing checks that the spec it reads is the spec that was written.
- **CROSS is reachable but unscheduled.** `disable-model-invocation` was dropped from all
  three (2026-08-14) so the model *can* reach them, but nothing suggests when. The
  hypothesis that they get invoked is exactly what the replacement ledger row measures.

---

## Research questions

1. **Which edges are conditional, and on what?** REVIEW → PLAN on blockers is the obvious
   one. Are there others — RESEARCH → SCOPE when research finds the requirement itself is
   unspecified (already written into `proto-research`'s exit as a human instruction)?
2. **What is the loop-termination rule?** A review → fix → review cycle needs a stopping
   condition or it runs forever on a finding nobody can fix. Guacamayo's driver has one;
   check whether it generalizes.
3. **Does `Status:` become the graph state, or does the graph need its own?** `Status:` is
   linear (`RESEARCH → … → COMPLETE`) and a graph with loop-backs is not. Either `Status:`
   gains states, or it stays a human-readable summary of a richer machine state.
4. **What does the driver own vs. the skill?** Guacamayo's `review/driver.py` has a
   hardcoded 5-reporter registry that already disagrees with galactus's 13 dimensions.
   That divergence is the warning: a driver that hardcodes the thing it orchestrates has to
   be edited every time a dimension is added. `signals.py`'s `active_dimensions()` is the
   better pattern — derive, don't enumerate.
5. **Where must the human stay?** Candidate answers: goal elicitation (`proto-plan`),
   the `READY` gate (`proto-refine` is the only writer), track ambiguity
   (`proto-research` asks rather than defaults), and the merge decision. Each of these is
   a place where being wrong is expensive and being slow is cheap.
6. **Does BUILD want worktree isolation?** `proto-review` already flags `worktree-agent-*`
   branches as blockers, so the convention exists and is enforced. Whether execute should
   *use* it is open.

## Prior art to read

- `review/signals.py` — `active_dimensions()`, `detect_track()`, and the injection scan
- `review/verdict.py` — `compute_verdict()`, the merge ladder
- `.claude/agents/review.md` — the generic-agent-plus-remit pattern
- `.claude/skills/proto-review/SKILL.md` §Stage 3 — parallel dispatch and its rules
- `guacamayo/review/driver.py` — the 5-reporter registry, as a counter-example
- `.claude/specs/agent-architecture.md` §Graph, `agent-uncertainty.md` — abstention and
  reversibility, which is what a loop-back edge is

## Out of scope

- Changing any `review-*` dimension's content
- The `proto-*` / `review-*` naming (settled 2026-08-14)
- Guacamayo's driver — that repo owns production review; this is prototyping

## Open decisions

**D1 — Does orchestration ship as a Python driver, a skill that dispatches, or both?**
REVIEW is currently the second (a skill dispatching agents) resting on the first (Python
deciding what is active). The default assumption is that the same split holds for the
whole pipeline, but it is an assumption.

**D2 — Is the graph a real executable, or a documented contract?** A written-down state
machine that humans follow is cheaper and may be sufficient. The measurable claim for
building it is that automatic loop-backs catch transitions humans currently skip — that
claim needs evidence before the build, not after.

---

## Research

### Summary

The pipeline's real defect is not the missing loop-back edges the doc opens with — it is
that **the state machine's tail is unreachable**. `COMPLETE` and `SUPERSEDED` have no
writer in any skill, `RESEARCHED` is read but never written, and the corpus confirms the
consequence: 6 of 6 docs that reached `EXECUTED` are stuck at `Review: pending`, and not
one has ever reached `COMPLETE`. That is the evidence D2 asked for, and it points at a
much smaller build than a graph — the skipped transition is a *terminal* one, where no
loop-back would have helped.

Q2 and Q4 turn out to be already-answered rather than open. The loop-termination rule
exists in two places (`proto-review` §F6's bounded corrective round, guacamayo's one-repair
round-trip) and generalizes as *bounded attempts, then record the failure as a typed
result*. Q4's premise is stale: guacamayo's registry is now 11 dimensions, not 5, and
matches galactus's set almost exactly — the divergence the doc treats as a warning has
already closed.

### Scope

**Investigated**: the deterministic spine (`review/` — 1,173 lines, 92 tests passing); the
`Status:` state machine as written in `plan_status_validate.sh` versus as actually written
by the seven `proto-*` skills; the 11-doc plan corpus as the empirical record; the
dispatch/fan-in pattern in `.claude/agents/review.md` and `proto-review` §Stage 3–6;
guacamayo's `review/driver.py` as the named counter-example; `agent-architecture.md`
§Graph and `agent-uncertainty.md` on abstention and reversibility.

**Out of scope** (per the doc, honored): `review-*` dimension content, the `proto-*` /
`review-*` naming, guacamayo's production driver. **Also not investigated**: token cost of
an orchestrated pipeline versus the typed one — the 3× graph-versus-loop figure below is
cited from the spec, not measured here.

### Findings

#### F1 — The state machine has three unreachable states. **Confidence: High**

`plan_status_validate.sh:19-22` enumerates nine states. Mapping each to the skill that
writes it:

| State | Written by | Status |
|---|---|---|
| `RESEARCH` | *(hand-authored at doc creation)* | reachable |
| `RESEARCHED` | **nothing** — only read, at `proto-refine/SKILL.md:29` | **dead** |
| `PLANNED` | `proto-research/SKILL.md:110`, `proto-plan/SKILL.md:139` | reachable |
| `REFINED` | `proto-refine/SKILL.md:115` | reachable |
| `READY` | `proto-refine/SKILL.md:114` | reachable |
| `IN_PROGRESS` | `proto-execute/SKILL.md:29` | reachable |
| `EXECUTED` | `proto-review/SKILL.md:371` | reachable |
| `COMPLETE` | **nothing** | **dead** |
| `SUPERSEDED` | **nothing** | **dead** |

`RESEARCHED` is skipped structurally: this very skill writes `Status: PLANNED` at the end
of research (`proto-research/SKILL.md:110`), so the state between research and planning
can never be occupied. The hook validates a vocabulary three words larger than the
pipeline speaks.

#### F2 — The corpus proves the pipeline is abandoned at the tail, not mid-loop. **Confidence: High**

Every doc in `.claude/docs/plans/` (11 docs, `Status:` line each):

| State | Count | Docs |
|---|---|---|
| `EXECUTED` + `Review: pending` | 6 | review-sweep, prototyping-review-subsystem, voice-capability-parity, review-leakage-unknown-verdict, context-engineering-space, track-routing |
| `REFINED` | 2 | gal-4-phase2, gal-4-phase3 |
| `IN_PROGRESS` | 1 | ml-capability-parity |
| `PLANNED` | 1 | gal-4-phase4 |
| `RESEARCH` | 1 | this doc |
| `COMPLETE` | **0** | — |

`Review: pending` is the hook-required field for `EXECUTED`
(`plan_status_validate.sh:87-88`), and it is `pending` on all six. The hook forces the
field to exist and then never checks that it ever flips. This is the single most
consistent behavior in the corpus — a 6/6 skip rate at exactly the transition with no
automation.

#### F3 — The loop-termination rule already exists, twice, and generalizes. **Confidence: High**

Q2 is answered by precedent, not by design work. Two independent implementations agree on
the shape:

| Site | Bound | On exhaustion |
|---|---|---|
| `proto-review/SKILL.md:182-186` | validation failures: re-dispatch **once** | record dimension `failed` with reason |
| `proto-review/SKILL.md:195-199` (F6) | corrective round: **at most once, never re-entered** | record in §11 that it ran |
| `guacamayo/review/driver.py:391` | "one repair attempt per dimension" | `ScanError`, driver handles |

The generalizable rule: **bound the attempts, then convert exhaustion into a typed result
rather than another attempt.** `proto-review:199` states the reason directly — *"An
unbounded 'one more look' loop is how a review stops terminating."* This composes with
`agent-uncertainty.md:77-79`, which insists a dispatch failure is never the same as an
abstention: exhaustion must be recorded as a distinct state, not as a clean pass.

#### F4 — Q4's counter-example is stale; the divergence has closed. **Confidence: High**

The doc warns that guacamayo's driver "has a hardcoded 5-reporter registry that already
disagrees with galactus's 13 dimensions." Both numbers are wrong now.

- `guacamayo/review/driver.py:118-130` and `:147-159` register **11**: correctness,
  intent, architecture, safety, contracts, testing, runtime, safeguards, silent-failure,
  leakage, wander.
- Galactus registers **11** in `review/models.py:101` (`REPORTER_ID_PREFIX`), described in
  `review/signals.py:5` as "the eleven dimensions." The 40 `review-*` directory count is
  skill files, not registered dimensions.

The sets differ by one on each side (guacamayo has `wander`; galactus has `performance`).
The warning the doc draws from this — *derive, don't enumerate* — remains correct as a
principle, but it is no longer supported by an active divergence, and guacamayo's registry
is still a hardcoded dict. `signals.py:433-440` is the stronger pattern and enforces it:
`active_dimensions` raises `AssertionError` when the active∪skipped set does not exactly
equal the registered set, so a dimension added to the enum but forgotten in dispatch fails
loudly instead of vanishing.

#### F5 — Every `Status:` write is an unverified self-report. **Confidence: High**

The hook validates *vocabulary*, never *transitions*. `plan_status_validate.sh` checks
that the token is one of nine and that `EXECUTED`/`SUPERSEDED` carry a companion field. It
never reads the previous value, so `RESEARCH → COMPLETE` in one Edit passes. Combined with
F1, the state machine described in `CLAUDE.md` as "a state machine, not a label" is
enforced as a spellchecker.

`proto-refine` is the one place with real gate discipline —
`proto-refine/SKILL.md:123-126` refuses to advance on NOT-READY *even when the user asks* —
but that discipline is prose in a skill, the weakest layer available by galactus's own
ladder (`CLAUDE.md`: hook > linter > test > instruction).

#### F6 — Plan docs are git-ignored globally, so the bus has no history. **Confidence: High**

`git check-ignore -v` resolves to `~/.gitignore_global:1: .claude/docs/*`. All 11 plan
docs are untracked; `git log -- .claude/docs/plans/` returns 0 commits. Consequences:

- The `Status:` history that a graph would treat as its transition log **does not exist**
  and cannot be reconstructed. Any driver wanting durable state must create its own store.
- It is a *global* ignore, so this holds in every repo, not just galactus — guacamayo's
  `CLAUDE.md` documents the same fact and works around it with a committed `queue.md`.
- The measurable claim in D2 can only ever be measured going forward.

#### F7 — The specs answer Q6 and constrain Q1 directly. **Confidence: High**

`agent-architecture.md` supplies three tests the doc's own questions turn on:

- **`:44`** — *"if you cannot name every node before the run starts, you want a harness
  with a good loop, not a graph."* The BUILD band's nodes are nameable and fixed
  (research → plan → refine → execute → review); FRAME's are explicitly not
  (`CLAUDE.md`: "FRAME is a band, not a sequence"). That splits Q1 cleanly.
- **`:105`** — human-in-the-loop is *"a first-class graph primitive, not a UI feature"*,
  requiring stateful persistence across the pause, *"a capability loops alone cannot
  provide, because a loop that pauses has nowhere to put its stack."* Every seam Q5 names
  is such a pause. Against F6, there is currently nowhere to put the stack.
- **`:214`** — graphs cost *"roughly 3× the tokens per cycle"* versus a loop and break
  even near a 50% per-cycle pass rate.

On Q6 (worktree isolation for BUILD), `agent-uncertainty.md:96` is decisive: irreversible
external action requires human approval before execution. A worktree makes execute
reversible, which by `:134` — *"is this decision cheap to reverse? If yes, make it and
move on"* — is what would license removing a human checkpoint. Isolation buys autonomy;
that is its argument, not tidiness.

#### F8 — Two artifacts drift from the code they describe. **Confidence: High**

- This plan doc says "88 tests currently pass"; `uv run pytest review/tests -q` reports
  **92 passed**.
- `review/signals.py:5` says "which of the eleven dimensions run" while `_ALWAYS_ON`
  (`:188-196`) lists 7 and the conditionals add 4 — consistent at 11, but `review/cli.py:9`
  advertises **three** subcommands in its docstring and then defines **four**
  (`validate-finding`, `detect-signals`, `detect-track`, `verdict`); `proto-review:286`
  says "All eleven dimensions get a row." The `detect-track` subcommand was added without
  updating the module docstring's count.

Both are cosmetic individually. Together they are the argument for deriving counts rather
than writing them down — the same argument as F4.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `review/signals.py` `active_dimensions()` | **REUSE** | n/a | The derive-don't-enumerate pattern the doc names as the target, already enforcing completeness by assertion (`:433-440`). Generalizes to phase dispatch unchanged |
| `review/verdict.py` `compute_verdict()` | **REUSE** | n/a | Pure function, no I/O, 53 lines, testable. The exact shape a transition-decision function should take |
| `review/cli.py` | **ADAPT** | n/a | JSON-in/JSON-out/exit-code contract is right; a `next-phase` subcommand fits beside the existing four. Docstring count needs fixing either way (F8) |
| `.claude/agents/review.md` | **REUSE** | n/a | One generic agent + N swappable remits, proven across 11 dimensions. Nothing about it is review-specific except the remit list |
| `proto-review` §F6 bounded round | **REUSE** | n/a | The loop-termination rule Q2 asks for, already written and reasoned (F3) |
| `plan_status_validate.sh` | **ADAPT** | The tolerant `Status:`/`Track:` regex (`:30`, `:48`) is reusable verbatim | Validates vocabulary, not transitions (F5); has no access to the prior value. Extending it to check transitions requires reading git history, which F6 shows does not exist |
| `guacamayo/review/driver.py` | **SKIP** | **Yes — two parts.** (1) The one-repair round-trip at `:391` is the termination precedent, worth copying as a rule not as code. (2) `_DIMENSION_TO_AGENT_FILE`/`_DIMENSION_TO_REPORTER` are worth reading as the negative example of enumeration | 836 lines coupled to guacamayo's SDK driver, JSONL findings store, and a hardcoded home-directory path (`:162-164`). Out of scope by the doc's own boundary |
| `Status:` line as graph state | **ADAPT** | Keep as the human-readable projection | Linear by construction; cannot express loop-backs (Q3). See Q3 below |
| Plan doc as the phase bus | **ADAPT** | Content works; durability does not | Git-ignored (F6) — no transition history, no crash recovery |

### Assumptions

- **Assumption:** The 6/6 `Review: pending` rate reflects a real workflow skip rather than
  a stale convention nobody uses anymore — **Evidence:** the two most recent docs
  (`context-engineering-space`, `track-routing`, both 2026-08-14) carry it, so the field is
  live, not legacy — **If wrong:** F2's headline evidence weakens to "a field nobody
  maintains," and D2 loses its empirical support — **Confidence:** Medium-High
- **Assumption:** `RESEARCHED` and `COMPLETE` are dead by omission rather than by
  deliberate reservation for a future phase — **Evidence:** `proto-refine:29` reads
  `RESEARCHED` as a live state to branch on, which is not how a reserved token behaves —
  **If wrong:** F1 is a smaller finding (two placeholders, one skipped state) —
  **Confidence:** Medium
- **Assumption:** The plan corpus (11 docs, ~5 weeks) is large enough to read a skip rate
  from — **Evidence:** unanimity (6/6, 0 `COMPLETE`) rather than a majority —
  **If wrong:** the rate is noise and D2 needs instrumentation before a build —
  **Confidence:** Medium
- **Assumption:** Token cost of orchestration is bounded by the spec's 3× graph-versus-loop
  figure — **Evidence:** `agent-architecture.md:214`, a cited external figure —
  **If wrong:** an orchestrated pipeline is materially more expensive than the typed one
  and D1's answer shifts toward the cheaper documented contract — **Confidence:** Low.
  Not measured here.

### Disconfirming Evidence

- **Against F1 (dead states):** *Are they written outside the `proto-*` skills — by a
  hook, an agent, or CROSS?* Looked: grepped `COMPLETE`/`SUPERSEDED`/`RESEARCHED` across
  all `proto-*/SKILL.md`, `.claude/agents/*.md`, and `.claude/hooks/`. The only hit
  outside the hook's own enum is `proto-refine:29` reading `RESEARCHED`. **Finding holds.**
  Note the hook *requires* `Superseded-by:` for `SUPERSEDED` — someone designed the state
  fully, then no skill claimed it.
- **Against F2 (tail abandonment):** *Is the skip explained by those docs being genuinely
  incomplete rather than un-transitioned?* Partially. `ml-capability-parity` at
  `IN_PROGRESS` is honest in-flight work. But `EXECUTED` is written by `proto-review`
  *after* the review runs, so a doc at `EXECUTED` + `Review: pending` has had its review —
  the field simply was not updated. **Finding holds for the 6.**
- **Against F3 (rule generalizes):** *Does review's bound work for a phase loop, where a
  retry is a full re-plan rather than a re-dispatch?* Weakly checked. Cost asymmetry is
  large — one re-dispatch is cheap, one re-plan is a session — so the *bound* generalizes
  but its *value* probably should not be 1. **Finding holds with that caveat.**
- **Against F4 (divergence closed):** *Is `driver.py` the live registry, or is a second
  one elsewhere?* Grepped `review/*.py` in guacamayo; `_DIMENSION_TO_REPORTER` at `:147`
  is the only registry, 11 entries. **Finding holds.** Not checked: whether guacamayo's
  `.claude/agents/` actually contains all 11 files the map names.
- **Against F5 (unverified self-report):** *Does another layer verify transitions —
  `task_complete_check.sh`, or a PreToolUse hook?* Listed all 11 hooks;
  `plan_status_validate.sh` is the only one matching `.claude/docs/plans/`
  (`:10`). **Finding holds.**
- **Against F6 (no history):** *Is there a repo-local override un-ignoring the plans?*
  Checked galactus `.gitignore` — it names `.claude/docs/review-findings.jsonl` but never
  re-includes `.claude/docs/`. `git status --ignored` confirms `!! .claude/docs/`.
  **Finding holds.**
- **Against the whole framing:** *Is the pipeline actually working fine, making this
  premature?* This is the strongest counter-argument and it partly succeeds. Seven skills,
  92 passing tests, and a corpus of completed work exist — the typed pipeline demonstrably
  produces output. What it does not do is *record* completion (F2). That reframes the
  build from "orchestrate the pipeline" to "close the ledger," which is a much smaller
  claim than the doc opens with.

### Key Unknowns

- **Whether an automated loop-back would have been traversed even once.** F2 shows a
  skipped *terminal* transition, not a skipped loop-back. No doc in the corpus shows
  REVIEW → PLAN re-entry, so the doc's motivating edge has zero observed traversals — it
  may be rare rather than merely unrecorded, and F6 means the absence is not decisive.
  **This is the gap D2 names, and it remains open.**
- **Where transition state would live.** F6 rules out git history and the plan doc.
  Untested candidates: a committed ledger (guacamayo's `queue.md` pattern), a sidecar
  under a non-ignored path, or re-including `.claude/docs/plans/` in galactus's
  `.gitignore` — which is a workspace-wide convention change, not a galactus decision.
- **The real cost of a re-plan cycle.** F3 gives the bound's shape but not its value; a
  bound of 1 on re-planning may be too tight and 3 may be unaffordable. Needs one measured
  cycle.
- **Whether CROSS skills are being invoked at all.** `.claude/docs/decisions/` does not
  exist, which is consistent with zero invocations since `disable-model-invocation` was
  dropped on 2026-08-14 — but the directory would also be absent on day one of a working
  system. Two days of data, no signal either way.
- **Q1's other conditional edges.** Only RESEARCH → SCOPE (already written as a human
  instruction in `proto-research`'s exit) and REVIEW → PLAN were found. Whether others
  exist was not established — the corpus records states, not the paths between them.

### Recommendation

The research does not support building the graph the doc opens with, and it does support a
much smaller intervention that the doc did not anticipate. The measurable failure in the
corpus is unanimous and terminal: nothing ever reaches `COMPLETE`, because nothing can —
three states have no writer (F1), and the one transition humans demonstrably skip 6 times
out of 6 is the last one (F2), where a loop-back edge would not have helped. Closing that
ledger is a state-writer and hook-transition change, not an orchestrator.

The graph question then narrows usefully. BUILD's nodes are nameable in advance and FRAME's
are not, which by `agent-architecture.md:44` makes BUILD the only band that qualifies at
all — and BUILD is also where the human seams Q5 names are load-bearing, each one a pause
that needs somewhere to put its stack (`:105`) and currently has nowhere (F6). So the
sequencing that falls out is: make the state machine honest first, give transitions a
durable home second, and only then ask whether the edges between them want automating —
by which point the loop-back traversal count that D2 wants will exist, instead of being
unmeasurable as it is today. Q2 and Q4 can be closed on precedent now (F3, F4): the
termination rule is written twice already, and the divergence the doc treats as a warning
has closed on its own.
