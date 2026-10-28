# GAL-27 — Band contract, HITL gates, and Workflow dispatch for the fast loop

Date: 2026-08-15
Status: REFINED
From: PLANNED
Track: agent
Issue: #27
Branch: GAL-27-band-contract-hitl-gates
Epistemic: CONFLICTED
Epistemic-by: fog-advisor
Epistemic-at: 2026-08-15
Epistemic-findings: 6

Reads: `.claude/docs/plans/2026-08-15-fast-loop-borrowables.md` (`Status: RESEARCH`) —
the research this plan executes. Also `2026-08-14-orchestrator-design.md` (#13,
`EXECUTED`) §1 decision-seat table, §3b-bis re-hydration, §3c graph-vs-loop; and
`2026-08-15-gal-23-hitl-gradient.md` (`Status: REFINED`), the downstream consumer.

## Plan
Date: 2026-08-15
Based on: the research doc, the control-plane design, and direct verification of the
hooks, settings registration, and skill frontmatter (2026-08-15, recorded below).

### Goal

Ship the **mechanism** a four-band fast loop needs: a band contract that sits over
`Status:`, per-band release checklists evaluated by audit rather than assertion, a
propose-and-confirm triage intake, and a dispatcher that routes between bands stopping
only at confirmation points.

The deliverable is the mechanism, not the measurement. #23 consumes it (its L4 arm is
blocked on the dispatcher); this plan does not run the gradient.

---

### Verification done at planning time — two of the issue's decisions do not survive

The issue records D1–D5 as settled and asks that they be honored. Two rest on premises
that are false in the repo as it stands on 2026-08-15. Both were checked directly, and
both are recorded here rather than built on, because the plan they imply would not work.

#### V1 — SUPERSEDED 2026-08-15 (re-verified later the same day): the parity gap was repaired

**The finding below was true when written (~14:58) and is false now.** Re-verified after
the global hook tree was updated at 20:13:

| File | Repo `.claude/hooks/` | Global `~/.claude/hooks/` | Result |
|---|---|---|---|
| `plan_status_validate.sh` | 14839 bytes | 14839 bytes | **`cmp` clean** |
| `plan_transition_validate.sh` | 9926 bytes | 9926 bytes | **`cmp` clean** |
| `lib.sh` `log_transition` / `log_recorder_session` | 7 matches | 7 matches | **present in both** |

`CLAUDE.md`'s byte-identical claim is **true as of 2026-08-15 20:13**, not false. The
global tree now carries the richer repo version — the port happened rather than the
divergence being documented.

**Consequences, and they run in both directions:**

- **Step 7 is dropped.** It filed an issue for a defect that no longer exists. Filing it
  now would be filing a fixed bug.
- **Step 5's root assertion is kept, and its justification changes.** It was justified as
  a mitigation for the weak-global-hook risk (R1). That specific risk is gone. The
  assertion survives on a different and more durable rationale: a dispatcher that writes
  `Status:` and depends on the ledger should assert its execution root regardless of
  whether the two trees happen to agree today. Parity is a *fact about right now*, not an
  invariant — nothing enforces it, and it was false eight hours ago. An assertion that
  costs three lines and converts a silent-wrong-hook failure into a loud one is worth
  keeping at that price.
- **R1 is downgraded** from "produces an untraced run that looks clean" to "would do so if
  parity regresses." Still worth the mitigation; no longer an active defect.

The original finding is preserved below because the *reasoning* it drove — D1's
justification being independent of the parity claim — is still what carries the plan.

#### V1 (original, as written ~14:58 — now stale) — The hooks are **not** byte-identical, and the transition hook exists only in the repo

`CLAUDE.md` claims `plan_status_validate.sh`, `plan_transition_validate.sh`, and both test
suites are "in sync as of 2026-08-15; `cmp` is the check." Running that check:

| File | Repo `.claude/hooks/` | Global `~/.claude/hooks/` | Result |
|---|---|---|---|
| `plan_status_validate.sh` | 14839 bytes | present, older | **DIFFER** — ~230 lines of divergence |
| `plan_transition_validate.sh` | present | **absent** | **MISSING** globally |
| `lib.sh` `log_transition` / `log_recorder_session` | present | **absent** (`grep -c` → 0) | **MISSING** globally |

The repo copy is the *richer* one. It alone carries: `unfenced()` fence-stripping, the
`LEGAL_EDGES` table, `From:` validation, `Review:` enum (`pending|passed|failed|blocked`),
`Track:` validation, the `Epistemic:` axis, `COMPLETE` requiring `Review: passed`, and
transition-ledger emission. The global copy has none of it.

