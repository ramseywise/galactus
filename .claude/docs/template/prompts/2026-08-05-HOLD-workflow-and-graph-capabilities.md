# Spawn prompt — ai-project-template: workflow + knowledge-graph capabilities

> **STATUS: HOLD. Do not run yet.**
>
> **Blocked on two upstream decisions**, both in progress as of 2026-08-05:
>
> 1. `~/workspace/librarian/.claude/docs/plans/2026-08-05-typed-graph-retrieval.md`
>    — the typed edge vocabulary and whether graph expansion beats a lexical baseline.
>    **Not yet run.**
> 2. `~/workspace/guacamayo/.claude/docs/plans/2026-08-05-multi-agent-orchestration.md`
>    — the role/contract decomposition. **Complete.** Key output: contracts move into
>    repo code as typed schemas while skills remain the invocation interface.
>
> **Why hold:** this template's job is to vendor *decided* patterns. Templating a
> knowledge-graph scaffold before librarian's ablation runs risks shipping a schema its
> own research refutes — and a bad pattern in a template propagates to every project
> scaffolded from it, which is strictly worse than no pattern. Run librarian's research
> first. If it refutes typed edges at this corpus size, **that finding is what gets
> templated** (as a documented "don't do this until N pages"), not the schema.
>
> Release condition: both plan docs exist with their edge-schema and role-contract
> sections resolved. Then delete this block and run.

Paste into a FRESH VS Code Claude session. Set model to **fable**
(`/model claude-fable-5`) — judgment-tier research pass, not execution.

---

Repo: ~/workspace/ai-project-template

/workflow-research repo:ai-project-template workflow-and-graph-capabilities

You are researching whether and how to add two new capabilities to this Copier template —
an **orchestrated-workflow scaffold** and a **knowledge-graph/retrieval scaffold** — and,
separately, whether the template's onboarding experience is actually good. Understand
only. Do not propose implementations, do not write code.

## Framing — read this before anything else

**This template is mature, not empty.** It has a phased Copier interview, a
`design.yaml` external-data staging layer, a rendering CI matrix
(`.github/workflows/test-render.yml`), 26 vendored skills, LangGraph/ADK/Vercel shape
examples, and ~20 prior plan docs under `.claude/docs/plans/`. **Read
`2026-07-30-system-design-rigor-gap.md` and `2026-08-01-49-llm-starter-kit.md` before
forming any opinion** — the questions below have probably been partly answered already,
and re-deriving them wastes the pass. Treat prior plan docs as findings you must
reconcile with, not as background.

Corollary: the bar for adding a capability here is high. Every new toggle is a question
in an interview that is already ~11–14 questions long, plus a row in the render matrix,
plus a maintenance surface. **"Add it as a `-d`-only capability, never a genesis
question" is the established pattern** — start from that presumption and argue only if
the evidence overturns it.

## The thesis this research must confirm or refute

*The two patterns worth templating are the ones just proven out in sibling repos: a
typed-graph retrieval scaffold (librarian) and a role-contract orchestration scaffold
(guacamayo). Both should enter as `-d` capabilities rather than interview questions, and
the orchestration one is more valuable than the graph one because it generalizes further.*

A refutation is valuable. "The graph pattern is too corpus-specific to template" or "the
role contracts are guacamayo-shaped, not general" are legitimate findings.

## Core questions

1. **What did the upstream research actually decide?** Read both plan docs named in the
   HOLD block. Extract the parts that are *general* (a role/contract table shape, a
   findings schema, an eval harness layout, an edge-type vocabulary) from the parts that
   are *repo-specific*. **Only the general parts are templatable.** Be strict — the
   temptation is to template the instance.

2. **The orchestration capability.** Guacamayo's adopted direction is that inter-role
   contracts belong in repo code as typed schemas while skills remain the invocation
   interface. What is the minimum scaffold that gives a new project that? Candidates: a
   `schemas/` module with role-boundary types, a findings-emit contract, a verdict type
   that is *actually consumed*. Note that guacamayo's central defect was a defined
   verdict type that both ends bypassed — **a scaffold that ships an unused type
   reproduces the bug it was meant to prevent.** What makes a templated contract
   load-bearing rather than decorative?

3. **The knowledge-graph capability.** Conditional on librarian's ablation. If typed
   edges help: what is the minimum scaffold (edge schema, storage, a retrieval path that
   branches on edge type, a golden set + ablation harness)? If they don't help at small
   corpus size: is the templatable artifact instead a *documented threshold* — "here is
   where graph structure starts to pay, here is the ablation to run before you build it"?
   The template already has a corpus pipeline (`core/pipelines/corpus/`, markdown→JSONL→
   DuckDB-FTS) and a retrieval golden-QA eval — determine whether this is an extension of
   that or a separate capability.

4. **Is the onboarding actually user-friendly?** The user's stated goal. Assess honestly
   rather than assuming it's bad: walk the interview as a new user, and identify where
   someone gets stuck or answers wrong. Specific things to check — is 11–14 questions the
   right length; is `/add-capability` discoverable *after* genesis or does it only exist
   in `_message_after_copy`; can a user tell what they'll get before answering; what
   happens when someone picks the wrong `project_type`. **Prefer concrete friction over
   general "improve docs" recommendations.**

5. **Vendored-skill staleness — the structural risk.** `scripts/sync-global-skills.sh`
   is the one sanctioned exception to "never copy global skills into a repo," because
   scaffolded projects can't reach `~/.claude`. But every vendored skill is a copy that
   drifts. Assess: how stale is the current vendored set; does the hard-fail-on-unknown-
   name guard catch the failure modes that matter; and — the real question — **when the
   global roles change shape (which the guacamayo work will do), what breaks here and how
   would anyone notice?**

6. **What does this collide with?** The repo is on branch `bug/sync-global-skills` as of
   2026-08-05 with recent work on that script. Check open issues and in-flight branches.
   Determine ordering against them. Do not assume the branch is finished.

## Required outputs beyond the standard template

- **Templatable/not-templatable split** — for each pattern from the upstream research, a
  verdict with the reason. This is the core deliverable.
- **Capability entry design** — for each capability judged worth adding: genesis question
  vs `-d`-only vs `/add-capability`, and what it costs in interview length and render
  matrix rows.
- **Onboarding friction list** — ranked, concrete, each with the specific step where a
  user gets stuck.
- **Drift-detection recommendation** — how a vendored-skill/global-role mismatch becomes
  *visible* rather than silent.

## Constraints

- Read the prior plan docs before concluding. Cite `file:line` for every finding.
- Confidence label on every finding; Disconfirming Evidence section is mandatory.
- Do not write code. Do not edit anything outside
  `.claude/docs/plans/2026-08-05-workflow-and-graph-capabilities.md`.
- Do not commit. Do not push.
- Stop when the core questions have confident answers with cited evidence.

Artifact lands at:
`~/workspace/ai-project-template/.claude/docs/plans/2026-08-05-workflow-and-graph-capabilities.md`

---

## After it returns

Next phase gate is `/workflow-plan` in a fresh session pointed at that doc, then
`/workflow-refine`. Do not execute from the research doc directly.
