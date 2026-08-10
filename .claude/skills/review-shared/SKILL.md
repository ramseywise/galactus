---
name: review-shared
description: "Shared contracts for every review reporter — the canonical finding schema, the evidence model, the context brief, and the merge-decision ladder. Preloaded by the review and wander agents and used by /workflow-review rather than invoked directly. Load it when writing a new dimension or when two dimensions disagree about a finding's severity."
---

# review-shared

The contracts every review reporter writes against. This skill holds no procedure of its
own — it exists so that all ten `review-*` dimensions emit findings a single orchestrator
can merge without re-reading each dimension's private conventions.

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

Reporters propose `merge_impact`; the verdict is **computed** from those proposals by
`compute_verdict` in `review/verdict.py`, run via:

```bash
uv run python -m review.cli verdict < review.json
```

The ladder is a pure function with five rungs, first match winning. It is deliberately
**not** restated here: a prose copy drifts from the implementation, and a ladder that
silently disagrees with the code produces verdicts nobody can reproduce. Read
`review/verdict.py` when you need the rungs; run the CLI when you need a decision.

Two properties worth carrying without reading it:

- **An empty findings array is a real result**, not a failure. A dimension that looked
  and found nothing has passed cleanly. Only a dispatch that errored, returned malformed
  output, or never returned is `failed`.
- **Questions never block on their own.** A finding that cannot be evaluated without more
  information is `evidence_state: question` with `comment_type: question` — the reviewer
  asks rather than rejects.

## Reporter contract

Any new reporter must:

1. Emit findings matching `finding-schema.md` exactly — including `severity.source_native`
   preserved verbatim. **Never rewrite another system's severity codes.**
2. Classify every finding into exactly one evidence state before returning it, having
   run the self-verification protocol in `evidence-model.md`.
3. Carry the `id` prefix its dimension declares in `prefix:` frontmatter (`IN`, `CR`,
   `SI`, …), so merged findings stay traceable and a wrong-skill dispatch is detectable.
4. Report only — never fix findings inline. The orchestrator decides what gets acted on.

A reporter that self-verifies is doing its own job; the orchestrator does not re-verify
from scratch. It reconciles conflicts and combines cross-reporter evidence. Assigning the
correct evidence state is the **reporter's** responsibility, not the orchestrator's.
