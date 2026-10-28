---
name: review-testing
description: >
  Review dimension: test coverage — unit, integration, contract, regression,
  end-to-end, negative paths, assertion usefulness, and failure-before-fix
  evidence.
prefix: TE
allowed-tools: Read, Grep, Glob, Bash
---

# Testing

Vendored from Parallax `.claude/skills/intent-correctness/SKILL.md`, § "Testing".
Parallax is read-only: fix upstream and re-vendor, never edit that copy from here.

You are dispatched with exactly this one dimension loaded. Report only testing
gaps — the bug itself belongs to correctness or silent failure; you own whether
anything would catch it.

## What to examine

- **Unit**: Do unit tests cover the new/changed logic in isolation?
- **Integration**: Do integration tests cover how this interacts with the
  components it depends on?
- **Contract**: If a contract (API, schema, interface) changed, is there a
  contract test guarding it?
- **Regression**: For a bug fix, does a regression test exist for that specific
  bug?
- **End-to-end**: Is there end-to-end coverage exercising this change through a
  realistic path?
- **Negative paths**: Are failure paths tested, not just the success case?
- **Useful assertions**: Do the assertions verify the behavior that matters, or
  only that the code ran without throwing?
- **Failure-before-fix evidence**: For bug fixes, is there evidence the test
  failed before the fix and passes after?

A test that cannot fail is worse than a missing test: it reports coverage it does
not provide. Assertions that only check "no exception" are the common shape.

### Seam conformance (fakes and the real adapter)

A fake that conforms to a broken seam certifies the break. Evidence base:
`bug/marketing-comms-review-fixes` — the vision path rendered PNGs and threw them
away because the `LLM` port had no `images` parameter, and every fake matched the
broken port exactly, so 300 green tests could not see it. Check:

- **One shared fake per port, not per-module fakes.** N hand-rolled fakes of the
  same Protocol are N places a port change is silently missed — a port change
  should break one fake loudly, not three quietly. Flag duplicated fakes.
- **The fake records the full signature**, including optional channels
  (`images=`, extra kwargs). A fake narrower than the Protocol it stands in for
  is a finding even when tests pass.
- **A contract test pins the real adapter's wire shape** independently of the
  fake: decode what the adapter actually sends (base64 back to bytes, block
  order, media type) and assert identity with the input. A fake's recording is
  only meaningful if something else proves what the real adapter does with the
  same argument.
- **Caller-side identity assertions close the loop**: what the caller hands
  across the seam equals the real artifact (byte-exact where possible), asserted
  at unit and end-to-end level.
- **Fake error modes raise the real error types**, imported from the production
  module — not stand-in exceptions.
- **Green for the wrong reason**: tests whose preconditions only pass because a
  validation is missing, or whose two runs are collapsed into one by idempotency
  so an assertion compares a value to itself. When the diff adds a check, ask
  which existing tests were relying on its absence.

### Duplex / streaming (only when the design has no turn boundary)

Skip for request/response code. See
[.claude/specs/agent-voice.md](../../specs/agent-voice.md) and
[.claude/specs/agent-eval.md](../../specs/agent-eval.md).

- **deterministic replay** — asserting end-to-end replay that does not exist. Audio
  timing, endpointing, and interruption points do not reproduce; a test that pins an
  exact transcript or turn sequence through the assembled pipeline is asserting
  determinism the system does not have, and it will flake or be pinned into
  meaninglessness. Components replay deterministically; the pipeline is graded
  statistically.
- **task success** — reporting WER in place of task completion. Task success is the
  metric; WER is a component number. Flag a suite whose headline is word error rate,
  or one that grades transcription while never asserting the task completed.
- Per-turn pass rates presented as end-to-end reliability: 90% per turn survives ten
  turns about a third of the time.

## Constraints

These five bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. Drop the rest.
2. **Surgical scope.** Flag coverage gaps this diff created. A module that was
   already untested is reportable only when the change extends it, carrying
   `pre_existing: true`.
3. **Terse.** One to two sentences per finding.
4. **`quoted_span` required.** Every finding quotes the literal source text at the
   line it cites — for a missing test, cite and quote the untested code, not an
   absent test file. A finding whose only location is a file that does not exist
   cannot be validated and will be rejected.
5. **IDs use the `TE-` prefix** — `TE-001`, `TE-002`. A mismatched prefix fails
   validation as a skill-load failure.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
