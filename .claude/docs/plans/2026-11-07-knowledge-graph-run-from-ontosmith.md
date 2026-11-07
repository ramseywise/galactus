# Knowledge-graph run — adapt the OntoSmith method into galactus

Status: READY
From: REFINED
Track: agent
Epistemic: NO_CONFLICT
Epistemic-by: fog
Epistemic-at: 2026-11-07
Epistemic-findings: 14
Date: 2026-11-07
Issue: — (none yet)
Source: `ontosmith/` clone at commit e68ca60 (2026-11-06), MIT, gitignored, not a dependency
Spec: `.claude/docs/specs/2026-11-07-knowledge-graph-run.md` (DRAFT, 2026-11-07)

Decided 2026-11-07 (Ramsey): OntoSmith is not adopted as a dependency. Galactus learns the
method and rebuilds it as a run under its own conventions.

Revised 2026-11-07 (Ramsey): Jev and a graph database are **optional seams, not exclusions**.
The run must let the judge seat be Claude or Jev, and the store be a relational file store or a
graph database, with both pairs evaluated on the same gold. Practising with graph databases is
a stated goal, for galactus first and possibly Librarian and the course later.

Track routing: the run calls models (a proposer and a judge) and fits none. Calibration bins
and threshold selection are measured parameters, not a trained model. `agent`, unambiguous.

**Two goals, in order.** The run is the vehicle, not the point.

1. **Improve the knowledge storage and retrieval behind the galactus prototyping agent.**
   `/proto-research` grounds in Librarian, which today retrieves chunks by hybrid search and
   expands one hop along author-typed page links. A judged, entity-grain graph with evidence
   spans is a candidate upgrade, and this run is where it gets measured against that path.
2. **Improve how future prototypes from this repo build knowledge graphs.** Today the only
   guidance is `cap-kg.md`, an untested Neo4j client template. The run becomes the tested
   reference the capability ref, the `/new-agent` references and the template's
   `/add-capability` path point at.

## Research

### Summary

Build the OntoSmith method as a small galactus run at the **triple grain** (entity, relation,
entity, verbatim quote), because that is the grain Librarian does not have: it already carries
6,821 author-typed **page-level** edges and expands retrieval along two of them, which the
first draft of this doc missed. The course notes confirm every stage of the method and add
three corrections: thresholds should be priced from the cost of each route rather than only
searched under a precision floor, judge quality is reported as TPR/TNR/κ against human labels
and never as seat agreement, and at this corpus size recursive SQL will match a graph store
on hops, so Neo4j is justified by the practice goal and the eval should say that in advance.

### Scope

Investigated: the OntoSmith clone's documents and module docstrings; the Librarian retrieval
code (`graph_expansion.py`, `format.py`, `index.py`); the wiki corpus by domain; the galactus
`experiments` module, `cap-kg.md`, `pyproject.toml` testpaths; six course-domain searches with
the notes they surfaced read in full. Out of scope: reading OntoSmith code bodies (the rebuild
is from the documents), calling the OpenRouter decisions route (no key set this session), any
benchmark other than the run's own gold.

### Smallest design

The least that meets the request as written (a rebuilt method, two optional seams, both
evaluated): a hand-written pack with a sha256 and an approval record; four pure-function gates;
a Haiku proposer at temperature 0; a Claude Sonnet judge behind a `JudgeSeat` protocol; a
two-threshold router; a SQLite store of mentions, triples, evidence and provenance behind a
`GraphStore` protocol; JSONL export; an `ask` that takes entry chunks from Librarian's existing
`search_text` and expands at most two hops; an eval harness with a hand-labelled gold.

Each component beyond that, with the failure it prevents and the evidence:

- **Jev seat.** Prevents a one-family judge measuring its own blind spots: two scorers with
  the same blind spot reached κ 0.93 with each other and 0.33 with humans
  (`course/generative-ai/08-eval/notes/15-calibration-against-human-labels.md`). Also a
  stated requirement.
- **Neo4j store.** Prevents no failure at this size: six hops over 500k edges run in
  milliseconds in recursive SQL
  (`course/data-engineering/01-storage-and-compute-foundations/notes/10-choosing-a-store.md`).
  It is in because practising with a graph database is a stated goal, and the eval's
  pre-registered expectation is parity on results with a latency difference either way.
- **Profile (census).** Prevents an unpriced build: the judge spend is linear in surviving
  candidates and only a count before spend can refuse by name (my reasoning; the spec's
  ceiling rule depends on it).
- **Review queue as a CLI table, not a UI.** Prevents nothing a UI would not; it is the cheaper
  form. A UI is in Test later.

### Findings

Each finding answers one decision the planner must make.

