---
name: review-shared
description: "Shared contracts for every review reporter — the canonical finding schema, the evidence model, the context brief, and the merge-decision ladder. Preloaded by /workflow-review, /akira, and /sanyi rather than invoked directly. Load it when writing a new reporter or when two reporters disagree about a finding's severity."
---

# review-shared

The contracts every review reporter writes against. This skill holds no procedure of its
own — it exists so that `akira-scan`, `akira-wander`, and `sanyi` emit findings a single
orchestrator can merge without re-reading each reporter's private conventions.

Load a reference when you need it, not preemptively:

| Reference | Load when |
|---|---|
| `references/finding-schema.md` | Emitting or merging any finding |
| `references/evidence-model.md` | Deciding how confident a finding is |
| `references/context-brief.md` | Assembling the input every reporter receives |

## The two axes

The one thing to carry even without reading the references: **evidence state and merge
impact are orthogonal.** Evidence state is how sure you are; merge impact is how much it
matters. A `hypothesis` can be a `blocker`. A `verified` finding can be a `nit`.

Collapsing them into a single severity number is the most common reporter bug, and it
fails in a specific direction: uncertain-but-serious findings get downgraded to nits
because the reporter could not fully confirm them.

## Merge-decision ladder

Reporters propose `merge_impact`; the orchestrator decides the verdict. One rule,
applied in order — the first match wins:

| Condition | Verdict |
|---|---|
| Any finding with `merge_impact: blocker` | `request_changes` |
| Any finding with `merge_impact: important` | `comment` |
| Otherwise | `approve` |

Questions never block on their own. A finding that cannot be evaluated without more
information is `evidence.state: question` and `comment_type: question` — the reviewer
asks rather than rejects.

## Reporter contract

Any new reporter must:

1. Emit findings matching `finding-schema.md` exactly — including `severity.source_native`
   preserved verbatim. **Never rewrite another system's severity codes.**
2. Classify every finding into exactly one evidence state before returning it, having
   run the self-verification protocol in `evidence-model.md`.
3. Claim a unique `id` prefix (`AK`, `AW`, `SY`, …) so merged findings stay traceable to
   their source.
4. Report only — never fix findings inline. The orchestrator decides what gets acted on.

A reporter that self-verifies is doing its own job; the orchestrator does not re-verify
from scratch. It reconciles conflicts and combines cross-reporter evidence. Assigning the
correct evidence state is the **reporter's** responsibility, not the orchestrator's.
