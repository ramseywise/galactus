---
name: review-safeguards
description: >
  Review dimension: evaluation rigor, human responsibility and escalation paths,
  and whether documented safeguards have real deterministic backing. Conditional
  on the diff touching agent code.
prefix: SG
allowed-tools: Read, Grep, Glob, Bash
---

# Accountability and Safeguards

Vendored from Parallax `.claude/skills/accountability-safeguards/SKILL.md`.
Parallax is read-only: fix upstream and re-vendor, never edit that copy from here.

You are dispatched with exactly this one dimension loaded, and only when
`review/signals.py` detected agent code in the changed files.

## Convention bindings

This dimension rests on written conventions, not on the code alone. Read the
relevant ref before reporting against it:

- [.claude/specs/agent-eval.md](../../specs/agent-eval.md) — what counts as evidence a change works
- [.claude/specs/agent-uncertainty.md](../../specs/agent-uncertainty.md) — abstention, asymmetric cost, reversibility
- [.claude/specs/agent-observability.md](../../specs/agent-observability.md) — what is visible at runtime

## Evaluation

- Is one successful run being overvalued? Are repeated runs needed?
- Is there a baseline?
- Are deterministic graders possible — is a model grading what code could check?
- Is an LLM judge calibrated?
- Are trace and final output both evaluated?
- Are cost and latency considered?

### Eval falsifiability

An eval that cannot fail measures nothing, and it is the highest-value check in
this section because it fails green. Evidence base:
`bug/marketing-comms-review-fixes` — a scripted provider drafted from a fixed
word list authored to match the fixtures, so the grounding rate measured
vocabulary overlap with a constant and was structurally incapable of dropping.
Check:

- **Both directions are tested.** For every headline metric there is a test that
  a good input scores positive *and* a test that a bad input scores negative.
  The negative is the load-bearing one: without it the positive is
  unfalsifiable.
- **Scripted providers respond to their inputs** — a harness double must derive
  its output from what it was actually prompted with (the facts in the prompt),
  not from constants authored to match the fixtures. Otherwise a regression that
  stops feeding the model its inputs leaves the metric green.
- **Config parity with production.** The eval runs the same constants and
  budgets the app runs — shared definitions, thresholds threaded as parameters,
  not re-hardcoded. An operator override that moves production behavior must
  move the eval numbers, or the harness measures a configuration nobody runs.
- **Fixture tables are validated at load.** A case table keyed by literal ids
  must fail loudly when a case is renamed or a required entry is missing —
  silent fall-through to a default profile keeps printing plausible numbers
  while measuring nothing. The validator itself runs against the shipped
  fixtures in CI.
- **Eval fakes conform to the port** (full signature) — otherwise the harness
  drifts from the system it grades.

## Human Responsibility

- Who approves? Who is accountable?
- Can a human take over?
- Is uncertainty visible?
- Is escalation available?

## Documented Safeguards

- Does documentation, a system prompt, or configuration claim a safety or
  guardrail behavior exists — an escalation path, an input/output validation
  layer, a confidence gate?
- Is that claim backed by an actual deterministic code path, or does it exist only
  as a sentence in a prompt?

A prompt-only invariant is the highest-value finding in this dimension: models are
probabilistic, so a constraint implemented only in a prompt is soft. When you find
one and the repo has a `SANYI.md`, report it here and note that the contracts
dimension should carry it as `BY-4` — do not attempt the contract draft yourself,
and do not route it to a subagent. Where no `SANYI.md` exists, recommend recording
the gap as a candidate Buyi or Pending entry, or running `/sanyi init`.

## Constraints

These six bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. Drop the rest.
2. **Surgical scope.** Flag what this diff caused; anything else carries
   `pre_existing: true`.
3. **Terse.** One to two sentences per finding.
4. **`quoted_span` required.** Quote the literal source text at the line you cite
   — for a prompt-only safeguard, quote the sentence in the prompt or doc that
   makes the claim.
5. **IDs use the `SG-` prefix** — `SG-001`, `SG-002`. A mismatched prefix fails
   validation as a skill-load failure.
6. **Spec citation (F4).** A finding that asserts a convention breach must carry
   `spec_citation` naming the spec file and section — for example
   `.claude/specs/agent-eval.md § Baselines`. `review/validate.py` rejects a
   finding that names a `.claude/specs/agent-*.md` path in its basis or claim text
   but carries no citation. Either cite the section or report the problem without
   invoking a spec.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
