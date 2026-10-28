# Angle: What should galactus's prototyping pipeline learn from diskoe's prototype-to-production journey?

## Findings

### 1. Spec separation timing — should `/proto-plan` enforce the four-document split from the start?

**Confidence: High** — diskoe CLAUDE.md:17-23, design-requirements.md header

Diskoe's "four documents, four questions" split (scope / requirements / roadmap / data-model) was
*imposed after the fact* on 2026-08-27 CHANGELOG:143: "Roadmap split into four documents with one
question each." The pre-split roadmap had become "a roadmap + requirements registry + backlog +
decision log + risk register in one file" (CLAUDE.md:18). The trigger was the namespace collision:
`D-` / `DA-` requirement IDs minted in two places at once.

The actual collision was earlier: `design-requirements.md` header notes "Requirement IDs are
inherited, not minted" and that `B*`, `D*`, `U*`, `Q*` IDs came from three *different* source
documents all referenced by the PRD. The repair (restructure to one-question-per-file) was done
retroactively on the same day as the big build wave, adding friction.

**What galactus's `/proto-plan` currently does**: writes a single plan doc with `## Research` and
`## Plan` sections. The plan doc is a one-work-item artifact, not a multi-document architecture
spec. The problem does not exist at the proto scale because galactus prototypes are one run
directory. But the FRAME band (`/proto-scope` → `/proto-design`) has no mechanism to enforce
separation of *scope* (what problem), *requirements* (what must exist), and *roadmap* (why this
next) once a project matures past a single run.

**Signal for galactus**: The collision point arrived when the `DESIGN.md` from `/proto-scope` was
being extended ad-hoc to carry requirements, decisions, and risk registers. The `/proto-design`
skill should warn when a `DESIGN.md` section count exceeds the "five-layer spec" frame it was
designed for, prompting a handoff-moment: the project is past prototype, scope/requirements/roadmap
belong in separate documents. This is a handoff signal, not a structural change to the proto pipeline.

### 2. Eval-from-day-1 — should `/proto-execute` include eval scaffolding as a default step?

**Confidence: High** — diskoe CLAUDE.md:36, 127-133; mvp-roadmap.md CHANGELOG:83-84

Diskoe's eval harness was *not* built early by default — it was built in one concentrated push on
2026-08-27 (CHANGELOG:83: "Eval harness live (B-18)"). However, the requirement that it *needed*
to exist was present earlier: CLAUDE.md:126-133 documents the constraint "Every scoring dimension
and enrichment attribute needs an eval metric." The harness shipped late relative to the code it
grades because nothing *forced* eval scaffolding at feature build time.

The consequence was explicitly named in the design-requirements.md header note: instrumentation
(T-0) could not ship independently because it depends on a ranked result set that did not exist
yet. The eval gate retroactively enforcing 17 metrics at 1.0 required no rewrites *only because*
the underlying logic was pure functions with no I/O. Had that separation not existed (see Finding 4),
retroactively adding evals would have been much harder.

**What galactus's `/proto-execute` currently does**: step 5 logs to CHANGELOG.md; the DoD check in
`/proto-review` checks "New behavior has a test that fails without the change" and "Doc parity" but
has no eval scaffold requirement. The word "eval" does not appear in `proto-execute/SKILL.md`.

**Signal for galactus**: Add an eval checkpoint to the `/proto-execute` per-step loop for `Track:
agent` work (not `Track: ml` where evals are already first-class through `/ml-select` and
`/ml-transform`). The checkpoint should not require a grader to exist, but should require the
developer to name the metric and state whether it is `GATED` or `UNGATED`. Diskoe's pattern of
"unmeasured metrics stay commented and report UNGATED" is the right shape — it makes the debt
visible rather than invisible. A step that introduces a new agent output with no named metric gets
flagged at execute time, not after the fact at review.