**This inverts CLAUDE.md's vendoring note.** That note says repo hooks are "payload that
does not run" because `$CLAUDE_PROJECT_DIR` resolves through the `~/workspace/.claude`
symlink to the operator's global hooks. That is true only for a session rooted at
`~/workspace`. Verified: `~/workspace/galactus/.claude/hooks/` is a **real directory, not
a symlink** (`realpath` returns itself), so a session rooted at `~/workspace/galactus`
runs the repo hooks.

Two independent confirmations, both from this session:

1. The transition ledger — `.claude/logs/plan-transitions.jsonl` has 30 entries carrying
   `"observer":1` and `"observed":"verified"`, fields only the repo hook emits.
2. **The first write of this very plan doc was blocked by the repo hook.** It carried
   `From: RESEARCH` on a doc that did not yet exist, and `plan_transition_validate.sh`
   rejected it: *"origin write declares a prior state… there is no state to come from."*
   The global hook tree contains no such file and could not have produced that error.

**Consequence for D1.** D1's stated benefit — "both hooks untouched; CLAUDE.md's
byte-identical parity claim stays intact" — is already void: the parity claim is false
today. D1's *substance* survives and is honored: **this plan changes no hook.** Bands sit
over `Status:`, no state is added, no vocabulary changes, `LEGAL_EDGES` is untouched. What
changes is the justification, not the decision. The parity repair is **out of scope** and
routed to its own issue (Step 7), because fixing it means either porting ~230 lines into
global or accepting a documented divergence — a decision with its own blast radius that
should not ride along inside a band-contract plan.

**Risk this creates for the dispatcher.** A dispatch that runs from `~/workspace` gets the
*weak* hook: no `From:` validation, no legal-edge table, no ledger. The band contract's
auditability depends on the ledger. Step 5 therefore has the dispatcher assert its
execution root and refuse to run from outside the repo, rather than silently producing
unrecorded transitions. This is the same class of failure that already bit #23 — its
`Epistemic-by:` line records `fog-advisor` failing to load because "the session is rooted
at `~/workspace`, not `~/workspace/galactus`."

#### V2 — `disable-model-invocation: true` blocks the dispatcher, it does not merely constrain it

D2 says "the script dispatches, the model does not self-trigger," treating the seven flags
as compatible with `Workflow` orchestration. The repo's own documentation says otherwise
(`.claude/skills/skill-creator/references/gotchas.md:32-38`, and the field table at `:207`):

> `disable-model-invocation: true` — "This field doesn't just prevent auto-invocation - it
> removes the description from Claude's system prompt entirely. Claude literally cannot see
> the skill exists unless the user types `/skill-name`."

A `Workflow` script dispatches **subagents** — model instances. A subagent told "run
`/proto-research`" cannot see that skill for the same reason the main loop cannot. The flag
is not a politeness convention the dispatcher routes around; it removes the skill from the
context of every model instance, including the ones the dispatcher spawns.

So D2 as written is not implementable: "keep all seven flags set" and "a `Workflow` script
dispatches the bands" are mutually exclusive **if dispatch means invoking the skills by
name**. D2's intent — the model must not self-trigger the pipeline — is sound and is
preserved. The resolution is to change what dispatch *means*, not to unset the flags:

**Flag distribution, verified 2026-08-15 (refine pass).** The "seven flags" are spread
unevenly across the pipeline, and Step 5 must not assume uniformity:

| Skill | `disable-model-invocation` |
|---|---|
| `proto-research`, `proto-plan`, `proto-refine`, `proto-execute`, `proto-design` | **set** |
| `proto-scope`, `proto-review` | **not set** |

(The other three of the eight repo-wide flags are on `ml-select`, `ml-transform`, and
`prototype-genesis` — not band skills.)

This does not change the dispatch mechanism — carrying bodies works uniformly and is still
the right choice — but it corrects a premise. Two band skills *are* model-reachable today,
so "the flags are what stop self-triggering" is only true of five of the seven. If D2's
intent (no self-triggering of the pipeline) is to hold for the whole band chain, that gap
is real and is **noted, not closed here**: closing it means *setting* flags on two skills,
which is a frontmatter change this plan's non-goals forbid. Recorded for a follow-up.

**The dispatcher carries the skill bodies, it does not invoke the skills.** `SKILL.md`
bodies are plain markdown, readable with `Read`. A workflow agent is given the body as its
instructions. This preserves every property D2 wanted:

- the flags stay set (D2 honored literally — Step 5 changes no frontmatter);
- the model still cannot reach these skills on its own, in any session;
- dispatch happens only when the operator explicitly starts the workflow.

