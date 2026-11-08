# Preregistration: SQLite vs Neo4j in the retrieval eval

Date: 2026-11-08. Written before the retrieval eval (Step B5) has run on either store.

## What is being compared

The same built graph, loaded into `SqliteStore` and `Neo4jStore` (Neo4j Community 5.x, local
Docker), queried through the identical `GraphStore` calls: `hops()` and `passages()` with
default filters (promoted builds, accept tier, k at most 2). Both stores use per-page
mention nodes and traverse by normalised surface key; `tests/test_kg_store_parity.py` checks
that equivalence on a fixture with one surface form repeated across two pages.

## Predictions

1. **Recall parity.** recall@5 per arm is equal between the two stores. The graph content,
   the filters and the traversal rule are the same, so any recall gap is not expected.
2. **Latency within noise.** At this scale (a few thousand triples, two hops) per-query
   latency is dominated by process and driver overhead, not the engine. Median latency
   differs by less than run-to-run variance across repeated runs of one store.
3. **A difference either way is a finding.** A recall gap means the stores are not
   equivalent and the cause (traversal rule, tier or build filtering, key normalisation) is
   investigated before any claim about retrieval. A latency gap beyond noise is reported
   with its size, not explained away. Neither outcome is a failure of the eval, and neither
   is tuned away before it is recorded.

## Not claimed

No claim is made about behaviour at larger scale, deeper hops (hard-capped at 2), or write
throughput. Neo4j parity is only measured when `NEO4J_URI` is set; without it the eval
refuses by name rather than reporting SQLite numbers as both.
