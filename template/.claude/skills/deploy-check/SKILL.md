---
name: deploy-check
description: >
  Launch-readiness audit for the Deployment phase — checks G2 (delivery → deployment)
  gate criteria against real artifacts and reports what's missing before a canary
  rollout. The pre-flight to /gate-check's recorded verdict; it never writes
  LIFECYCLE.md. Use before shipping, when asked "are we ready to deploy/launch",
  or when starting a canary. Triggers on: "deploy check", "ready to ship",
  "ready to launch", "pre-flight", "can we deploy", "deployment readiness",
  "/deploy-check".
---

# deploy-check

Audit, don't assert. Every result below comes from looking at a real artifact
this run — never from memory or intent. If a check can't be verified, it
**fails**; a launch pre-flight that guesses is worse than none.

**This skill does not write `LIFECYCLE.md`.** `/gate-check` is that file's sole
writer. `/deploy-check` is the launch-day pre-flight — it tells you whether G2
will pass and what to fix. Once it's green, run `/gate-check` to record the G2
verdict and advance the phase. Keeping the two separate keeps one writer for the
status contract (doc-writer boundary).

## Before you start

Read `LIFECYCLE.md` for the current `phase` and the G2 checklist, and
`DEPLOYMENT.md` for the rollout plan. If `DEPLOYMENT.md` is missing, that's the
first thing to fix — a G2 check (`runbook_monitoring_documented`) depends on it.

## Process

### 1. Audit G2 (delivery → deployment)

Same checks `/gate-check` records for G2, verified here as a pre-flight:

| Check | How to verify |
|---|---|
| `eval_gate_green` | **First check `evals/targets.yaml` has ≥1 activated (uncommented) target** — a fully-commented file makes `make eval-gate` pass *vacuously* (the CD gate only WARNs on it, by design, so canary iteration isn't blocked). An agentic project with zero activated targets is **NOT ready** — FAIL this check and name it as the gap to fix. Once ≥1 target is real, run `make eval-gate`; it must pass, including the margin-over-naive-baseline row. Capture the actual result. |
| `security_review_clean` | A `/security-review` artifact exists for the shipping commit with no unresolved findings. |
| `sanyi_audit_clean` | `/sanyi audit` passes — SANYI.md exists and the contract holds for what's shipping. |
| `deployment_target_resolved` | DESIGN.md's deployment decision is `Resolved` (not Open, not Deferred). |
| `runbook_monitoring_documented` | `DEPLOYMENT.md` exists and its Rollout, Rollback, and Monitoring sections are filled — not placeholder comments. |

### 2. Audit the launch mechanics — DEPLOYMENT.md specifics

Beyond the G2 booleans, confirm the rollout is actually executable:

| Check | How to verify |
|---|---|
| Staged rollout defined | DEPLOYMENT.md's stage table has a bake window and traffic steps filled in (not `<!-- set per release -->`). |
| Guardrail metrics have numbers | Each guardrail names a floor/ceiling — a guardrail without a number can't trigger a rollback. |
| Rollback is one command | The last-known-good tag/revision is recorded, and the rollback path is redeploy-previous (not forward-fix). |
| A/B decision is wired | If interaction metrics + `ml/` exist, `ml/AB_BRIDGE.md` is present and the canary's promote/rollback decision is statistical, not eyeballed. |
| Health/monitoring | Every long-running service exposes `/health`; the monitoring checklist names a log destination and an on-call/operator (DESIGN.md's operator-model row). |
| CD wiring (docker/cloud) | `.github/workflows/cd.yml` exists with the `build-canary` + `promote` jobs, and the `production` environment has a required reviewer for the promote gate. (serverless/local: confirm the platform's own traffic-split primitive is planned instead.) |

### 3. Layered-onto-existing-repo variant

If the project has no `evals/`/`Makefile`/`cd.yml` from this template
(layering-only), template-owned checks are **inapplicable** — report them as
`n/a` with a one-line note, don't fail on machinery the project never adopted.
Checks against DESIGN.md, the security review, and DEPLOYMENT.md always apply.

## Output

A launch-readiness scoreboard, then a verdict:

- **Scoreboard**: each check `pass` / `fail` / `n/a`, with the evidence (the
  actual `make eval-gate` result, the review artifact path, etc.).
- **Blockers first**: the failing checks, ordered by what unblocks the most.
- **Verdict**: `READY` (all pass/n/a) or `NOT READY` with the shortest path to
  ready.
- If `READY`: the explicit handoff — "G2 pre-flight is green: run `/gate-check`
  to record the verdict and advance the phase, then execute DEPLOYMENT.md's
  stage 0 (shadow)."

## Rules

- **Never write `LIFECYCLE.md`** — that's `/gate-check`'s job. Report readiness;
  let `/gate-check` record it.
- Results reflect this run's evidence only; re-running after a fix is cheap and
  expected.
- A green pre-flight is a recommendation to record via `/gate-check`, not the
  record itself — and never the decision to launch. Advancing the phase and
  starting the rollout are human calls.
- Deferred decisions don't count as resolved: a `Deferred` deployment target is
  a `deployment_target_resolved` failure at G2.

---

**Upstream:** `/execute-tasks`, `/code-review`, `/security-review`, `/sanyi audit`, `DEPLOYMENT.md`
**Next:** pre-flight green → `/gate-check` (records G2, advances phase) → execute DEPLOYMENT.md's staged rollout