It costs one real thing, stated plainly: the dispatched agent runs a *copy* of the skill
body, so a skill edited after the dispatcher is written would drift from what the
dispatcher sends. Step 5 handles this by reading `SKILL.md` at dispatch time rather than
inlining its text — the body is read fresh each run, so drift is impossible.

**Alternative considered and rejected:** unset the flags for the four band skills and let
the dispatcher invoke them by name. Rejected because it makes the whole `proto-*` pipeline
model-reachable in every session, which is exactly the property CLAUDE.md protects when it
says CROSS skills are "the only skills the model may reach for on its own: cheap,
read-only, and never touch `Status:`." The band skills are none of those three.

---

### Open Questions

The issue names three. All three are resolved here; the resolutions are load-bearing and
each carries the evidence it rests on.

**Q1 — Is band 2's non-blocking requirement compatible with HITL at all?**
**Resolved: yes, by hoisting, with one structural carve-out.**

The tension is real: band 2 runs while the operator is in notebooks, `human_approval` may
never be silently derived, and a decision cannot both stop the pipeline and not stop it.
Three options were considered.

| Option | Verdict |
|---|---|
| Async confirmation channel (M1 status contract as a mailbox band 2 polls) | **Rejected for this issue.** A channel the operator is not watching is not a confirmation — it is a timeout with extra steps. Building it means deciding what happens when nobody answers, and every answer to that is either "block" (defeats the band) or "proceed unapproved" (the exact irreversible failure the carve-out forbids) |
| Defer approvals to band 4 | **Rejected.** Band 2 writes artifacts; an approval that arrives after the write approves nothing |
| **Hoist every irreversible decision into band 1** | **Adopted** |

Hoisting works because of the blast-radius rule the research already establishes: *a
default is safe to apply silently in proportion to how cheaply it can be reversed.* Band 2
in this pipeline fits a model, writes under `runs/`, and writes a plan doc. Those are
cheap to reverse — rerun, delete, `git checkout`. They are not `human_approval` territory.

The carve-out, and it is the honest part of this answer: **if band 2 ever needs an
irreversible action, it stops.** Not defers, not proceeds — stops, and the run is recorded
as blocked at that point. The band contract makes this a legible outcome rather than a
crash (Step 2 gives it a checklist item). The 20–30 min budget is not a licence to proceed
unapproved. If stopping proves common in practice, that is the evidence that an async
channel is genuinely needed, and it can be built then against real cases instead of
speculated ones.

**Q2 — What records a backward transition?**
**Resolved: the ledger already does, and the field already exists. Nothing new is built.**

Verified 2026-08-15: `.claude/logs/plan-transitions.jsonl` records every accepted edge as
`{ts, repo, doc, from, to, track, epistemic, observed, observer}`. A live sample:

```
{"ts":"2026-08-15T14:50:23Z","repo":"galactus","doc":"2026-08-15-gal-23-proto-pipeline-dry-run.md","from":"PLANNED","to":"SUPERSEDED","track":"agent","epistemic":"","observed":"verified","observer":1}
```

A backward transition is therefore *already traced* — it is an entry whose `from` is later
in the sequence than its `to`. The research's worry ("a loop that regresses silently
cannot be measured") was about a gap that the #13 work closed after the research was
written. `EXECUTED → PLANNED` is in `LEGAL_EDGES` and is the loop-back edge D10 needs.

What is missing is not the record but a **reader**. Step 6 adds one: a band-aware view over
the existing ledger that classifies each edge as forward, backward, or lateral by band, and
counts loop-backs per run. No hook change, no new field, no new log — a reader over data
already being written. This is the cheapest possible resolution and it is available only
because the ledger landed first.

**Q3 — Where do bands 3 and 4 get their budgets?**
**Resolved: they do not get one. Recorded as a risk, and the plan refuses to invent one.**

No measurement exists in either repo for bands 3 or 4. The research says so; verification
confirms it. The issue's own scope line puts "band 3/4 budget validation" **out**.

The temptation is to write "10–15 min" into the band contract as a budget. This plan does
not, because a target with no measurement behind it, written into a contract, becomes an
estimate the next reader trusts. That is the same failure class as the baseline in
`runs/ml/lending/WALKTHROUGH.md` — a number that was real in one context and got read as
authoritative in another.

**What the contract carries instead:** bands 3 and 4 record `Budget: unmeasured (target
10–15 min, no evidence)` and **emit their elapsed time**. After #23's runs there will be
measurements, and the target can become an estimate with evidence behind it. The
dispatcher timing every band (Step 5) is what makes that data appear as a side effect of
normal use rather than requiring a separate exercise.

