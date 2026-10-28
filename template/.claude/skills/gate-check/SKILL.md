---
name: gate-check
description: >
  Audit the project's lifecycle phase gates (Discovery → Delivery → Deployment)
  against the real artifacts and update LIFECYCLE.md — the committed status
  contract that project-mgmt-ai and other tooling read. Use before handing over
  a phase, when asked "are we ready to build/ship", or after closing open
  questions to see gate progress. Triggers on: "gate check", "are we ready",
  "discovery done?", "can we start delivery", "ready to deploy", "update the
  lifecycle", "project status".
---

# gate-check

Audit, don't assert: every checkbox in `LIFECYCLE.md` is the result of looking
at a real artifact this run. This skill is the **only writer** of
LIFECYCLE.md. If a check can't be verified, it stays `false` — never mark a
gate item true on memory or intent.

## Before you start

Read `LIFECYCLE.md` (fail if missing — the project predates the lifecycle
contract; offer to create it from the template). Note the current `phase`.

## Process

### 1. Audit G1 (discovery exit) — always

| Check | How to verify |
|---|---|
| `design_no_blocking_open_questions` | Read DESIGN.md. Every Open Questions entry and every `Open` Key Decision is either resolved or marked `Deferred(<trigger>)` with a real trigger. Count blockers. |
| `eval_targets_defined` | DESIGN.md Evaluation table has ≥1 real row AND `evals/targets.yaml` exists with matching metrics. |
| `golden_set_authored` | DESIGN.md § Behavioral Cases has ≥1 non-placeholder row AND `data/evals/cases.jsonl` exists, every case carrying a non-empty `source_risk` that matches an MVP Scope bullet. Count cases; do not trust a claim in the doc. Two-tier floor: **<10 cases = FAIL**, **10–19 = WARN** (reports the count and the 20–50 target, does not block), **≥20 = PASS**. A case with an empty or unmatched `source_risk` is a FAIL at any count. |
| `non_functionals_and_breakage_stated` | Read DESIGN.md. Non-Functional Constraints' Load / Latency target / Spend ceiling / Observability bullets each carry a real answer — **an accepted tier default ("free tier only (weekend-sprint default)") counts, an unreplaced `<!-- comment -->` does not** — AND the What Breaks First table has ≥1 non-placeholder row. This checks that the decisions were *made*, never that a particular number was chosen; a POC that consciously accepts demo-tier everything passes. |
| `base_scaffold_ci_green` | The project renders/builds: latest CI run green (`gh run list`), or locally `make test` + `make lint-check` pass. |
| `milestones_and_m1_tasks_reviewed` | Milestone doc(s) exist (`.claude/docs/milestones/` or DESIGN.md roadmap section) AND a TASKS.md/first-sprint plan exists AND a `/plan-review` artifact or review note covers them. |
| `rfc_approved` | RFC.md exists and contains a human-set `Status: APPROVED` line. **Never write that line yourself** — mirror it only. |

### 2. Audit G2 (delivery exit) — when phase is delivery or later

The G2 evidence lives in `DELIVERY.md` (the delivery record + handoff to
deployment) and `DEPLOYMENT.md` (the runbook). Read both; each check below
still verifies against the real artifact, not the doc's claim.

| Check | How to verify |
|---|---|
| `eval_gate_green` | Run `make eval-gate`; it must pass against `evals/targets.yaml`. |
| `security_review_clean` | A `/security-review` artifact exists for the current state with no unresolved findings. |
| `sanyi_audit_clean` | `/sanyi audit` passes (SANYI.md exists and the contract holds). |
| `deployment_target_resolved` | DESIGN.md deployment decision is `Resolved` (not Open, not Deferred). |
| `runbook_monitoring_documented` | Operator model row in DESIGN.md filled + a runbook/monitoring section or DEPLOYMENT.md exists. |

### 3. Layered-onto-existing-repo variant

If the project has no `evals/`/`Makefile` from this template (layering-only),
checks that audit template-owned artifacts are **inapplicable**: mark them
`true` and list them under "inapplicable" in the status summary — a gate must
not block on machinery the project never adopted. Checks against DESIGN.md,
RFC.md, and CI always apply.

### 4. Update LIFECYCLE.md

- Set each gate boolean to the audited result; set `updated` to today,
  `milestone` from the active TASKS.md, `blocking_open_questions` to the count
  from step 1.
- Advance `phase` only when its exit gate is fully true **and** the user
  confirms the handover — gates measure readiness; the human calls the move.
  Regressing phase (delivery back to discovery) is allowed and normal.
- Rewrite the Status summary: current phase, what's blocking the next gate
  (name the specific failing checks), what changed since last check.

## Output

Updated `LIFECYCLE.md`, plus a short report to the user: gate scoreboard
(passed/failed per check), the single next action that unblocks the most
checks, and — if a gate just went fully green — the explicit handover
question ("G1 is green: move to delivery?").

## Rules

- Booleans reflect this run's evidence only; re-running after any change is
  cheap and expected.
- Never flip `rfc_approved` from your own judgment; never edit RFC.md's
  Status line.
- Never advance `phase` silently — always ask.
- Deferred decisions don't block gates, but a `Deferred` without a concrete
  trigger counts as Open (that's a blocker).

---

**Upstream:** `/scope-poc` (DESIGN.md), `/define-milestones`, `/sprint-kickoff`, `/plan-review`, `/rfc` (RFC.md); for G2, `/deploy-check` (launch pre-flight — audits the same G2 criteria before this records them)
**Next:** on G1 green → `/execute-tasks`; on G2 green → `DEPLOYMENT.md` staged rollout (run `/deploy-check` first to pre-flight readiness)