**F1 — Grain: build at the triple grain, keep Librarian's page edges as weak gold and baseline.**
Confidence: High. Librarian already has typed, author-asserted page edges: 735 at the 2026-08-06
pin and 6,821 at today's index build (`librarian/src/librarian/retrieval/graph_expansion.py:1-30`,
index log `typed_edges=6821`), and it expands retrieval along `prerequisite-for` and `extends`
(`graph_expansion.py:36`). What it lacks is anything below the page: no entities, no typed
relation between two named things, no evidence span, no judged edge. The run's value is that
grain. The page edges are a free weak gold for the retrieval eval (does a question about page
A reach pages A's typed neighbours?) and the baseline arm must run **with** expansion on,
because that is what `/proto-research` uses today.

**F2 — Pipeline shape: extract cheap into mentions, judge strong, assemble deterministically,
let the eval block the load.** Confidence: High. The course's pipeline is the same seven stages
OntoSmith has, with the same model tiering: Haiku-class extraction into schema-constrained
output, Sonnet-class for the judgement step, nothing but code for assembly, and a gold-set
evaluation that "blocks the load if it regresses"
(`course/ai-engineering/05-graph-engineering/notes/10-building-kgs-with-llms.md`, pipeline
table). Its rule "create, not merge: one `Entity` per mention per page; resolution writes
similarity edges on top" means the store keeps **mentions**, and entity resolution across pages
is a later stage, not an extraction-time merge. That is what makes ER deferrable (Test later).

**F3 — Judge seat: treat each seat as an instrument calibrated on human labels; report TPR,
TNR and κ; never report agreement as quality.** Confidence: High. The course's procedure is
100–200 human labels with both classes, split train/dev/test, confusion matrix on dev, measure
test once, pin model and prompt version, re-calibrate on any change
(`.../15-calibration-against-human-labels.md`, "The procedure"). Raw agreement exceeded κ by
34–41 points across 21 judges; a repeatable judge "reproduces its bias exactly". The run's gold
is therefore split, the ECE bins are kept but κ leads, and the five repeats measure
test–retest, which is a separate number from validity. Multi-family judging is the course's
mitigation for self-preference, which is the course-side reason for the Jev seat.

**F4 — Route: price the three routes and let the thresholds follow; report the risk–coverage
curve.** Confidence: High. The course derives `t_lo` and `t_hi` from the cost of a wrong
accept, a wrong reject, one review, and the reviewer's own catch and false-alarm rates
(`course/data-science/01-classical-ml/notes/13-automate-review-or-reject.md`, "Price each route
and the thresholds follow", Chow 1970). On its generated data the priced two-threshold policy
beat one threshold by 2.49 per item across 20/20 seeds. OntoSmith's operating point (minimum
review rate at a 0.90 auto-precision floor) is one point on that curve. The run should state the
prices (a wrong accept reaches a plan doc; a review costs a minute of Ramsey's time; a wrong
reject costs one triple's coverage), compute the thresholds from them, and report the curve so
the floor and the priced point can both be read. Vocabulary to adopt: straight-through rate
(coverage), selective risk (error on the auto-accepted share), human correction rate.

**F5 — Store: pre-register parity.** Confidence: High on the guidance, Medium on the outcome.
The course's store-choice note puts graph stores where "long chains of links dominate" and
shows recursive SQL reaching six hops over 100k nodes and 500k edges in about 15 ms, degrading
to 4.4 s only at 3M edges (`.../10-choosing-a-store.md`, "As a graph store"). A one-domain
build here is thousands of edges. So SQLite with a recursive CTE is expected to tie Neo4j on
recall and be within noise on latency, and the Neo4j arm's value is the practised seam, its
constraint-plus-`MERGE` idempotent load pattern
(`course/ai-engineering/05-graph-engineering/notes/10b-assembling-and-maintaining-kgs.md`,
L3–L6), and a full-text index for entity entry. Writing the expected result down before the
eval makes a surprise a finding rather than a preference.

**F6 — Retrieval: hybrid mode, hops ≤ 2, return passages not triples, expect a modest gain.**
Confidence: High on the mode, Low on the size of any gain. The course reads the GraphRAG
evidence as "most of the win comes from going global, not from the graph", notes there is "a
lack of benchmark standards", and recommends hybrid retrieval (vector entry, graph expansion)
for text-heavy corpora with canned traversals for the question shapes you can name
(`course/ai-engineering/05-graph-engineering/notes/11-kg-rag-and-text-to-cypher.md`,
"Retrieval modes", "Default order"). Two more rules bind the design: per-hop error compounds
as pⁿ (85% per hop is 44% at five hops), so `k` defaults to 1 and caps at 2; and "triples lose
meaning" (the beach-trip example), so `ask` returns chunk-plus-edge passages, never bare
triples. The spec's ≥ 10-point recall@5 bar for a goal-1 gain is strict against this evidence
and should stay strict.

**F7 — First domain: `eval/`.** Confidence: Medium. Page counts today: `foundations` 442,
`patterns` 370, `eval` 80, `infra` 67, `meta` 41, `prompting` 36, `interview` 35, `rag` 34,
`harness` 31, `private` 9 (excluded). `eval/` is 80 pages and 656 KB, inside the $10 build
ceiling at the spec's arithmetic, and the course's eval chapter gives a ready source of
retrieval questions and a human (Ramsey) who knows the material well enough to label it.
`graph/` at 13 pages is the fallback if the first build busts the band-rate halt.

**F8 — Gold: hand-labelled at the triple grain with hard negatives, plus page-edge weak gold
for retrieval.** Confidence: High. Course 15 wants 100–200 human labels with both classes and
a split; the spec adds ≥ 30 hard negatives (verbatim quote, right entities, wrong relation) and
≥ 5 quoted-instruction controls after the dry run showed shuffled negatives never reach the
judge. The bootstrapped pool stays separate. For retrieval, the typed page edges (F1) are a
weak gold that costs nothing and tests the baseline arm on its own terms.

**F9 — Proposer stability: temperature 0 plus a repeat test and prompt unit tests.**
Confidence: Medium-High. The course's extraction lessons: temperature 0 "does not make output
stable", so run the same page several times and compare; keep (snippet → expected triples)
unit tests and run them on every prompt change; do not trust model character offsets,
recompute spans deterministically (`.../10-building-kgs-with-llms.md`, "Lessons from ch. 5").
The verbatim gate already recomputes offsets; the stability check and prompt tests are new
test-suite items, not new components.

### Course grounding

Librarian's MCP server failed to connect this session (CONNECTION_CLOSED), so the queries below
were run through the same function the `search_wiki` tool calls,
`librarian.retrieval.format.search_text(query, domain="course")`, from the Librarian repo.

- query: `knowledge graph construction from documents with LLM extraction and evidence` (domain=course) → 5 hits
  - used: course/ai-engineering/05-graph-engineering/notes/10-building-kgs-with-llms.md
  - used: course/ai-engineering/05-graph-engineering/notes/09-kg-fundamentals-and-cypher.md
- query: `GraphRAG graph retrieval versus chunk retrieval recall` (domain=course) → 5 hits
  - used: course/ai-engineering/05-graph-engineering/notes/11-kg-rag-and-text-to-cypher.md
  - used: course/ai-engineering/02-context-engineering/notes/04-retrieval.md
- query: `LLM as judge calibration controls hard negatives` (domain=course) → 5 hits
  - used: course/generative-ai/08-eval/notes/15-calibration-against-human-labels.md
  - used: course/generative-ai/08-eval/notes/04-graders.md
- query: `human review band abstention threshold precision floor` (domain=course) → 5 hits
  - used: course/data-science/01-classical-ml/notes/13-automate-review-or-reject.md
- query: `graph database Neo4j versus relational SQL traversal` (domain=course) → 5 hits
  - used: course/data-engineering/01-storage-and-compute-foundations/notes/10-choosing-a-store.md
  - used: course/ai-engineering/05-graph-engineering/notes/10b-assembling-and-maintaining-kgs.md
- query: `ontology schema entity relation types extraction contract` (domain=course) → 5 hits
  - used: course/ai-engineering/05-graph-engineering/notes/10-building-kgs-with-llms.md

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| OntoSmith method (pack, proposer/judge, gates, route, profile, priced build, conformance record, adjudication) | ADAPT | — | Written from the whitepaper and docs, not the code; cited in `docs/case-study.md` and `THIRD_PARTY.md` |
| Jev as judge seat | ADAPT as optional | — | One request shape to one endpoint; under 100 lines. Off without `OPENROUTER_API_KEY`, and the run says so by name. Course-side reason: multi-family judging (F3) |
| Neo4j as store | ADAPT as optional | — | Protocol-backed, Docker-local. Justified by the practice goal; parity pre-registered (F5) |
| `packs/*/pack.json` + `pack.schema.json` | ADAPT | — | Field list is the checklist for the Pydantic contract; the JSON Schema and hand validator are not taken |
| `docs/ADJUDICATION.md` protocol | REUSE as protocol | — | A judging protocol is not code; seam rulings are domain-specific and not taken |
| OntoSmith serving app and UI | SKIP | Nothing. The `kg://` citation idea it would need is already in `cap-kg.md` | Product, not method |
| OntoSmith OWL import | SKIP | Nothing for a hand-written pack | Out of scope by decision |
| OntoSmith benchmark harness (DocRED, BioRED, CUAD) | SKIP | The shape of a conformance record is already taken under the method row | Benchmarks are not ours; the run's gold is |
| OntoSmith `configure` wizard, dialects, Linux packaging | SKIP | Nothing; `config.py` with two env-var keys does the job | Infrastructure |
| The clone itself | Keep out of tree | — | Move to `~/workspace/ontosmith`; still pending |
| Librarian `retrieval/graph_expansion.py` | REUSE | — | Baseline arm with expansion on, and the typed edges as page-level weak gold (F1) |
| Librarian `retrieval/format.search_text` | REUSE | — | Entry-point chunk retrieval for `ask`; avoids building a second chunk index |
| `cap-kg.md` | ADAPT | — | Keep the `graph_to_passages()` seam and `kg://` scheme; drop the untested client with its two noted bugs (`cap-kg.md:11,13`) |
| `experiments` module (`RunRecord`, `NotApplicable`, `capture_code_state`, `fingerprint_frame`) | REUSE | — | `experiments/record.py:32,129`, `provenance.py:74`; `fingerprint_frame` is frame-shaped, so the corpus fingerprint is the profile hash instead |
| marketing-comms `layout/contract.py` + `guardrails/validator.py` pattern | ADAPT | — | Same thesis: code enforces, model fills; the run mirrors the layout so `/proto-harden` applies |
| Anthropic KG construction cookbook (cited by course note 10) | REUSE as reference | — | Same Haiku-into-Pydantic extraction shape; read, not vendored |
| `langchain_experimental` `LLMGraphTransformer` | SKIP | The idea of returning structured nodes and relationships rather than Cypher, which the design already does | Adds a dependency for a shape Pydantic gives |

### Assumptions

- **Assumption:** the two judge seats are comparable on the same gold — **Evidence:** none yet; the whitepaper reports Jev-only precision and no frontier comparison — **If wrong:** one seat becomes default and the other stays documented; the spec survives — **Confidence:** Low. First item for `/assumption-audit`.
- **Assumption:** an entity-grain graph improves `/proto-research` retrieval over Librarian search with page-edge expansion — **Evidence:** course 11 says the published GraphRAG wins are mostly from global summarisation, not the graph — **If wrong:** the number is recorded, Librarian stays as is, goal 2 stands — **Confidence:** Low.
- **Assumption:** SQLite recursive queries tie Neo4j on results at one-domain scale — **Evidence:** course DE 10 timings — **If wrong:** Neo4j becomes the default store and the reason is measured — **Confidence:** Medium-High.
- **Assumption:** the gold is the real cost — **Evidence:** OntoSmith's records rest on public benchmarks; galactus has none; course 15 wants 100–200 labels — **If wrong:** nothing bad; the build gets cheaper — **Confidence:** High.
- **Assumption:** `eval/` at 80 pages fits the $10 ceiling — **Evidence:** spec arithmetic (~$0.60 proposer, ~$7–9 judge on ~1,500 survivors) — **If wrong:** the priced build refuses by name and the domain shrinks to `graph/` — **Confidence:** Medium.
- **Assumption:** the typed page edges are a usable weak gold for retrieval — **Evidence:** 6,821 edges today, author-asserted, covering most pages at the 2026-08 pin — **If wrong:** the retrieval eval uses hand-written questions only — **Confidence:** Medium.

### Disconfirming Evidence

- *Librarian already does this.* **Looked, and partly found it.** Librarian has author-typed page edges and expands along two relation types. The first draft of this doc said it had "no typed relations"; that was wrong at the page grain. It remains true at the entity grain: no entities, no evidence spans, no judged edges. F1 is the correction.
- *The 2026-11-04 plan already rejected a knowledge graph.* Looked: it rejected a graph **for skill routing**, because the eval showed no routing errors. This run does not touch routing. Stands.
- *Graphs do not beat vectors.* Looked, and the course agrees in the general case (F6). The run's claim is narrower: entity-grain, evidence-backed expansion on a corpus the agent already searches. The ≥ 10-point bar is the test, and "no gain" is an expected and recorded outcome.
- *A graph database is unjustified at this size.* Looked, and it is unjustified **by performance** (F5). It is justified by the stated practice goal, and the doc now says so rather than implying a performance case.
- *The two-threshold band is OntoSmith-specific.* Looked: it is Chow (1970) and the course teaches it with priced thresholds; the run should price, not just floor (F4).
- *This duplicates `cap-kg.md`.* Looked: `cap-kg.md` is an untested client template with two bugs noted in its own header and no proposer, gates, judge or route. This run is what that ref should point at.

### Key Unknowns

- Per-seat TPR, TNR, κ and test–retest on the hard control pool; seat agreement as a descriptive number only.
- Review-band rate on `eval/` at the priced thresholds and at the 0.90 floor. Above 0.40 the build halts; whether that fires is unknown until the first build.
- Whether OpenRouter's alpha decisions route is reachable and returns usage; the Jev seat must degrade to `unavailable` by name.
- Retrieval recall@5 and p95 latency per store against the baseline arm with expansion on.
- Whether the half-day gold-labelling budget is accepted (spec's one open question).
- How many `eval/` pages exceed the ~6k-token split threshold (the profile answers this at zero cost).

### Test later

- **Cross-page entity resolution.** Signal: `inspect` shows the same entity under more than ~10% alias variants, or hop-2 precision falls well below hop-1 (course 10: resolution is the load-bearing step for multi-hop).
- **Vector index inside the store.** Signal: entity entry by exact surface form and alias table misses on more than ~20% of eval questions. Until then Librarian's chunk search is the entry point.
- **Text-to-Cypher.** Signal: a question shape the canned traversals cannot express appears repeatedly in `/proto-research` traces. Course 11: only with a validator, and last.
- **Community summaries (global GraphRAG).** Signal: whole-corpus questions ("what are the themes across eval?") appear in the traces. Course 11: that is where the published gains are, and it is a different product.
- **Quote re-verification at `ask` time.** Signal: `stale: true` on passages the agent actually cited.
- **A review UI.** Signal: more than one reviewer, or band sizes a CLI table cannot be read in.
- **Model-drafted pack.** Signal: a second corpus with no hand-written schema.

### Recommendation

Build one run, `runs/ai/knowledge-graph/`, at the triple grain: a hand-written, hash-pinned
pack; four pure gates; a Haiku proposer into mentions; a `JudgeSeat` with Claude first and Jev
as a multi-family second seat; a priced two-threshold router that also reports the floor-based
point and the risk–coverage curve; a `GraphStore` with SQLite first and Neo4j as the practised
seam with parity pre-registered; `ask` as hybrid retrieval that enters through Librarian's
existing search and expands at most two hops into passages. Evaluate on a hand-labelled gold
with hard negatives, split train/dev/test, reporting TPR/TNR/κ per seat, and a retrieval eval
against Librarian with page-edge expansion on, using the typed page edges as weak gold. Start
on `eval/`, keep the source under about 3,000 lines, and treat "no retrieval gain" as a
recorded result, not a failure.

## Decisions (accepted 2026-11-07, recorded as resolved)

| # | Question | Resolved as |
|---|---|---|
| Q1 | First corpus | Librarian `data/wiki/`, minus `private/`; first domain `eval/` (F7) |
| Q2 | Gold source | Hand-labelled (~100 positives, ≥ 30 hard negatives, ≥ 5 quoted-instruction controls) and judge-bootstrapped, two pools, never merged; page-edge weak gold for retrieval |
| Q3 | Store | Both behind `GraphStore`; SQLite first, Neo4j second; parity pre-registered |
| Q4 | Judge seat | Both behind `JudgeSeat`; Claude Sonnet first, Jev when a key is set; five repeats per seat for test–retest |
| Q5 | Clone location | Move to `~/workspace/ontosmith` (pending) |
| Q6 | Neo4j hosting | Local Docker, Neo4j Community 5.x, in the run's `docker-compose.yml` |
| Q7 | Retrieval baseline arm | Librarian `search_text` with page-edge expansion on, as `/proto-research` uses it today |

## Proposed shape (input to `/proto-plan`, not a plan)

Mirrors `runs/ai/marketing-comms/` so `/proto-harden` applies unchanged. Revised after the spec
dry run (F1–F8 there) and this research.

```
runs/ai/knowledge-graph/
  src/
    contract/   schema.py (Pydantic: EntityType, RelationType, definition, boundary examples;
                sha256 pin; loader refuses drift), approve.py (approval record bound to hash)
    profile/    census.py (deterministic corpus inventory, split flags, profile hash; no model)
    propose/    proposer.py (Haiku, temperature 0; mentions with verbatim quote; Pydantic output)
    gates/      quote_verbatim.py, attested.py, schema_conform.py, dedupe.py (pure; run on the
                normalised body, normalisation rule hashed into the profile)
    judge/      seat.py (JudgeSeat: supported | not_supported | unclear, score, usage),
                claude.py, jev.py (unavailable-by-name without a key),
                calibration.py (TPR, TNR, κ, test–retest, ECE bins, per seat, on the test split)
    route/      prices.py (route costs → t_lo, t_hi), tiers.py (accept | review | reject;
                risk–coverage curve), review_queue.py (CLI table)
    store/      protocol.py (GraphStore: write mention/triple with evidence and provenance,
                hops(entities, k, tiers), passages(..., tiers)), sqlite.py, neo4j.py,
                export.py (JSONL; Obsidian markdown), passages.py (graph_to_passages seam)
    retrieve/   hybrid.py (Librarian search_text entry → entity match → ≤2 hops → passages
                with tier, build_id, stale flag)
    observability/  structlog per stage; PageResult.status ∈ {proposed, no_candidates, not_run};
                cost stamped with basis or NotApplicable
    cli.py      profile | approve | propose | build | inspect | review | promote | unpromote | verify | repeat | ask ;
                every command has --dry-run
  evals/        gold/ (hand-labelled, split), bootstrapped.jsonl, questions.jsonl,
                run.py (dry-run adapter, --json, --judge claude|jev, --store sqlite|neo4j;
                refuses an unavailable seat or store rather than skipping)
  tests/        added to testpaths in pyproject.toml in the first slice; Neo4j tests skip
                without NEO4J_URI and the skipped count is printed
  docker-compose.yml   Neo4j Community 5.x
  docs/         DESIGN.md, case-study.md (what came from OntoSmith, cited), THIRD_PARTY.md
```

Metrics the harness reports, each with its denominator, seat and store named: gate pass rate;
`not_run` pages; per-seat TPR, TNR, κ, test–retest and ECE on the hard pool; seat agreement
(descriptive); straight-through rate and selective risk at the priced thresholds and at the
0.90 floor; grounding (must be 100%); cost per 100 accepted triples with basis; retrieval
recall@5, grounding rate and p95 latency per store against the baseline arm.

## Route through the bands

1. **Housekeeping, no band.** Move the clone (Q5). Add the run's test dir to `testpaths` the
   moment it exists.
2. **FRAME:** done. Spec at `.claude/docs/specs/2026-11-07-knowledge-graph-run.md`.
3. **BUILD:** `/proto-plan`, `/proto-refine`, then `/proto-execute` in slices ordered by spend
   and dependency: contract and profile (no API) → gates (no API) → SQLite store and export →
   proposer and Claude judge (capped) → priced route → **eval harness with the hand gold** →
   Jev seat → Neo4j store and the retrieval eval → CLI polish. Live spend cap for the whole
   build: about $30 across both seats; $10 per build, refused before spend.
4. **CROSS, at two points:** `/assumption-audit` on seat comparability before `/proto-plan`;
   `/fog` on the route stage before `/proto-execute`.
5. **REVIEW:** `/proto-harden`, then `/proto-review` before the first commit.
6. **Feed back, after COMPLETE, one track per goal.**
   - *Goal 1:* if recall@5 gains ≥ 10 points over the baseline arm, Librarian gains a
     graph-aware retrieval path (its own plan doc, in its repo) and `/proto-research` grounding
     cites triples with evidence spans. If not, the number is recorded and Librarian stays.
   - *Goal 2:* `cap-kg.md` is rewritten around the run's tested seams; the `/new-agent`
     references point at the run; the template's `/add-capability` catalog gains a `kg` entry;
     `agent-uncertainty.md` gains the priced review-band pattern with numbers; the course's
     graph-engineering notes get a note citing the whitepaper and this run.

## Out of scope for the first run

Entity resolution across pages, ontology import from OWL, schema drafting by a model, the
serving app and UI, text-to-Cypher, community summaries, more than two provider bindings, any
store beyond the two named, a full-corpus build, and any benchmark other than the run's own gold.

## Plan
Date: 2026-11-07
Based on: `## Research` above, the spec at `.claude/docs/specs/2026-11-07-knowledge-graph-run.md`,
and direct inspection of `runs/ai/marketing-comms/`, `experiments/`, `pyproject.toml`, and
Librarian's `retrieval/ranking.py` and `retrieval/graph_expansion.py`.

Baseline (2026-11-07, `main`, clean apart from the two staged docs and an unstaged `.gitignore`
edit): `uv run pytest --tb=no -q` → 1133 passed, 6 skipped.

### Goal

A recorded recall@5 number that says whether an entity-grain, evidence-backed graph earns a
place in `/proto-research` grounding, produced by a run that `cap-kg.md` and `/new-agent` can
point at as the tested way to build one.

### Open Questions

Resolved with Ramsey on 2026-11-07, before any step was drafted:

1. **Goal** — both goals as stated in the research, in that order. *Resolved: yes.*
2. **Plan shape** — one plan doc, two phases with a review boundary. Phase A ends at a
   verifiable state: the whole pipeline runs end to end on the dry-run adapter against the
   `eval/` corpus, with the eval harness computing every metric from scripted verdicts and
   fixture gold. Phase B adds the Jev seat, the Neo4j store, the Librarian baseline and the
   retrieval eval. *Resolved: two phases.*
3. **Gold budget** — about two hours of Ramsey's time, not half a day. Targets drop to
   ~50 positives, ≥ 15 hard negatives, ≥ 5 quoted-instruction controls. The plan states that
   κ confidence intervals at n≈70 will be wide and the report prints them. *Resolved: 2 h.*
4. **Spend** — **dry-run only in this plan.** Live adapters for Haiku, Sonnet and Jev are
   written and request-shape tested against fakes, but no step calls a paid API. The first
   live `eval/` build is a separate decision after `/proto-review`, recorded in
   `docs/spend-decision.md` by Step B6. *Resolved: dry-run only.*

Defaults the plan assumes and the reviewer should confirm or overturn:

5. **Package name and import path.** `runs/ai/marketing-comms/src` sits on `pythonpath` with
   bare module names (`config`, `store`, `models`). A second run with a bare `config.py` would
   shadow it. The new run is a package, `runs/ai/knowledge-graph/src/kg/`, imported as
   `kg.<module>`, with `runs/ai/knowledge-graph/src` added to `pythonpath`. *Default: `kg`.*
6. **Pack authorship.** Step A2 has execute draft `packs/eval-v1.json` from the `eval/`
   pages' titles and tags; Ramsey edits and approves it with `kg approve`, which writes the
   approval record bound to the hash. Nothing builds against an unapproved pack.
   *Default: execute drafts, Ramsey approves.*
7. **Determinism claim corrected.** The research says "temperature 0". Current Anthropic
   models reject sampling parameters (`gateway.py:27-29`), so the proposer has no temperature
   knob. Stability comes from the gates and the repeat test (research F9), not from a
   parameter. *Default: drop the knob, keep the test.*
8. **Corpus and Librarian location.** `KG_CORPUS_ROOT` defaults to
   `~/workspace/librarian/data/wiki`; `LIBRARIAN_ROOT` defaults to `~/workspace/librarian`.
   Both are read at `Settings.load()`; a missing path refuses by name. The baseline arm calls
   Librarian in a subprocess (`uv run --project $LIBRARIAN_ROOT python -I <script>`) and
   reads JSON back, so galactus never imports Librarian. *Default: env vars + subprocess.*
9. **Neo4j driver dependency.** Added as a uv dependency group `kg = ["neo4j>=5"]`, not to
   `default-groups`, so `uv sync` stays unchanged for everyone else. *Default: optional group.*
10. **Model ids.** `KG_PROPOSER_MODEL=claude-haiku-5-5`, `KG_JUDGE_MODEL=claude-sonnet-5-5`,
    both overridable. *Default: current Haiku and Sonnet.*

### Approach

Mirror `runs/ai/marketing-comms/` closely enough that `/proto-harden` applies unchanged: a
`Settings.load()` that works with no key, a narrow provider Protocol with one real adapter
and one scripted fake, pure validators that code enforces, an `evals/run.py` whose `--dry-run`
path exercises everything, and tests that script the fake rather than mock the SDK. Build
the deterministic core first (contract, normalisation, gates, store) so most of Phase A
never touches a model, then the two model seams behind Protocols, then the router and the
build orchestration, then the eval harness. The key tradeoff: writing live adapters that
this plan never runs means the first live build will surface request-shape and cost
surprises that a dry run cannot. That is accepted in exchange for a plan that spends
nothing, and Step B6 records the live build as the next decision.

### Out of Scope

- Any paid API call. Live adapters are written and shape-tested, not executed.
- Cross-page entity resolution, OWL import, model-drafted packs, text-to-Cypher, community
  summaries, a serving API or UI, Neo4j Aura or any hosted store.
- Changes to Librarian. The baseline arm reads Librarian; nothing writes to it.
- Rewriting `cap-kg.md`, the `/new-agent` references or `agent-uncertainty.md`. Those are
  the goal-2 feedback after `COMPLETE`, in their own plan doc.
- A full-corpus build. One domain, `eval/`, 80 pages.
- A fixed pack for any domain other than `eval/`.
- Moving the `ontosmith/` clone (housekeeping, not a step).

---

### Phase A — the pipeline, end to end on the dry-run adapter

#### Step A1: Scaffold the run, register it with pytest, settings that load without a key
**Files**: `pyproject.toml` (testpaths lines 112–121; pythonpath line 127; dependency-groups
lines 24–35); new `runs/ai/knowledge-graph/src/kg/__init__.py`, `src/kg/config.py`,
`tests/__init__.py`, `tests/conftest.py`, `tests/fakes.py`, `tests/test_config.py`,
`.env.example`, `README.md` (stub).
**What**: Create the package. `Settings.load()` reads `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`,
`NEO4J_URI`, `KG_CORPUS_ROOT`, `LIBRARIAN_ROOT`, `KG_PROPOSER_MODEL`, `KG_JUDGE_MODEL`,
`KG_BUILD_CEILING_USD` (10), `KG_BAND_CEILING_USD` (30), `KG_BAND_RATE_HALT` (0.40),
`KG_MAX_HOPS` (2), `KG_DB_PATH`. Keys are optional at load; `require_anthropic_key()`,
`require_openrouter_key()`, `require_neo4j_uri()` are the explicit gates and name the missing
variable. `fakes.py` holds `ScriptedProposer` and `ScriptedSeat` stubs that later steps fill
in. Add the test dir to `testpaths` and the src dir to `pythonpath`. Add the `kg` dependency
group with `neo4j>=5` via `uv add --group kg neo4j`.
**Snippet**:
```toml
# before (pyproject.toml testpaths)
    "evals/prototyping/tests",
]
# after
    "evals/prototyping/tests",
    "runs/ai/knowledge-graph/tests",
]
...
pythonpath = [".", "runs/ai/marketing-comms/src", "runs/ai/marketing-comms",
              "runs/ai/knowledge-graph/src"]
```
```python
# src/kg/config.py — after
@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    openrouter_api_key: str | None
    neo4j_uri: str | None
    corpus_root: Path
    librarian_root: Path
    proposer_model: str = "claude-haiku-5-5"
    judge_model: str = "claude-sonnet-5-5"
    build_ceiling_usd: float = 10.0
    band_ceiling_usd: float = 30.0
    band_rate_halt: float = 0.40
    max_hops: int = 2
    def require_openrouter_key(self) -> str:
        if not self.openrouter_api_key:
            raise ConfigError("OPENROUTER_API_KEY is not set; the Jev seat is unavailable")
        return self.openrouter_api_key
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_config.py -v` and
`uv run pytest --co -q | grep -c knowledge-graph` (must be > 0).
**Done when**: the new dir collects tests under a bare `uv run pytest`; `Settings.load()`
succeeds with no env set and each `require_*` raises naming its variable; the full suite is
still 1133 passed.

#### Step A2: Contract — hash-pinned pack and approval record
**Files**: new `src/kg/contract/__init__.py`, `src/kg/contract/schema.py`,
`src/kg/contract/approve.py`, `packs/eval-v1.json`, `tests/test_contract.py`.
**What**: Pydantic v2 models: `EntityType(name, definition, boundary_examples: list[str])`,
`RelationType(name, definition, domain: str, range: str, boundary_examples)`, `Pack(name,
version, entity_types, relation_types)` with `extra="forbid"`. `pack_hash(pack) -> str` is
sha256 over canonical JSON (sorted keys, no whitespace). `load_pack(path, expected_hash=None)`
raises `PackDrift(expected, actual)` on mismatch. `approve.py` writes
`packs/<name>.approval.json` = `{pack_hash, approved_by, approved_at}`; `require_approved(pack)`
refuses a pack whose approval hash differs. Draft `eval-v1.json` with ~6 entity types
(Metric, Method, Artifact, Failure mode, Tool, Role) and ~6 relations (measures, mitigates,
requires, produces, contradicts, instance-of) from the `eval/` page titles and tags; Ramsey
edits and approves it with `kg approve packs/eval-v1.json` (CLI lands in A7; until then a
one-line `python -c` call documented in README).
**Snippet**:
```python
# after — contract/schema.py
def load_pack(path: Path, expected_hash: str | None = None) -> Pack:
    pack = Pack.model_validate_json(path.read_text())
    actual = pack_hash(pack)
    if expected_hash is not None and actual != expected_hash:
        raise PackDrift(expected=expected_hash, actual=actual)
    return pack
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_contract.py -v`
**Done when**: a one-character edit to a boundary example changes the hash and `load_pack`
with the old hash raises `PackDrift`; an unknown field is rejected; `require_approved` refuses
an unapproved pack; `eval-v1.json` validates and has an approval record authored by Ramsey.

#### Step A3: Normalisation, profile (census) and the four gates
**Files**: new `src/kg/profile/__init__.py`, `src/kg/profile/normalise.py`,
`src/kg/profile/census.py`, `src/kg/gates/__init__.py`, `src/kg/gates/quote_verbatim.py`,
`src/kg/gates/attested.py`, `src/kg/gates/schema_conform.py`, `src/kg/gates/dedupe.py`,
`src/kg/models.py` (Candidate, Mention, Evidence, Triple, PageResult, GateReport),
`tests/test_normalise.py`, `tests/test_census.py`, `tests/test_gates.py`,
`tests/fixtures/pages/` (three hand-written wiki-shaped `.md` files: normal, empty body,
injected instruction).
**What**: `normalise.py`: strip YAML frontmatter; reduce `[[Target|Display]]` and
`[[Target]] — relation` to display text; NFC-normalise; collapse whitespace. Export
`NORMALISATION_RULE_HASH` = sha256 of this module's rule text (spec F8). `census.py`:
walk `<corpus_root>/<domain>/*.md`, skip `private/`, per page record `path, bytes,
est_tokens (chars/4), split: est_tokens > 6000`, compute `profile_hash` over the sorted
list of (path, body-sha256), and `estimate_cost(profile, prices) -> Estimate(usd, basis)`
with the basis string stamped; the price table lives in `src/kg/profile/prices_table.py`
with its source URL and date, and the estimate prints the survival-rate assumption it used.
`refuse_if_over(estimate, ceiling)` raises `BuildRefused` naming the number;
`refuse_if_empty(profile)` raises it on zero pages, so a mistyped domain never costs $0 and
passes (fog FA-002). Gates are pure functions `(candidate, body, pack) -> GateResult(passed,
reason)`: verbatim quote found **exactly once** in the normalised body and at least
`MIN_QUOTE_CHARS` (20) long, with offsets recomputed here, so a repeated phrase is rejected
as ambiguous rather than pointing the judge window at the wrong occurrence (fog FA-012);
both entity surface forms inside the quote (attested); types and relation in the pack with
domain/range satisfied; and dedupe on a canonical `(subject_norm, relation, object_norm,
page_path)` key, which is also the store's write key (fog FA-006).
**Snippet**:
```python
# after — gates/quote_verbatim.py
def check(candidate: Candidate, body: str) -> GateResult:
    if len(candidate.quote) < MIN_QUOTE_CHARS:
        return GateResult(False, "quote too short to locate")
    n = body.count(candidate.quote)
    if n == 0:
        return GateResult(False, "quote not verbatim in normalised body")
    if n > 1:
        return GateResult(False, f"quote ambiguous: {n} occurrences")
    start = body.find(candidate.quote)
    return GateResult(True, None, span=(start, start + len(candidate.quote)))
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_normalise.py runs/ai/knowledge-graph/tests/test_census.py runs/ai/knowledge-graph/tests/test_gates.py -v`
**Done when**: a quote lifted from frontmatter or a wikilink target fails the verbatim gate
while the same text in the body passes; a quote that occurs twice is rejected as ambiguous
and a 10-character quote is rejected as too short; the census over `tests/fixtures/pages/`
returns the expected counts and a stable hash across two runs; an empty domain directory
raises `BuildRefused`; an estimate over the ceiling raises `BuildRefused` with the dollar
figure in its message; the census over the real `eval/`
(when `KG_CORPUS_ROOT` is set, else skipped with a printed reason) reports 80 pages.

#### Step A4: `GraphStore` protocol, SQLite implementation, export, passages
**Files**: new `src/kg/store/__init__.py`, `src/kg/store/protocol.py`,
`src/kg/store/sqlite.py`, `src/kg/store/export.py`, `src/kg/store/passages.py`,
`tests/test_store_sqlite.py`, `tests/test_export.py`, `tests/test_passages.py`.
**What**: `GraphStore` Protocol: `open_build(build_id, pack_hash, profile_hash)`,
`write_page_result(PageResult)`, `write_triple(Triple, Evidence, Judgement, tier)`,
`hops(entities: set[str], k: int, tiers: set[Tier]) -> list[Triple]`,
`passages(entities, k, tiers) -> list[Passage]`, `stats(build_id)`, `set_build_status(build_id,
status)`, `delete_build(build_id)`. SQLite schema: `builds` with `status ∈ {building, complete,
halted, promoted}`, `pages`, `mentions`, `triples` (with `tier`, `score`, `seat`, `build_id`),
`evidence` (quote, span, page path), `judgements`. **The query path reads only builds in
`promoted` status** unless a `build_id` is passed explicitly, so a halted or crashed build
never serves its partial accepts (fog FA-001); `delete_build` is the undo for a bad promote
and removes only that build's rows (fog FA-005). `hops()` is one recursive CTE bounded by `k`
and filtered by tier and build status. `passages.py` is the `graph_to_passages()` seam from `cap-kg.md:280`: each `Passage`
carries `text` (quote + one sentence of surrounding body), `tier`, `build_id`, `source_path`,
`hop`, and `freshness ∈ {fresh, stale, unverified}`: `unverified` whenever the current corpus
profile hash differs from the build's and no re-check has run, so "not checked" never reads
as "fresh" (fog FA-007). `export.py` writes JSONL (one triple per line with evidence) and an
Obsidian-flavoured markdown page per entity. Mirror `store.py:30-33` for `BUSY_TIMEOUT_MS`.
**Snippet**:
```python
# after — store/protocol.py
@runtime_checkable
class GraphStore(Protocol):
    def hops(self, entities: set[str], k: int, tiers: frozenset[Tier]) -> list[Triple]: ...
    def passages(self, entities: set[str], k: int, tiers: frozenset[Tier]) -> list[Passage]: ...
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_store_sqlite.py runs/ai/knowledge-graph/tests/test_export.py runs/ai/knowledge-graph/tests/test_passages.py -v`
**Done when**: a `review`-tier triple never appears in `passages()` with the default
`tiers={accept}` (spec F1); a build left in `halted` or `building` status contributes zero
rows to default `hops()` and `passages()` even when it holds accept-tier triples; `delete_build`
removes that build's rows and no others; `hops(k=2)` returns exactly the two-hop closure on a
five-node fixture and nothing at hop 3; re-writing the same canonical key is idempotent; a
passage from a build whose profile hash differs from the current corpus reports `unverified`;
JSONL round-trips.

#### Step A5: Proposer and `JudgeSeat` with the Claude adapters, shape-tested only
**Files**: new `src/kg/propose/__init__.py`, `src/kg/propose/proposer.py`,
`src/kg/propose/anthropic.py`, `src/kg/propose/prompt.py`, `src/kg/judge/__init__.py`,
`src/kg/judge/seat.py`, `src/kg/judge/claude.py`, `src/kg/judge/prompt.py`,
`src/kg/observability.py`; fill `tests/fakes.py`; new `tests/test_proposer.py`,
`tests/test_judge_claude.py`, `tests/test_prompts.py`, `tests/fixtures/snippets.jsonl`.
**What**: `Proposer` Protocol `propose(page: Page, pack: Pack) -> PageResult` (status
`proposed | no_candidates | not_run` with reason, spec F2). `AnthropicProposer` follows
`gateway.py` exactly: structured output via `output_config`, thinking disabled, no sampling
parameters, SDK errors mapped to `ProposerError`; prompt states the pack types positively
with boundary examples and demands a verbatim quote per candidate. `JudgeSeat` Protocol
`judge(candidate, window: str) -> Verdict(label: supported|not_supported|unclear,
score: float, usage: Usage)`; the judge is blind: it sees the candidate and a ±400-char
window, never the proposer's reasoning. `Verdict.score` is validated to `[0, 1]` at
construction and **raises** outside it, never clamps, so a seat returning percentages or a
0–10 rating cannot route everything to accept (fog FA-003). Failure mapping is fixed here
and shared by every seat: an SDK or HTTP error, a schema mismatch, a refusal, or truncated
output becomes `not_run` with a reason on the page or judgement, never a verdict;
`unclear` is reserved for a judge that answered and could not decide, and routes to
`review` (fog FA-002, FA-013). `ClaudeSeat` is the one real implementation here.
`observability.py` adapts marketing-comms `AgentSpan` with ops `kg.propose`, `kg.judge`, and
redacts quote text to its length. `tests/fixtures/snippets.jsonl` holds (snippet → expected
triples) pairs run as prompt unit tests against the **scripted** proposer (F9): they test the
pipeline's handling, and are the file a live run later asserts against.
**Snippet**:
```python
# after — judge/seat.py
@runtime_checkable
class JudgeSeat(Protocol):
    name: str
    async def judge(self, candidate: Candidate, window: str) -> Verdict: ...
    def available(self) -> tuple[bool, str]: ...   # (ok, reason-if-not)
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_proposer.py runs/ai/knowledge-graph/tests/test_judge_claude.py runs/ai/knowledge-graph/tests/test_prompts.py -v`
**Done when**: the Anthropic adapters build the expected request (model id, `output_config`
schema, thinking disabled, no `temperature`) against a fake client, as
`test_anthropic_adapter.py` does for marketing-comms; an SDK exception, a refusal and a
truncated JSON body each become `not_run` with a distinct reason, not a crash and not
`no_candidates`; `Verdict(score=85.0)` raises; the judge prompt contains no proposer
reasoning; the fakes satisfy both Protocols by `isinstance`.

#### Step A6: Priced two-threshold router and review queue
**Files**: new `src/kg/route/__init__.py`, `src/kg/route/prices.py`, `src/kg/route/tiers.py`,
`src/kg/route/review_queue.py`, `tests/test_route.py`.
**What**: `Prices(wrong_accept, wrong_reject, review, reviewer_tpr, reviewer_fpr)` with
documented defaults (a wrong accept reaches a plan doc: 10; a review: 1; a wrong reject: 1;
reviewer 0.95/0.05). `thresholds(prices) -> (t_lo, t_hi)` by the course's Chow derivation
(`course/data-science/01-classical-ml/notes/13-automate-review-or-reject.md`). `assign(verdict,
t_lo, t_hi) -> accept|review|reject`, where label `unclear` routes to `review` regardless of
score, and `band_rate` returns `NotApplicable("no judged candidates")` on a zero denominator
instead of `0.0` (fog FA-002, FA-013). `floor_point(scores, labels, precision=0.90)` finds
the minimum-band operating point at a precision floor (OntoSmith's rule) so both points are
reported. `risk_coverage(scores, labels)` returns the curve as a list of (coverage,
selective_risk). `band_rate(tiers)` and `halt_if_over(rate, limit)` raising `BuildHalted`.
`review_queue.py` renders the band as a CLI table and applies a human decision file.
**Snippet**:
```python
# after — route/prices.py
def thresholds(p: Prices) -> tuple[float, float]:
    # Chow reject option: review when expected cost of reviewing beats both auto routes.
    t_lo = p.review / (p.review + p.wrong_reject)          # below: reject is cheaper
    t_hi = 1 - p.review / (p.review + p.wrong_accept)      # above: accept is cheaper
    return t_lo, t_hi
```
(The exact form, including reviewer error rates, is taken from the course note at execute
time; the test pins the course's worked example, not this sketch.)
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_route.py -v`
**Done when**: the course's worked example reproduces its thresholds; `t_lo < t_hi` for every
positive price set; the floor point on a fixture hits ≥ 0.90 precision with the smallest
band; band rate 0.41 raises `BuildHalted`; the risk–coverage curve is monotone in coverage.

#### Step A7: Build orchestration, conformance record, CLI
**Files**: new `src/kg/build.py`, `src/kg/conformance.py`, `src/kg/cli.py`,
`tests/test_build.py`, `tests/test_cli.py`, `tests/test_conformance.py`.
**What**: `build(domain, settings, proposer, seat, store, *, dry_run) -> BuildReport` runs
profile → `refuse_if_over` → propose per page → gates → judge survivors → route → store;
opens the build in `building` status, writes triples as pages complete, and flips to
`complete` only at the end, or to `halted` on `BuildHalted`, a crash, or a runtime meter
that sums metered usage per call and halts at the ceiling, so the estimate is a refusal
before spend and the meter is the stop during it (fog FA-001, FA-010); stamps cost with
basis or `NotApplicable("dry run")`. `conformance.py`
writes an `experiments.record.RunRecord` (`DataIdentity(frame_hash=profile_hash,
n_rows=page_count, n_cols=1, columns=("body",))`, `capture_code_state()`, metrics: gate pass
rate, band rate, accepted count, `not_run` count, cost; `headline_metric="band_rate"`) via
`experiments.io.write_record` to `runs/ai/knowledge-graph/docs/records/<build_id>.json`.
`cli.py` (argparse, like Librarian's): `profile | approve | propose | build | inspect |
review | promote | unpromote | verify | repeat | ask`, every command with `--dry-run`;
`promote` refuses while any page is `not_run` unless `--waive <path> --reason <text>` names it
(spec F2), refuses a build with zero accepted triples on a non-empty domain or with
`no_candidates` on more than half its pages (fog FA-002), and in Phase B additionally refuses
until `docs/decisions/<build_id>.jsonl` records a measured accept-tier precision on live
proposer output (fog FA-004, written by the spend-decision checklist in B6); `unpromote`
returns the previous promoted build. Every human decision (approval, review decisions,
waivers with reason) is appended to `docs/decisions/<build_id>.jsonl`, committed, outside
the store, so a rebuild cannot lose it (fog FA-005). `verify` re-checks every stored quote
against the current **normalised** corpus body and sets `freshness`. `repeat <page> --n 5`
runs one page through the proposer n times and prints Jaccard over canonical keys; it is a
live-only command exercised by the spend-decision checklist (fog FA-006). `ask` in this
phase queries the SQLite store by entity surface form only (Librarian entry lands in B4).
**Snippet**:
```python
# after — build.py
if report.not_run and not waived:
    report.promotable = False
    report.reasons.append(f"{len(report.not_run)} page(s) not_run: {paths}")
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_build.py runs/ai/knowledge-graph/tests/test_cli.py runs/ai/knowledge-graph/tests/test_conformance.py -v`
and `cd runs/ai/knowledge-graph && uv run python -m kg.cli build eval --dry-run`
**Done when**: a dry-run build over `tests/fixtures/pages/` produces a report with every
denominator named and `not_run` separated; the record round-trips through `read_record`;
`promote` refuses with the page named; a build forced into `BuildHalted` after accepts were
written ends in `halted` and serves nothing; a scripted proposer returning `no_candidates`
everywhere yields a non-promotable build with `band_rate` reported as `NotApplicable`;
decisions appear in `docs/decisions/` and survive deleting the store file; the dry-run
build over the real `eval/` domain completes with 80 pages profiled and zero spend.

#### Step A8: Gold schema, labelling CLI, eval harness with calibration (dry-run)
**Files**: new `src/kg/judge/calibration.py`, `src/kg/label.py`, `evals/__init__.py`,
`evals/run.py`, `evals/gold/README.md`, `evals/gold/eval-v1.jsonl` (empty until B1),
`evals/bootstrapped.jsonl` (empty until a live build), `tests/test_calibration.py`,
`tests/test_label.py`, `tests/test_evals.py`, `tests/fixtures/gold_small.jsonl` (12 rows:
6 positive, 4 hard negative, 2 control).
**What**: Gold row schema: `{id, page, subject, subject_type, relation, object, object_type,
quote, label: positive|hard_negative|control, split: train|dev|test, labelled_by, at}`.
`label.py` (`kg label eval`) walks pages, shows the normalised body, takes a triple and a
quote, runs the verbatim and attested gates **immediately** so a bad label cannot be saved,
assigns `split` by hash of `id` (60/20/20), and appends to the JSONL (append-only, course
note on human labels). `calibration.py`: TPR, TNR, Cohen's κ with a Wilson interval, ECE in
10 bins, test–retest agreement across repeats, all per seat, computed on `split=test` only
and reported with `n`. `evals/run.py --dry-run --judge scripted` scores the fixture gold
with `ScriptedSeat`; `--judge claude|jev` and `--store neo4j` **refuse** when the seat or
store is unavailable, and `--judge claude` additionally refuses without `KG_LIVE=1`, printing
"live evaluation is a separate decision; see docs/spend-decision.md". Report template
includes the sentence "agreement is not precision" (spec F4) and prints the hard-negative
precision separately (spec F3).
**Snippet**:
```python
# after — evals/run.py
if args.judge == "claude" and not os.environ.get("KG_LIVE"):
    sys.exit("refused: --judge claude spends money; set KG_LIVE=1 after the spend decision")
ok, why = seat.available()
if not ok:
    sys.exit(f"refused: judge seat '{seat.name}' unavailable — {why}")
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_calibration.py runs/ai/knowledge-graph/tests/test_label.py runs/ai/knowledge-graph/tests/test_evals.py -v`
and `cd runs/ai/knowledge-graph && uv run python evals/run.py --dry-run --json`
**Done when**: κ on a hand-computed 2×2 matches to four decimals; TPR and TNR are reported
separately; a label whose quote is not verbatim is rejected at entry; `--judge jev` without a
key exits non-zero with the variable named; the dry run prints every metric in the spec's
Measurement table with its `n` and seat, and `--json` validates against a schema in the test.

**Phase A review boundary.** `/proto-review` here, before Phase B. The verifiable state: a
dry-run build and a dry-run eval both complete over the real `eval/` domain with zero spend,
and every spec finding F1–F8 has a test that would fail if it regressed.

---

### Phase B — the optional seams, the baseline, and the retrieval eval

#### Step B1: Label the gold (Ramsey, ~2 hours)
**Files**: `evals/gold/eval-v1.jsonl` (append-only, via `kg label eval`).
**What**: Ramsey labels ~50 positive triples, ≥ 15 hard negatives (verbatim quote, attested
entities, wrong relation) and ≥ 5 quoted-instruction controls across at least 20 distinct
`eval/` pages, using the CLI from A8. No model output is involved; this pool is independent
of any proposer.
**Snippet**: n/a (a human step).
**Test**: `cd runs/ai/knowledge-graph && uv run python -m kg.cli verify-gold evals/gold/eval-v1.jsonl`
(added in A8: counts per label and split, every quote re-checked).
**Done when**: counts meet the floors, every quote passes the verbatim gate against the
current corpus, and the split has ≥ 10 rows in `test`.

#### Step B2: Jev seat via OpenRouter, shape-tested, unavailable by name
**Files**: new `src/kg/judge/jev.py`, `tests/test_judge_jev.py`.
**What**: `JevSeat` posts to `https://openrouter.ai/api/alpha/decisions` with model
`typesafe/jev-1.13`, question type `noul`, and maps the returned probability to a `Verdict`;
`available()` returns `(False, "OPENROUTER_API_KEY not set")` without a key; HTTP and schema
errors follow the A5 mapping and become `not_run` with the reason logged, never a verdict
and never a silent score; the probability is validated to `[0, 1]` by `Verdict` (fog FA-003,
FA-013). Uses `httpx`
(already a dependency). Tests use `httpx.MockTransport`.
**Snippet**:
```python
# after — judge/jev.py
def available(self) -> tuple[bool, str]:
    return (True, "") if self._key else (False, "OPENROUTER_API_KEY not set")
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_judge_jev.py -v`
**Done when**: the request body matches the documented shape; a 5xx on every call ends the
build with the seat reported as failed and every candidate `not_run`, producing no reject
tiers; a response outside `[0, 1]` raises; `evals/run.py --judge jev` without a key refuses naming the variable;
with a fake key and `MockTransport` the dry run completes.

#### Step B3: Neo4j store behind the same protocol, parity pre-registered
**Files**: new `src/kg/store/neo4j.py`, `docker-compose.yml`, `tests/test_store_neo4j.py`,
`tests/test_store_parity.py`, `docs/preregistration.md`.
**What**: `Neo4jStore` implements `GraphStore` with a uniqueness constraint on
`(entity key, page path)`, so a node is a per-page mention exactly as in SQLite and no
cross-page merge happens in either store (research F2, fog FA-011); idempotent `MERGE` loads
(course note 10b, L3–L6); a full-text index on entity surface forms; `hops()` as a bounded
variable-length match filtered by tier and build status; the same `builds.status` semantics
as A4. `docker-compose.yml` runs
Neo4j Community 5.x locally. Tests skip without `NEO4J_URI` and `conftest.py` prints the
skipped count at session end (spec F6). `test_store_parity.py` loads the same fixture into
both stores and asserts identical `hops()` result sets. `docs/preregistration.md` states,
before the retrieval eval runs: expected recall parity between stores, latency within noise
at this scale, and that a difference either way is a finding.
**Snippet**:
```python
# after — store/neo4j.py
MERGE (s:Mention {key: $s, page: $page}) MERGE (o:Mention {key: $o, page: $page})
MERGE (s)-[r:REL {type: $rel, build_id: $build}]->(o)
SET r.tier = $tier, r.score = $score, r.evidence_id = $ev
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_store_neo4j.py runs/ai/knowledge-graph/tests/test_store_parity.py -v`
(with `docker compose -f runs/ai/knowledge-graph/docker-compose.yml up -d` for the
non-skipped path).
**Done when**: without Neo4j the suite passes and prints "N neo4j tests skipped"; with it,
loading twice yields the same counts and parity holds on a fixture that deliberately repeats
one surface form across two pages; `evals/run.py --store neo4j` without a
URI refuses by name.

#### Step B4: Librarian baseline adapter and hybrid `ask`
**Files**: new `src/kg/retrieve/__init__.py`, `src/kg/retrieve/librarian_baseline.py`,
`src/kg/retrieve/_librarian_probe.py` (the script run inside Librarian's venv),
`src/kg/retrieve/hybrid.py`; edit `src/kg/cli.py` (`ask` command); `tests/test_retrieve.py`.
**What**: `_librarian_probe.py` imports `librarian.retrieval.ranking.search_rows(query,
limit, expand=True)` and prints the 7-tuples (path, title, tags, summary, content, backlinks,
score) plus the `degraded` list as JSON. `librarian_baseline.py` runs it with
`uv run --project $LIBRARIAN_ROOT python -I <probe>` and returns `BaselineResult(rows,
degraded)`; a missing root or non-zero exit refuses by name. `hybrid.py`: entry rows →
entity surface-form match against the store → `hops(k ≤ max_hops)` → `passages()` with
`tier`, `build_id`, `freshness`; `ask --include-review` widens tiers. `ask` returns a typed
`AskResult(status ∈ {ok, entry_miss, no_hops, degraded}, passages)` so an entity the store
has never seen is distinguishable from an entity with no relations (fog FA-008), and it
re-runs the deterministic substring check of each quote against the current normalised body
at serve time, which costs no model call and sets `freshness` honestly (fog FA-007). A
`DEGRADED RETRIEVAL` flag from Librarian becomes `status=degraded`, never dropped. The probe
reports its own in-process retrieval time so latency excludes `uv run` startup (fog FA-009).
**Snippet**:
```python
# after — retrieve/librarian_baseline.py
cmd = ["uv", "run", "--project", str(root), "python", "-I", str(PROBE), "--query", q,
       "--limit", str(limit), "--expand"]
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_retrieve.py -v` (subprocess
faked; one integration test skipped unless `LIBRARIAN_ROOT` resolves).
**Done when**: the probe returns rows for a known `eval/` query when Librarian is present;
the baseline refuses with the path named when it is not; `ask` with defaults never returns a
`review`-tier passage; an unknown entity returns `entry_miss`, not an empty `ok`; a quote
edited out of the fixture corpus after the build comes back `stale`; hop depth never exceeds
`KG_MAX_HOPS`.

#### Step B5: Retrieval eval — questions, weak gold, recall@5 and latency per arm and store
**Files**: new `evals/questions.jsonl`, `src/kg/retrieve/weak_gold.py`; edit `evals/run.py`
(`--retrieval` mode), `tests/test_retrieval_eval.py`, `tests/test_weak_gold.py`.
**What**: `weak_gold.py` reads Librarian's typed wikilinks in `eval/` pages (the `[[Target]]
— relation` form seen in the corpus) and emits (question stem from page title, expected
neighbour pages) rows; Ramsey adds ≥ 20 hand-written questions so `questions.jsonl` has ≥ 50.
The eval runs four arms over the same questions: Librarian baseline with expansion **off**,
baseline with expansion on, graph arm on SQLite, graph arm on Neo4j (refused if unavailable).
The two baselines together show how much baseline recall comes from the same typed edges the
weak gold is built from, so the weak-gold and hand-written question sets are **scored and
reported separately** and the goal-1 verdict is read on the hand-written set (fog FA-009).
Reports recall@5 as a paired difference against the expansion-on baseline with a bootstrap
interval, grounding rate (every returned passage's quote still verbatim), entry-miss rate
(fog FA-008), and p95 in-process latency per arm, and pins the Librarian index build id and
the graph build's profile hash in the report so both arms are known to describe the same
corpus. "Five runs" applies to latency only; recall is deterministic per snapshot. The
pre-registered expectation from `docs/preregistration.md` prints beside the result. The
goal-1 bar is ≥ 10 points absolute over the expansion-on baseline on the hand-written set,
and the report says when the interval straddles the bar; below the bar it prints "no gain
recorded".
**Snippet**:
```python
# after — evals/run.py
BAR_POINTS = 10
verdict = "gain" if (graph.recall5 - base.recall5) * 100 >= BAR_POINTS else "no gain recorded"
```
**Test**: `uv run pytest runs/ai/knowledge-graph/tests/test_retrieval_eval.py runs/ai/knowledge-graph/tests/test_weak_gold.py -v`
and `cd runs/ai/knowledge-graph && uv run python evals/run.py --retrieval --dry-run`
**Done when**: weak gold over the real `eval/` yields ≥ 30 rows; the dry run with scripted
arms prints recall@5 per question set and per arm with `n`, the paired difference with its
interval, entry-miss rate, p95 per arm, the index build id and the preregistered line; an unavailable
store or missing Librarian refuses rather than skipping an arm.

#### Step B6: Docs, attribution, spend decision record, size report
**Files**: new `docs/DESIGN.md`, `docs/case-study.md`, `docs/THIRD_PARTY.md`,
`docs/spend-decision.md`; finish `README.md`; `.env.example` complete.
**What**: `DESIGN.md` in the marketing-comms shape (thesis, seams, what code enforces vs.
what the model fills). `case-study.md` names what came from OntoSmith (method, pack shape,
adjudication protocol, route rule) with citations and what did not. `THIRD_PARTY.md`
carries the MIT notice. `spend-decision.md` is the gate for the first live build, written as
an ordered checklist the operator ticks before any full build (fog FA-003, FA-004, FA-006,
FA-010 and the dry-run blind spots): (1) verify both model ids with one request; (2) run
`kg build eval --limit 1` and compare metered cost and candidate count against the estimate
and its survival assumption; (3) judge one known-true and one known-false candidate and
confirm their scores land on the expected sides of `t_hi` and `t_lo`; (4) `kg repeat` on one
page, five times, with a Jaccard bar of 0.8 on canonical keys; (5) label 30 live proposer
candidates and record accept-tier precision with a Wilson interval in `docs/decisions/`,
which is what unlocks `promote`; (6) only then the full build, with every candidate routed
to `review` until step 5 is recorded. It names the ceiling, the halt rule, the three numbers
to read first (band rate, `not_run`, hard-negative precision), and who decides. README prints the `wc -l src` number
and the "no live call has been made" state.
**Snippet**: n/a (prose).
**Test**: `wc -l $(git ls-files runs/ai/knowledge-graph/src | grep '\.py$') | tail -1` and
`uv run pytest --tb=no -q`.
**Done when**: source is ≤ ~3,000 lines (reported, not gated); every CLI command in the README
runs with `--dry-run`; the full suite passes with the new tests counted; `/proto-harden
runs/ai/knowledge-graph` is the next command.

### Test Plan

- Unit tests per step as listed; every model seam tested through `ScriptedProposer` and
  `ScriptedSeat`, every adapter through a fake client or `MockTransport`. No test calls a
  paid API; a test that needs a key or a URI skips and the skipped count is printed.
- Spec regression tests, one per finding: F1 banded-triple exclusion (A4), F2 `not_run`
  separation and promote refusal (A7), F3 hard-negative precision reported separately (A8),
  F4 "agreement is not precision" in the report (A8), F5 eval slice before Jev and Neo4j
  (plan order), F6 refuse-not-skip for seat and store (A8, B2, B3), F7 one-domain ceiling
  refusal (A3), F8 frontmatter and wikilink stripping before the verbatim gate (A3).
- End-to-end dry runs over the real `eval/` corpus at A7, A8 and B5, zero spend.
- Full suite `uv run pytest --tb=no -q` after A1 and after B6; the marketing-comms count must
  stay at its baseline.

### Risks & Rollback

- **Everything is additive** under `runs/ai/knowledge-graph/` plus three lines in
  `pyproject.toml`. Code rollback is deleting the directory and reverting those lines; no
  other run is touched.
- **Data plane, named separately** (fog FA-005). The SQLite file at `KG_DB_PATH` is
  disposable: every human decision lives in committed `docs/decisions/*.jsonl`, and the gold
  is a committed append-only JSONL, so a rebuild loses nothing human-authored. A bad promote
  is undone with `kg unpromote` or `delete_build`. The Neo4j volume is removed with
  `docker compose down -v` and reloaded from the SQLite export.
- **Known limit, accepted** (fog FA-014): the judge measures support within the quoted text,
  not truth. A page asserting an instruction-shaped falsehood can yield an accepted triple.
  The quoted-instruction controls measure this class but at n≥5 cannot certify a rate.
- **Shared `pyproject.toml` edit** (A1) can break collection for every run. Mitigation: run
  the full suite in A1's done-when; the `pythonpath` addition is a package dir, so no bare
  module names are added.
- **Live adapters never executed here.** Request shapes may be wrong at the first live
  build. Mitigation: adapters mirror `gateway.py` line for line where the API is shared, and
  `spend-decision.md` tells the operator to run one page first with `--limit 1`.
- **Librarian subprocess coupling.** Librarian's `search_rows` signature can change.
  Mitigation: the probe is ten lines, fails loudly, and the integration test skips with a
  printed reason when Librarian is absent.
- **Gold too small for a tight κ.** Accepted at the 2-hour budget; intervals are printed, and
  the labelling CLI is append-only so the pool can grow later without re-labelling.
- **Neo4j Docker not available on the machine.** The store is optional by design; parity and
  the Neo4j arm are refused by name, and the SQLite path carries the whole eval.

### Open Questions

See the top of this plan. Resolved at refine, 2026-11-07:

- Pack authorship: execute drafts `eval-v1.json`, Ramsey edits and approves (default 6
  stands). Ramsey can still replace the draft wholesale at the approve step.
- Live gate: `KG_LIVE=1` as an environment variable, because it cannot be committed by
  accident, plus the spend-decision checklist in B6 as the human half of the gate.

## Refinement — 2026-11-07

Gate run on the Full path (14 steps, ~60 files, a shared `pyproject.toml` edit). All seven
Definition of Ready checks pass; `fog-advisor` dispatched with the plan only and returned 14
findings. Disposition, each folded into the step named:

| Finding | Severity | Closed in |
|---|---|---|
| FA-001 halted build still serves accepts | fatal | A4 build status + promoted-only query path; A7 status flips |
| FA-002 zero output reads healthy | fatal | A3 empty refusal; A5 refusal/truncation → `not_run`; A6 `NotApplicable` band rate; A7 promote refusals |
| FA-003 score units unvalidated | fatal | A5 `Verdict` range check raises; B6 checklist step 3 |
| FA-004 accept precision never measured | fatal | A7 promote refuses without recorded precision; B6 steps 5–6 |
| FA-005 no data-plane rollback | costly | A7 decisions file; Risks & Rollback |
| FA-006 repeat test has no step | costly | A7 `kg repeat`; A3 write key; B6 step 4 |
| FA-007 stale defaults false | costly | A4 `freshness` tri-state; B4 serve-time re-check |
| FA-008 empty `ask` is ambiguous | costly | B4 typed `AskResult`; B5 entry-miss metric |
| FA-009 retrieval number biased, underpowered | costly | B5 four arms, separate scoring, paired interval, pinned ids |
| FA-010 estimate is not a meter | costly | A7 runtime meter; A3 price table source |
| FA-011 Neo4j merges across pages | costly | B3 per-page mention key; parity fixture |
| FA-012 first-occurrence quote match | costly | A3 uniqueness + minimum length |
| FA-013 `unclear` route unstated | costly | A5 mapping; A6 `unclear` → review; B2 |
| FA-014 quoted instructions pass gates | costly | accepted as a known limit, Risks |

Verdict REFINED rather than READY: the amendments touch ten steps, so the next refine pass
re-reads them once on the Light path before `READY`.

**Light pass, same day.** Re-read A3–A7 and B2–B6 for internal consistency: the `builds.status`
column A4 introduces is what A7 flips and B3 mirrors; A5's failure mapping is what A6's
`assign` and B2's Jev seat consume; `freshness` is set in A4, re-checked in A7 `verify` and
B4 `ask`. No contradictions. Verdict READY. Phase A executes first; Phase B starts after the
A8 review boundary and the spend-decision checklist.