Bands 1 and 2 do have evidence and carry it: band 1 at 5–10 min (against the ~2 min
conversational-intake measurement, `archived/design-prototype/SKILL.md:76`); band 2 at
20–30 min **conditional on fold/model capping as a declared default** — the one-hour claim
was tested once and failed (`runs/ml/lending/WALKTHROUGH.md:202-216`), and the mitigation is
the cap, not optimism.

---

### Non-goals

- No hook edits. No new `Status:` state, no vocabulary change, no `LEGAL_EDGES` change (D1).
- No frontmatter change to any skill; the seven `disable-model-invocation` flags stay (D2).
- No copier render, no `design.yaml.jinja`, no `.copier-answers.yml` (D5).
- No vendoring of the `gate-check` skill — the discipline only (D3).
- Not #23's measurement. This ships the mechanism; #23 exercises it.
- Not the hook-parity repair (V1) — **moot as of 2026-08-15 20:13**, repaired outside this
  plan. Step 7 is dropped.

---

### Steps

#### Step 1 — Ratify the band contract as a document

**Files**: `.claude/docs/band-contract.md` (new)

The band → `Status:` mapping from the issue, ratified verbatim, plus what each band owns:

```
Band 1 triage    → RESEARCH, RESEARCHED, PLANNED
Band 2 prototype → REFINED, READY, IN_PROGRESS
Band 3 optimize  → EXECUTED
Band 4 harden    → COMPLETE
```

Bands are a **view**, not a state. The doc states this explicitly: `Status:` remains the
only validated field, the hook is unchanged, and a band is derived by lookup from the
current `Status:`. `SUPERSEDED` belongs to no band — it is an escape from the sequence,
reachable from anywhere, and the contract says so rather than forcing it into band 4.

Records per band: owner skill(s), budget with its evidence (or `unmeasured` per Q3),
whether the band may stop for a human, and its release checklist (Step 2).

**Band 3 has no owner skill — settle this first.** Confirmed 2026-08-15 against CLAUDE.md's
pipeline table: there is no skill between `/proto-execute` (Build, writes `EXECUTED`) and
`/proto-review` (Review). Band 3 maps to `EXECUTED` with nothing owning it, so the verify
below **fails as the mapping stands**. The likely resolution is that band 3's owner is
`/proto-review` and the mapping is redrawn accordingly — but that is Step 1's decision to
make explicitly, not a gap to paper over. A band with no owner cannot have a release
checklist, which makes Steps 2 and 5 unbuildable for it.

**Verify**: every one of the eight non-`SUPERSEDED` states maps to exactly one band; no
state is unmapped; **no band is empty, and every band names an owner skill that exists**.

#### Step 2 — Release checklists, evaluated by audit (D4 + M2)

**Files**: `.claude/docs/band-contract.md` (checklist section)

Each band gets a checklist of expectations that must hold **before** the pipeline proceeds.
Every item is a named artifact check with a named verifier — the *shape* borrowed from the
template's G1/G2 tables, not the rows (which are keyed to template-owned machinery).

Item shape: `id | expectation | verifier (file path or command) | value`, where value is
`true | false | error` (third value added per FA-002 — see the failure pass).

`error` means **the verifier itself could not run** — missing file, failed import, moved
path. It stops for repair and never routes back a band. `false` means the verifier ran and
the expectation did not hold. Collapsing the two, as this step originally did, makes the
"errors and gates route differently" rule below unenforceable by construction: it would be
an instruction contradicted by its own schema, which is the weakest layer of CLAUDE.md's
`hook > linter > test > tool schema > instruction` ladder.

The governing rule, stated at the top of the section and repeated at each gate (M2):

> **Audit, don't assert.** Every item is the result of looking at a real artifact this run.
> If an item cannot be verified, it stays `false` — never true on memory or intent. An
> unreadable or missing artifact is an **error, not a failed gate** (the distinction
> `/proto-refine` already draws at `SKILL.md:28-33`); say which, because they route
> differently — an error stops for repair, a failed gate routes back a band.

Two checklist items are written from the failure instances the research documents, so the
checklist starts with teeth rather than generic rows:

- **Nested-field check.** `runs/ml/fraud/docs/summary.json` nests `operating_point_reported`
  under `refusal` while the plan's precondition table asserts it top-level; a check keyed
  on the flat name reads `None` and evaluates falsy — "no refusal reported." The item
  verifies the field **at its actual path**, and a lookup returning `None` is `false`, never
  a pass.
- **Non-empty `skipped` check.** `"skipped": {"catboost": …}` — a model silently absent from
  the comparison with `beats_baseline` computed over survivors only. The item fails when
  `skipped` is non-empty, because a comparison missing a candidate is not a completed
  comparison.