The pure-function / no-I/O separation that made diskoe's retroactive eval possible is already a
galactus norm (agent layers are pure), so the enforcement surface is there.

### 3. Change contract — does diskoe have a change-contract.md? What does it enforce? SANYI gap?

**Confidence: High** — diskoe `.claude/specs/change-contract.md` (SANYI.md); galactus
`review-contracts/SKILL.md`

Diskoe has a `change-contract.md` named `SANYI.md` with `project: diskoe, version: 1,
last-audit: 2026-08-29`. It enforces 11 named invariants (Buyi), 5 budgets (Jianyi), and 5
tunables (Bianyi), with a `## Debt` section for declared-but-unenforced invariants (BY-4) and a
`## Migrations` log.

Key invariants that are *diskoe-specific and earned by defect*:
- One visibility gate (`review_status = 'published'`) — came from 4 competing lifecycle columns
- G1 — served ranked set = logged ranked set (instrumentation ships in same commit as ranker)
- Every scoring dimension has an eval metric (enforced via CI gate)
- A migration is not done until pushed AND probed (earned by two columns marked DONE while absent)

**The SANYI gap from galactus's perspective**: Galactus's `review-contracts` dimension
(`SKILL.md:1-9`) activates *conditionally* — only when `SANYI.md` is at the repo root and
`detect-signals` fires `has_sanyi_contracts`. Galactus is a *prototyping* repo and does not carry
its own `SANYI.md`. The current design assumes that galactus's *final act* is emitting review
contracts (SANYI.md) that make the prototype guacamayo-ready — the handoff artifact is the
contract itself.

**What is actually missing**: Galactus has no `/contract` skill (diskoe's `change-contract.md`
was authored by `/contract init`). The skill exists in diskoe's `.claude/skills/` but its presence
in galactus is not confirmed. There is no skill in galactus's pipeline to *produce* a SANYI.md
as a final-act output. The `proto-review` SKILL.md (Stage 1, step 4) checks "for SANYI.md" to
decide whether to activate `review-contracts`, but the pipeline has no step that *creates* one.

**Signal for galactus**: Add a `/proto-harden` or `/proto-review` Stage 5 item that, on first
invocation of a run that has no SANYI.md, generates one from the conventions, invariants, and
budgets that the review process has surfaced. Diskoe's file was "auto-drafted from code, CLAUDE.md
and the gates" and then submitted to a human interview to confirm business/safety intent —
exactly the handoff artifact galactus is supposed to produce. The pipeline's exit should produce
a skeleton `SANYI.md` into the run directory. Whether it is committed there or extracted upstream
is a handoff decision, not a pipeline decision.

### 4. Build velocity patterns — what should galactus structure from diskoe's arc?

**Confidence: High** — diskoe CHANGELOG, mvp-roadmap.md, design-requirements.md

Diskoe's build arc, from CHANGELOG provenance note ("Work before 2026-08-20 in diskoe-mvp;
2026-08-20–28 no git"):

- **Phase 0 (before 2026-08-20)**: Align — scope, architecture, feasibility docs. No code.
- **Phase 1–3 (2026-08-20 to 2026-08-27)**: All engineering of concierge + data pipeline + accounts
  landed in one concentrated day (2026-08-27 CHANGELOG: "big day — evals, concierge, polls,
  accounts, schema"). The entire day was triaged plan-doc driven.
- **Phase 4 (2026-08-28 on)**: git init, restructure, board, then validation experiments.

Three structural patterns worth naming:

**Pattern A — Codebase audit before plan.** Design-requirements.md has a prominent "2026-08-24
verification" block that caught the PRD's inherited markers as wrong (ranker marked shipped, was
not built). The research phase re-verified *actual build state* before planning resumed. Galactus's
`/proto-research` already does this (reads the codebase before writing `Track:` and `## Research`),
but the skill could be more explicit about making a "build state vs spec state" table when a partial
prototype exists.

