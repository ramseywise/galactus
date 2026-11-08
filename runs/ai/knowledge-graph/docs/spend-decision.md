# Spend decision: the first live build

**Status:** not taken. No live model call has been made. **Who decides:** Ramsey.

Everything up to here runs with `--dry-run` and costs nothing. A live build spends money on
two models and writes triples that `ask` will serve once promoted. This page is the gate:
tick it in order, and stop at the first box that fails.

## Limits

| Limit | Value | Where it is enforced |
|---|---|---|
| Build ceiling (pre-build estimate) | `KG_BUILD_CEILING_USD`, default $10 | `refuse_if_over` before any call |
| Runtime meter | same ceiling, on metered tokens | `build.py` meter halts the build mid-run |
| Band rate halt | `KG_BAND_RATE_HALT`, default 0.40 | `halt_if_over`, the build ends `halted` |
| Live guard | `KG_LIVE=1` | `kg build` without `--dry-run`, `propose`, `repeat`, `evals/run.py --judge claude` |

The dry-run estimate for the whole `eval/` domain is **$3.31** (80 pages, ~105k tokens;
proposer $0.07, judge $3.24), assuming 10 candidates per call, a 75% gate survival rate and 20%
repair retries. The judge dominates, so the survival rate is the assumption to check first.

A halted build serves nothing: only promoted builds are read, and only a complete build
promotes.

## Checklist

1. [ ] **Model ids.** One request to each of `KG_PROPOSER_MODEL` and `KG_JUDGE_MODEL`. A
   `model_not_found` not-run here costs cents and saves the build.
2. [ ] **One page.** Build a single page and compare metered cost and candidate count against
   the estimate's per-page share and its 75% survival assumption. *Gap: `kg build` has no
   `--limit` yet; until it does, run `kg propose <page>` plus a one-page corpus root.*
3. [ ] **Threshold sides.** Judge one known-true and one known-false candidate (take them from
   the gold) and confirm the scores land above `t_hi` and below `t_lo`. At the default prices
   these are t_lo ≈ 0.448 and t_hi ≈ 0.881 (wrong accept 10, wrong reject 3, review 1,
   reviewer TPR 0.95 / FPR 0.05).
4. [ ] **Repeatability.** `kg repeat <page> --n 5`: Jaccard over canonical keys must be at
   least 0.8. Below that, a build is a sample, not a graph.
5. [ ] **Accept-tier precision.** Label 30 live proposer candidates and record the accept-tier
   precision with a Wilson interval in `docs/decisions/`. This is what should unlock
   `promote`. *Gap: `promote` does not check for this record yet (the note in `build.py`,
   fog FA-004). Until it does, this box is enforced by the operator, not by code.*
6. [ ] **Full build**, with every candidate routed to `review` until box 5 is recorded. *Gap:
   there is no force-to-review switch yet; until there is, do not promote before box 5.*

## Read these three numbers first

After any live build, before anything else in the report:

1. **Band rate**: the share of judged candidates routed to review. Near the 0.40 halt
   means the thresholds or the judge are wrong for this corpus.
2. **`not_run`**: pages and candidates that never got a verdict, with reasons. A large count
   is an outage or a schema problem, not a quiet corpus.
3. **Hard-negative precision**: from `evals/run.py` on the gold `test` split. Agreement is not
   precision; this is the number that says whether the judge separates a wrong relation from a
   right one.

## Not covered

Live retrieval evaluation (`evals/run.py --retrieval` without `--dry-run`) calls no paid
model but needs a promoted build to have anything to measure. Live judge calibration
(`--judge claude`) has no ceiling of its own beyond `KG_LIVE`. Decide its budget here when it
is first run.