Band 2's checklist carries the Q1 carve-out as an item: *no irreversible action was taken
without approval* — `false` stops the run rather than deferring.

**Verify** (corrected per FA-005 — the original criterion was unsatisfiable and demanded a
pass on the known-bad artifact). Run both fraud checks against the real `summary.json`. The
measured values, confirmed 2026-08-15:

| Lookup | Value | Item reads |
|---|---|---|
| `d.get('operating_point_reported')` (flat) | `None` — the field is not there | **`error`**, not `false` — an absent field means the verifier looked in the wrong place |
| `d['refusal']['operating_point_reported']` (nested) | `False` | **`false`** — a real boolean, correctly read |
| `d['skipped']` | `{'catboost': …}` non-empty | **`false`** |

The nested-field item is demonstrating **absent versus a real `False`**, not false versus
true. Both readings are `false`-or-worse, and that is the point: the artifact's own
`refusal.reason` says "no operating point is reported," so any item reading `true` here has
been inverted until it passed. A checklist that passes on the known-bad artifact is not a
checklist.

#### Step 3 — Propose-and-confirm intake for triage (M3)

**Files**: `.claude/skills/proto-scope/SKILL.md`

`/proto-scope` currently interviews — open questions, in tiers. Band 1's 5–10 min budget
does not survive 14 blind prompts. The change is the one the genesis lifecycle doc already
worked out and evidenced across three sessions: **confirmations that carry a proposed
answer.** A confirmation costs seconds; an open question costs minutes.

This is a reasoning layer, not a prompt-count optimization — the source doc is explicit
that "shrinking the *asked* set ≠ shrinking the *interviewed* set." Every question is still
*answered*; most are answered by a proposal the operator ratifies or overrides.

The routing rule for which form a question takes is the blast-radius rule: **a default is
safe to apply silently in proportion to how cheaply it can be reversed.** Add a section
stating it, with the carve-out that is not negotiable:

> **Never derive `human_approval`.** A silent default there has an irreversible failure
> mode — an autonomous agent making an external write nobody sanctioned. It is asked, every
> time, regardless of budget.

The skill already has the right precedent to extend rather than invent: Step 0 and Step 0.6
ratify inherited decisions with "your roadmap resolved X — confirm, or reopen?" This
generalizes that from inherited answers to *proposed* ones.

**Verify**: the skill's question inventory splits into asked-open vs. proposed-confirm, the
split is justified by reversibility per question, and `human_approval` is in the asked
column. Re-runnability is preserved (the skill is idempotent over `DESIGN.md` — a later run
must still ratify what is resolved and interview only gaps).

#### Step 4 — Decision records for what triage settles

**Files**: `.claude/docs/decisions/` (shape doc), `.claude/skills/proto-scope/SKILL.md`

Triage's output must be inspectable before anything downstream consumes it — the
answers-file seam the research identifies as salvageable from copier at low cost: **decide
first, render second.**

Each decision triage settles records: the decision, the proposed default, whether the
operator confirmed or overrode, and the reversibility class that determined whether it was
asked at all. That last field is what makes the Step 3 routing auditable rather than
asserted — a decision marked "silently defaulted" carries the claim that it was cheap to
reverse, and that claim is now on the record where a reviewer can dispute it.

`.claude/docs/decisions/` is the CROSS tree, chosen deliberately: it is not guarded by
`plan_status_validate.sh`, so writing there cannot trip the state machine.

**Verify**: a decision record round-trips — written by triage, read by the dispatcher at
band 2 entry, and the reversibility field is populated for every entry.

#### Step 5 — The `Workflow` dispatcher (D2, as resolved in V2)

**Files**: `.claude/workflows/fast-loop.js` (new)

A workflow script with four phases and HITL breakpoints between them.

**Dispatch mechanism** (per V2, **amended per FA-001**): each band's agent prompt is
**composed**, not copied. Three parts, and omitting any one produces an agent that narrates
the procedure instead of running it:

1. the `SKILL.md` body, read from disk at dispatch time (so it cannot drift);
2. an **explicit target substituted for `$ARGUMENTS`** — the runtime does not expand it, and
   every band body reads it (`proto-refine:20`, `proto-execute`, `proto-plan` ×2,
   `proto-research` ×2). A body handed over raw reads a literal unexpanded token, and
   `proto-refine`'s own fallback ("with no argument, use the most recently modified plan
   doc") is a race under concurrent bands;
