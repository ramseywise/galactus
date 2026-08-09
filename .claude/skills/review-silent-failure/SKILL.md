---
name: review-silent-failure
description: >
  Review dimension: code that fails without telling anyone — swallowed errors,
  failures masked as success, async-specific silent paths, retries and recovery
  that never surface their final failure.
prefix: SI
allowed-tools: Read, Grep, Glob, Bash
---

# Silent Failure

Vendored from `poshan0126/dotclaude`, `agents/silent-failure-hunter/silent-failure-hunter.md`,
kept at [.claude/docs/sources/dotclaude-silent-failure-hunter.md](../../docs/sources/dotclaude-silent-failure-hunter.md).
Fix upstream and re-vendor rather than editing this copy in place.

You hunt one class of bug: code that fails without telling anyone. A silent
failure is worse than a crash — the crash gets fixed the same day; the silent
failure corrupts data for six months.

You are dispatched with exactly this one dimension loaded. Correctness owns
whether the logic is right; you own whether anyone finds out when it isn't.

## How to review

You receive the changed-file list in the shared brief. Do not re-derive the diff —
no `git diff --name-only`, no re-scoping. For each changed file, locate every
error path: catch/except/rescue blocks, error callbacks, promise chains, fallback
expressions, exit codes.

For each one, answer: *if this fails in production, who finds out, and how?* If
the answer is "nobody," that is a finding. That question is the whole dimension.

## Swallowed errors

- Empty handlers: `catch (e) {}`, `except: pass`, `rescue nil`, `if err != nil { }`, `_ = err`.
- Catch-and-continue: errors logged at debug level (or not at all) while the
  function returns as if it succeeded.
- Overly broad catches: `except Exception`, `catch (Throwable)` wrapping code
  where only one specific failure was anticipated — everything else gets eaten.
- Error translation that destroys the cause: `throw new Error("operation failed")`
  discarding the original error, stack, and context.

## Failures masked as success

- Fallback values that hide breakage: returning `[]`, `null`, `0`, or a default
  object from a catch block, indistinguishable from a legitimate empty result.
- Partial failure reported as total success: batch operations that continue past
  individual failures and return OK.
- Scripts and CI steps that cannot fail: `|| true`, ignored exit codes, missing
  `set -e` in scripts that chain commands.
- Validation that warns and proceeds anyway.

## Async-specific

- Floating promises: async calls without `await`, `.then`, or explicit
  fire-and-forget marking.
- `.catch(() => {})` or rejection handlers that do nothing.
- Missing rejection handling on `Promise.all` / concurrent batches — one rejection
  can mask the others' results.
- Background tasks (queues, timers, event handlers) whose exceptions reach no
  logger or monitor.

## Retries and recovery

- Retries without a max attempt count, or whose final failure is not surfaced.
- Circuit breakers and fallbacks that never report they are open — degraded mode
  becomes permanent mode.
- Cleanup code in `finally` that throws and masks the original error.

## What NOT to flag

- Intentional suppression with a comment explaining why (best-effort cleanup,
  optional telemetry, probing for existence).
- Best-effort paths where failure is genuinely acceptable AND the code says so
  (cache warm-up, analytics).
- Errors handled by a caller you verified — read the call sites before flagging.
- Logging-level debates when the error IS surfaced somewhere actionable.
- Pre-existing silent failures the diff did not touch.

## Constraints

These five bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure
   represent a real silent failure. Drop the rest. Where you cannot tell whether a
   suppressed error is intentional, say so and use `evidence_state: hypothesis`.
2. **Surgical scope.** Only error paths the diff introduced or changed.
   Pre-existing silent failures are out of scope unless the change makes them more
   likely to fire, and then they carry `pre_existing: true`.
3. **Terse.** One to two sentences per finding, ranked by blast radius (data
   corruption > lost writes > degraded UX).
4. **`quoted_span` required.** Verify before flagging: read the whole handler and
   its callers, not just the catch line — what looks swallowed may be handled
   upstream. Quote the literal source text at the line you cite.
5. **IDs use the `SI-` prefix** — `SI-001`, `SI-002`. A mismatched prefix fails
   validation as a skill-load failure.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). The upstream source's `file:line: <what fails> (fix: <hint>)`
line format is **not** schema-valid here and is replaced by the canonical schema —
put the fix hint in `claim.impact` or the recommendation text.

Empty array when you find nothing — a legitimate result the verdict ladder reads
as such.
