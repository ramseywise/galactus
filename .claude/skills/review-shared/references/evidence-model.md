# Evidence Model

Every finding must be classified into exactly one evidence state before a reporter
returns it. This is the `evidence.state` field in the canonical finding schema
(`finding-schema.md`).

## States

### Verified

Directly confirmed by deterministic evidence:

- Code inspection (grep, read, trace)
- Test result (ran and observed)
- Reproduction (triggered the failure)
- Explicit contract (SANYI.md entry matched)
- Deterministic tool output

### Supported

Strong evidence exists, but one external assumption remains unverified.
Example: code analysis shows the path is reachable, but depends on a configuration
value not inspectable in the current context.

### Hypothesis

Plausible risk without enough evidence to confirm. **Must not be phrased as a
confirmed defect.** Use language like "this appears to..." or "if X, then Y would..."

A hypothesis can still be `merge_impact: blocker` — evidence state and severity are
orthogonal. A plausible safety concern with insufficient evidence is reported as
`hypothesis` + `blocker`, not downgraded to `nit`.

### Question

Missing context prevents judgment. **Must be phrased as a clarification request.**
The reviewer cannot determine correctness without information that isn't in the code.

## Orthogonality principle

Evidence state describes **how confident you are**. Merge impact describes **how
much it matters**. They are independent axes:

| | blocker | important | suggestion | nit |
|---|---------|-----------|------------|-----|
| **verified** | confirmed critical | confirmed significant | confirmed minor | confirmed trivial |
| **supported** | likely critical | likely significant | likely minor | likely trivial |
| **hypothesis** | plausible critical | plausible significant | plausible minor | plausible trivial |
| **question** | unclear but potentially critical | unclear | unclear | unclear |

## Self-verification protocol

Before returning findings, verify your own candidates using available evidence:

1. **Inspect code** — read the actual implementation, don't guess from names
2. **Inspect callers** — check who calls the function and how (Grep for references)
3. **Inspect contracts** — check SANYI.md, CLAUDE.md, type signatures
4. **Inspect tests** — check if tests already cover the concern
5. **Run safe checks** — read-only Bash commands (grep, find, test runners in dry mode)
6. **Downgrade unsupported claims** — if you can't verify, classify as `hypothesis` or
   `question`, never as `verified`

The orchestrator does not re-verify findings from scratch. It only reconciles conflicts
between reporters or combines cross-reporter evidence. Assigning the correct
`evidence_state` is the reporter's responsibility.