3. the **tool grant** the body's `allowed-tools` frontmatter declares — read *from* the
   frontmatter, since the runtime does not carry it. `proto-refine` needs
   `Read Grep Glob Bash Edit Agent`; `proto-execute` needs `Read Grep Glob Bash Edit Write`.
   An agent without `Agent` cannot run `proto-refine`'s Stage 3 dispatch and will silently
   skip it.

No skill is invoked by name; no frontmatter changes; the flags stay set.

**Nested dispatch is bounded.** `proto-refine` dispatches `fog-advisor` and `proto-execute`
dispatches worktree agents — both are one level below a band agent that is itself a subagent.
The runtime permits this via `agentType`, and `workflow()` nests exactly one level. Band
agents must therefore be dispatched such that their own dispatches remain legal; if a band
needs two levels, it is dispatched as its own workflow rather than as an agent.

**Execution-root assertion** (per V1, **strengthened per FA-006**), before any dispatch: the
script verifies it is running against `~/workspace/galactus`, that
`.claude/hooks/plan_transition_validate.sh` is the registered `$CLAUDE_PROJECT_DIR` hook,
**and that the hook which will actually run emits transitions** — `grep -q log_transition`
on the resolved path, or read `recorder.attested`, which `review/transitions.py:139-151`
already computes. If any check fails, it **stops**.

The third check is the load-bearing one. A registration check passes against an *older* hook
identically to a current one, which is galactus#20 verbatim — `transitions.py:24` records it
as "two copies of the hook at different vintages both registered, and the one that ran had no
ledger." Parity is repaired today (V1) but nothing enforces it, so the assertion must test
behavior rather than presence. A run from
`~/workspace` gets the weak global hook — no `From:` validation, no ledger — and would
produce a band trace with no recorded transitions, which reads exactly like a clean run.
This is the failure that already hit #23's `fog-advisor` dispatch.

**Breakpoints**: after band 1 (confirm the decision tree) and after band 3, before band 4
(gate confirmation). Bands 2 and 3 run without stopping. Each breakpoint prints the band's
release checklist with per-item evidence, then asks. **Readiness is established first, then
the human is asked** — never asked first. A `false` item blocks; the operator may override,
and the override is recorded as an override rather than as a pass.

**Timing**: every band's elapsed time is recorded (this is what makes Q3 answerable later),
**alongside stopped-vs-completed** (per FA-003). A band that stops on the Q1 carve-out must
never contribute its elapsed time to the budget figure — a 20–30 min number computed over
runs that stopped early reads as evidence the budget holds.

**Serial/parallel**: the "serial by default" rule is scoped to bands 1 and 4 only. It was
written for a watchable recorded exercise where narration was the deliverable; band 2 is the
opposite case, and carrying the rule in unexamined would forbid the parallelism the 20–30
min budget depends on.

**Band 2 declares the cap**: fold and model capping is passed as a **declared default**, not
an available flag — the measured constraint from the lending run. **Per FA-004, the cap is
recorded as a first-class field in the run artifact.** A declared default is invisible by
construction, and a model excluded by the cap may never reach `skipped` at all — it was never
scheduled — so the cap must be legible to the checklist that judges the comparison.

**Verify**, in two stages. The first gates the second:

1. **The one-band test (FA-001, run this before building the rest).** Compose one band's
   prompt per the mechanism above and dispatch it against a real `PLANNED` doc. Diff the
   ledger before and after. **An agent that reports success while the ledger is unchanged is
   the failure this catches** — and an empty ledger looks identical to a band that was
   skipped and one that never ran. If this fails, the finding is not "fix the dispatcher": it
   is that V2's resolution does not resolve D2, and the flags-versus-dispatch contradiction
   is open again.
2. **The four-band run**: dispatches without the operator typing a skill name; the root
   assertion fires when run from `~/workspace` *and* when the resolved hook lacks
   `log_transition`; every breakpoint prints its checklist before asking; the ledger shows
   the run's transitions afterward.

#### Step 6 — The band-aware ledger reader (Q2)

**Files**: `review/transitions.py` (extend), `review/tests/test_transitions.py`

A reader over `.claude/logs/plan-transitions.jsonl` that maps each edge's `from`/`to` to
bands via the Step 1 mapping and classifies it forward / backward / lateral, then counts
loop-backs per run. `review/transitions.py` already exists and is the right home.

No new field, no new log, no hook change — the ledger already records what is needed.

**Verify**: unit tests over synthetic edges — `EXECUTED → PLANNED` classifies backward
(band 3 → band 1); `REFINED → READY` classifies lateral (both band 2); `PLANNED → REFINED`
classifies forward. Run against the real 30-entry ledger and confirm it parses without
error.