**Pattern B — Gate separation from phase separation.** Diskoe's three gates (G1, G2, G3) are
*system states*, not phase names. Phases name the *work*; gates name *what must be true before
the next thing*. Galactus's pipeline uses `PLANNED → REFINED → READY → IN_PROGRESS → EXECUTED →
COMPLETE` as a per-work-item state machine, but has no concept of a system-level gate that spans
multiple work items. For multi-item prototypes, a gates table in DESIGN.md would let
`/proto-review` check gate status rather than only checking plan fidelity.

**Pattern C — Phase 4 = validate, not build.** Diskoe explicitly separated Phase 4 (validate —
"each experiment may return no, and that is the deliverable") from Phase 5 (scale + hardening —
"fires on a number or a fact"). Galactus's pipeline ends at `COMPLETE` with no corresponding
concept of a validation phase. A prototype that exits the galactus pipeline is handed off to
production; whether it *earned* that handoff (i.e., beat a baseline measurably) is not tracked
in the pipeline state machine. Adding a `VALIDATED` state (after `COMPLETE`, gating on a specified
baseline comparison) would match how the successful prototypes actually shipped.

**Pattern D — "Nothing built without a file path" convention** (diskoe CLAUDE.md:25): "Check the
tree before trusting a section here. Nothing is BUILT without a file path." Galactus's
`/proto-research` already enforces this (flags missing paths as blockers), but `/proto-plan`'s
output template has no corresponding "Done when" verification that a claimed-built component has
a file path in the tree. The diskoe convention of `BUILT` = "module exists and is tested" should
be a `/proto-review` DoD item.

### 5. SANYI alignment — are galactus's emitted review contracts aligned with diskoe's SANYI shape?

**Confidence: Medium** — galactus `review-contracts/SKILL.md`, diskoe `change-contract.md`

Galactus's `review-contracts` dimension knows how to *read* a SANYI.md and check a diff against
it (SKILL.md checks BY-*, JY-*, BN-*, MG-*, UN-* violation codes). The violation taxonomy is
exactly the vocabulary diskoe's `change-contract.md` uses.

But galactus has no `/contract` skill that *produces* a SANYI.md. The handoff statement in
galactus's CLAUDE.md ("galactus's final act is emitting the review contracts that make the
prototype guacamayo-ready") is stated as a design intent, not implemented as a pipeline step.
There is no `proto-harden` or `proto-review` exit action that writes a SANYI.md.

Diskoe's SANYI.md was auto-drafted from "code, CLAUDE.md, and the gates" (change-contract.md:7-12)
on 2026-08-29 — after the full build — using a `/contract init` skill. That skill reads the specs
first, then asks only what the specs cannot answer, and every question arrives with its citation.
This is the correct shape for the galactus handoff: galactus writes the skeleton, the owner
confirms the intent.

**The gap**: Galactus's pipeline has no `/contract` or equivalent skill. If this was demoted from
global to guacamayo, it would be accessible from galactus via `repo:` dispatch, but there is no
evidence of this path being used. The `review-contracts` dimension in proto-review activates on
detecting a SANYI.md; because galactus runs have no SANYI.md, the `contracts` dimension is always
skipped for galactus work, meaning the contract review that should be galactus's *final product*
never runs.

**Alignment verdict**: The vocabulary is aligned (both use BY-*/JY-*/BN-* codes). The *process* is
misaligned — galactus's pipeline has no mechanism to produce the artifact that its `review-contracts`
dimension checks, so the final-act promise is unimplemented.

## Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| Diskoe `/contract` skill | ADAPT | The interview-guide.md, violations.md taxonomy, and the "auto-draft from code + CLAUDE.md + gates" bootstrapping pattern are directly portable to galactus with a `proto-` prefix and `Track: agent` scoping | The skill lives in diskoe, not galactus; galactus's pipeline has no equivalent. Adapting it as `/proto-contract` would close the final-act gap without wholesale copying diskoe's toolchain |
| Diskoe's four-document spec split (scope/requirements/roadmap/data-model) | SKIP | The handoff signal — "DESIGN.md has grown past the five-layer spec frame" — is the salvageable idea: add a section-count check in `/proto-scope` or `/proto-design` exit that warns when DESIGN.md exceeds its frame | Galactus works at a finer grain (one run dir per work item); the four-document structure is a project-maturity artifact, not a proto-pipeline design. The split belongs to the stage *after* galactus hands off |
| Diskoe eval CI gate pattern (`registry.ts` + `targets.yaml` + `eval:grade --gate`) | ADAPT | The invariant — "unmeasured metrics stay commented and report UNGATED; CI runs the gate" — is portable as a pattern note in `/proto-execute` for `Track: agent` steps that introduce new model outputs | The TypeScript/Vitest stack is diskoe-specific; galactus uses Python/pytest. The pattern is what matters, not the file structure |
| Diskoe's `make gate` db-drift + migration-is-not-done-until-probed invariant | SKIP | The probing protocol ("The file existing is not evidence that it ran") is a general verification rule worth adding to galactus's `/proto-execute` DoD checklist for any step that touches a store or external dependency | Diskoe's `db-drift` target is Supabase-specific. Galactus prototypes rarely manage migrations; the structural insight is the probing rule, not the tooling |
| Diskoe Phase 4 "validate — no is a result" structure | ADAPT | Add a `VALIDATED` state to galactus's plan doc state machine (after `COMPLETE`, gating on a named baseline comparison) and a `/proto-validate` or Phase 4 section in `/proto-plan`'s template | Galactus's current `COMPLETE` terminal state has no way to capture "earned the handoff vs declared it done." A minimal adaptation is a `baseline:` field in the plan doc template that `/proto-review` must confirm is met |
| Diskoe's `BUILT = module exists and is tested, not deliverable accepted` distinction | REUSE | Lift verbatim into galactus's `/proto-review` DoD item: "A claimed-built component has a file path in the tree and a test that fails without it" | This is already partially in place (DoD requires tests), but the explicit "nothing is BUILT without a file path" phrasing sharpens it |

## Open questions

1. **Does `/contract` (or equivalent) exist anywhere in galactus's skills?** The `archived/`
   directory was not read. If it was demoted to archived or to guacamayo, the path to a
   `/proto-contract` is just a re-vendor; if it never existed in galactus, the gap is larger.

2. **Is the galactus "final act emits SANYI.md" promise tracked as an open issue?** The CLAUDE.md
   asserts it as design intent but no skill produces a SANYI.md and no plan doc was found
   describing how to build one. If this is intended to be implemented, it needs an issue.

3. **What is the right grain for a system-level gates table in DESIGN.md?** Diskoe's three gates
   (G1/G2/G3) span the whole build. For a galactus prototype, a run-level gates table would be
   1-3 items. The question is whether `/proto-design` should prompt for them during FRAME, or
   whether `/proto-plan` should require them when `>8 steps` triggers a phase split.

4. **`Track: agent` eval scaffolding — at the step level or the plan level?** Diskoe built all
   17 metrics in one wave. The alternative is requiring a metric name per agent output at plan
   time (proto-plan) rather than a scaffold at execute time (proto-execute). The plan-time
   approach makes the debt visible earlier but adds friction to plans that will never need graded
   evals.

5. **Is the `/proto-review` `contracts` dimension currently always skipping for galactus runs?**
   The dimension activates on `has_sanyi_contracts` signal, which requires a `SANYI.md` at the
   repo root. Galactus prototypes live under `runs/ai/` or `runs/ml/`, not the repo root. The
   question is whether `detect-signals` also checks the run directory for a SANYI.md or only
   the repo root — if it is root-only, the dimension is permanently skipped for all galactus
   work, which means the final-act promise is unreachable by the current signal logic.
