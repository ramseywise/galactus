# knowledge-graph: design

**Thesis.** Checking that a quote is verbatim, that a type exists, or that a build stayed
under budget is a job for code. The model's job is to propose a triple and to judge whether
its quote supports it. Everything a model returns crosses a gate that code owns.

## The pipeline

```
profile ─► propose ─► gates ─► judge ─► route ─► store ─► promote ─► ask
 (code)    (Haiku)   (code)   (seat)   (code)   (code)   (human)   (code + Librarian)
```

1. **Profile** (`kg/profile/`). A census of the domain: pages, estimated tokens, a profile hash
   over the normalised bodies, and a cost estimate whose basis string names each assumption.
   A build is refused before any spend when the domain is empty or over the ceiling.
2. **Propose** (`kg/propose/`). One structured-output call per page or chunk, with an enum
   schema built from the pack. Every failure becomes `not_run` with a reason; an empty result
   is `no_candidates`, never confused with the first.
3. **Gates** (`kg/gates/`). Four pure functions: the quote is verbatim and unique in the
   normalised body, both entities are attested in the quote, the types and relation conform to
   the pack, and the triple is not a duplicate. A gate failure is a recorded reason, not a
   judge call.
4. **Judge** (`kg/judge/`). A blind seat sees the triple and a ±400-character evidence window,
   never the proposer's reasoning, and returns a label and a score in [0, 1] or `NotRun`.
5. **Route** (`kg/route/`). Two thresholds priced from the cost of each route (Chow's reject
   option with an imperfect reviewer). Accept above `t_hi`, reject below `t_lo`, review
   between, and review for `unclear` or a label that contradicts its score. A band rate above
   0.40 halts the build.
6. **Store** (`kg/store/`). Mentions, triples keyed canonically, evidence and judgements, per
   build. Default reads see promoted builds and the accept tier only.
7. **Promote** (human). Only a complete build promotes; decisions live in `docs/decisions/`,
   outside the store, so deleting the store cannot lose them.
8. **Ask** (`kg/retrieve/`). Librarian's ranked search finds entry pages, surface forms match
   entities in the store, at most two hops expand, and each passage's quote is re-checked
   against the current body at serve time, so freshness is honest.

## Seams

Each seam is a Protocol with a scripted fake, so the whole pipeline runs with no network.

| Seam | Protocol | Implementations | Unavailable means |
|---|---|---|---|
| Proposer | `kg.propose.proposer.Proposer` | `AnthropicProposer`, `ScriptedProposer` (tests) | `ANTHROPIC_API_KEY` unset, refused by name |
| Judge | `kg.judge.seat.JudgeSeat` | `ClaudeSeat`, `JevSeat` (OpenRouter), `ScriptedSeat` | `available()` returns `(False, reason)` |
| Store | `kg.store.protocol.GraphStore` | `SqliteStore`, `Neo4jStore` | `NEO4J_URI` unset, refused by name |
| Baseline | `kg.retrieve.Baseline` callable | Librarian probe subprocess | `LIBRARIAN_ROOT` missing, `BaselineError` |

Galactus never imports Librarian. The probe runs in Librarian's own environment as a
subprocess (`uv run --project $LIBRARIAN_ROOT python -I`) and returns JSON, with its own
in-process timing.

## What code enforces and what the model fills

| Code enforces | The model fills |
|---|---|
| The pack's types, by hash; an edited pack is refused until re-approved | Which triples a page states |
| Quote verbatim and unique; entities attested in it | Whether the quote supports the relation |
| Score in [0, 1]; out of range is `schema_mismatch`, never clamped | The score |
| The ceiling before spend and the meter during it | — |
| Thresholds, from prices | — |
| Hop depth ≤ 2, accept tier by default, promoted builds only | — |
| Freshness, by substring check at serve time | — |

## Uncertainty

What the system does when it does not know:

- A model failure is `not_run`, never a reject.
- A judge that is unsure says `unclear`, which routes to a human.
- A rate with no denominator is `NotApplicable`, printed with its reason.
- A quote no longer in its page is `stale`, not served as fresh.
- A build that halts partway serves nothing.

Irreversible steps (spend and promotion) each sit behind a human: `KG_LIVE=1` and the
checklist in `spend-decision.md`, and `kg promote`.

## What we did not build

- A review UI. The review queue is a CLI table plus a decisions file.
- Cross-page entity merge. A node is a per-page mention in both stores; merging is a separate
  decision with its own eval.
- A chunk index. `ask` reuses Librarian's search for entry points.
- OntoSmith's serving app, OWL import and benchmarks (`case-study.md`).