#### Step 7 — DROPPED (2026-08-15, re-verification)

The parity defect this step would have filed **was repaired at 20:13 today**, after this
plan was written. See V1's superseding note. `cmp` is clean on both hooks and `lib.sh`
carries the helpers in both trees.

Nothing to file. `CLAUDE.md`'s claim is accurate as written and needs no correction.

The step is left in place rather than deleted so the numbering of Steps 1–6 stays stable
and the reason the step vanished is on the record — a step that silently disappears
between the plan and the execution looks like it was skipped.

---

---

### Failure pass — `fog-advisor`, 2026-08-15

Dispatched on the Full path (Step 5 writes a shared dispatcher and Step 3 edits a shared
skill — blast radius, per `proto-refine/SKILL.md:60-71`). `resolve-capability fog` returned
exit 0; the advisor was given the plan and not the caller's assessment.

Six findings. Four are verified below and change the plan; two are accepted as recorded
risks. The advisor's own three blind spots are closed here where this session could close
them.

**FA-001 — dispatch mechanism (fatal, `likely`). VERIFIED, and Step 5 is amended.**

The advisor's structural claim holds: every band skill body reads `$ARGUMENTS`
(`proto-refine:20`, `proto-execute`, `proto-plan` ×2, `proto-research` ×2), and Step 5 never
says what substitutes for it. Its blind spot — "I could not read the `Workflow` runtime" —
is closed from this session's tool contract:

| Requirement | Runtime answer |
|---|---|
| `$ARGUMENTS` | **Not expanded.** `agent(prompt, opts)` takes a prompt string. The dispatcher must interpolate the target explicitly; a body handed over verbatim reads a literal unexpanded token |
| `allowed-tools` | **Not carried.** The dispatched agent gets the tools the *dispatcher* grants, not the skill's frontmatter |
| Nested dispatch | **Available but bounded** — via `agentType`, and `workflow()` nests exactly one level |

So the mechanism is **repairable, not broken** — but Step 5 as written does not describe a
working dispatcher. The amendment, and it is mandatory before Step 5 is built:

> The dispatcher **composes** each agent prompt: the `SKILL.md` body read fresh at dispatch
> time, plus an explicit target substituted for `$ARGUMENTS`, plus the tool grant the body's
> `allowed-tools` line declares (read from frontmatter, not carried by it). Handing over the
> raw body is not dispatch.

The advisor's proposed check stands as Step 5's **first** acceptance test, before the
four-band run: dispatch one band by hand against a real `PLANNED` doc and diff the ledger.
An agent that reports success while the ledger is unchanged is the failure this catches, and
an empty ledger looks identical to a skipped band.

**FA-005 — Step 2's verify criterion is unsatisfiable (`certain`). VERIFIED; criterion
corrected.**

Run directly against the real artifact:

```
flat:   d.get('operating_point_reported')            → None
nested: d['refusal']['operating_point_reported']     → False
reason: "…no operating point is reported."
```

The nested path yields `False`, not `True` as Step 2 demanded — and `False` is the *correct*
reading, since the artifact genuinely reports no operating point. The criterion asked for the
wrong value, and an executor chasing it would invert the item until the checklist passed on a
known-bad artifact — precisely what Step 2's guard forbids. **Step 2's verify is restated
below**: the item demonstrates *absent* (`None`, flat) versus *a real `False`* (nested), not
false-versus-true.

**FA-002 — `true`/`false` cannot represent a broken verifier (`costly`). ACCEPTED; item
shape amended.**

Step 2 requires errors and failed gates to route differently, then gives every item a
two-element value domain in which both values are gate outcomes. `/proto-refine`, the cited
precedent, has a real third branch (`SKILL.md:24-34`, "Error. Stop."). The rule as written
sits at the weakest layer of CLAUDE.md's own ladder — an instruction contradicted by the
schema one line above it. **Item shape becomes `true | false | error`**, where `error` stops
for repair and never routes back a band.

**FA-006 — the root assertion cannot detect a stale hook (`costly`). ACCEPTED; assertion
strengthened.**

A registration check passes against an *older* hook identically to a current one — which is
the galactus#20 failure verbatim, and `review/transitions.py:24` already names it: "two
copies of the hook at different vintages both registered, and the one that ran had no
ledger." Since parity is not enforced and was false earlier today, Step 5's assertion is
upgraded from "a hook is registered here" to **"the hook that will run emits transitions"** —
`grep -q log_transition` on the resolved path, or read `recorder.attested`, which
`transitions.py:139-151` already computes. One extra line, and it closes the actual failure.

**FA-003 — hoisting may be unachievable (`costly`). ACCEPTED as a recorded risk; R5
amended.**

Band 2 owns `IN_PROGRESS`, so it runs `/proto-execute`, whose body dispatches worktree agents
that **commit** (`SKILL.md:53-60`) — not in Q1's enumerated set of "rerun, delete, `git
checkout`". Q1's resolution survives (the carve-out makes stopping legible), but the advisor
is right that stopping may be the modal case rather than the exception, and that a 20–30 min
budget computed over runs that stopped early reads as evidence the budget holds. **R5 gains
its mitigation**: the dispatcher records stopped-vs-completed alongside elapsed time, so the
budget figure is never computed over a contaminated population.

**FA-004 — the cap changes what the comparison means (`costly`). ACCEPTED; checklist item
widened.**

A model excluded by a declared cap may never appear in `skipped` at all — it was never
scheduled — so the Step 2 item that fails on non-empty `skipped` has a blind spot the cap
itself creates. Verified that `skipped` currently carries a real entry (`catboost`, a
parameter collision), so the item has teeth for the mid-run case but not the never-scheduled
one. **The item is widened** to fail on "candidate set was capped" as well, and the declared
cap is recorded as a first-class field in the run artifact. The plan's own words apply:
a number "real in one context and read as authoritative in another."

**Band 3 has no owner skill — the advisor could not evaluate it, and neither can this plan.**

Confirmed against CLAUDE.md's pipeline table: there is no skill between `/proto-execute`
(`Build`) and `/proto-review` (`Review`). Band 3 maps to `EXECUTED` with nothing that owns
it. Step 1's verify ("no band is empty") is the check that surfaces this, and it will fail
as the mapping stands. This is **not resolved here** — it is the first thing Step 1 must
settle, and it may mean band 3's owner is `/proto-review` with the mapping redrawn.

---

### Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Dispatcher runs from `~/workspace` and gets a hook tree that has drifted from the repo's, producing an untraced run that looks clean. **Downgraded 2026-08-15**: parity was repaired at 20:13, so this is latent rather than active — but nothing *enforces* parity, and it was false eight hours ago | Step 5 asserts the execution root and refuses to run; the failure is loud. Kept despite the repair, because parity is a fact about the present, not an invariant |
| R2 | Skill body drift — the dispatcher sends a stale copy of a `SKILL.md` | Read at dispatch time, never inlined (Step 5) |
| R3 | Bands 3/4 budgets get read as estimates | Contract records `unmeasured` with the target labelled as a target; the dispatcher emits elapsed time so evidence accrues (Q3) |
| R4 | Checklists become assertion theater under time pressure | Every item names a verifier and a path; Step 2's verification runs the checks against a known-bad artifact |
| R5 | Band 2 hits an irreversible decision triage failed to pre-clear. **Raised by FA-003**: band 2 owns `IN_PROGRESS`, so it runs `/proto-execute`, whose worktree agents **commit** (`SKILL.md:53-60`) — an action absent from Q1's enumerated "rerun, delete, `git checkout`" set. Stopping may be the modal case, not the exception | Contract makes stopping a legible outcome, not a crash (Q1). **The dispatcher records stopped-vs-completed from day one** (Step 5), so the budget is never computed over a population containing early stops — waiting for "frequency" to reveal itself is what would corrupt the measurement |
| R6 | Propose-and-confirm degrades into leading the operator to the proposal | Decision records capture confirmed-vs-overridden (Step 4); an override rate of zero is itself the warning sign |
| R7 | `.claude/docs/plans/` is git-ignored (F6), so band state has no durable git record | Out of scope; the artifact-on-disk-is-canonical rule (§3b-bis) already governs, and the ledger is the durable trace |

### Rollback

Steps 1, 2, 4, 5, 6 are new files or additive sections — delete them. Step 3 edits
`proto-scope/SKILL.md`; revert the commit. No hook, no state machine, and no skill
frontmatter is touched, so nothing this plan does can leave a plan doc unwritable — the
failure mode the #13 rollback discussion was built around does not arise here.

### Definition of Done

- The band → `Status:` mapping is ratified in a doc; all eight states map; no hook changed
- Every gate emits its release checklist with per-item evidence; an unverifiable item reads
  `false`; the fraud checks fail against the known-bad artifact
- A run of four bands over one target dispatches without the operator typing each skill
- The operator is asked at exactly two breakpoints and nowhere else
- The seven `disable-model-invocation` flags are still set; `git diff` shows no frontmatter change
- The ledger reader classifies forward/backward/lateral and counts loop-backs, with tests
- ~~The parity defect (V1) is filed as its own issue~~ — dropped; repaired 2026-08-15 20:13
