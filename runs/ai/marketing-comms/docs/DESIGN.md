# galactus — design

Constrained marketing-collateral generation behind a deterministic layout contract.

A sales rep needs a two-column brief about a partnership between their company
and a prospect. Today that is four manual steps: read both companies' material,
pull out the claims worth making, write the copy, then fight the copy into a
fixed page layout until it fits.

Three of those steps are judgement. The fourth is arithmetic.

## The reframe

The instinct is to hand all four to a model — "write me a brief that fits this
layout" — and then be disappointed when the headline is eleven words in a
nine-word slot. That failure is not a prompting problem, and no amount of
"remember, at most nine words" fixes it reliably. Length compliance is a
constraint-satisfaction problem, and a language model is the wrong tool for it:
it cannot count its own tokens before emitting them, and asking it to try
spends capability on a task that `len(text.split())` settles exactly.

So the split this system is built on:

> **Counting characters is a job for code. The model's job is content.**

The model proposes; deterministic code disposes. Everything downstream follows
from taking that seriously.

## The layout contract

A template is a JSON file declaring fields and their constraints
([templates/two_column_brief.json](../templates/two_column_brief.json)). The
shipped template has nine fields:

| Field | Kind | Limits |
|---|---|---|
| `headline` | text | 3–9 words, ≤70 chars |
| `subheadline` | text | ≤18 words, ≤130 chars |
| `column_left` | text | 60–95 words, ≤620 chars |
| `column_right` | text | 60–95 words, ≤620 chars |
| `pull_quote` | text | ≤22 words, ≤150 chars |
| `cta` | text | ≤12 words, ≤80 chars |
| `hero_image` | image_placeholder | `{{hero_image}}` |
| `sender_logo` | image_placeholder | `{{sender_logo}}` |
| `accent_color` | color_ref | one of five named theme colors |

Word floors matter as much as ceilings: a 12-word column in a slot sized for 95
leaves a hole in the page, which is a layout failure just as much as overflow.

Three kinds cover the shipped template, and the validator dispatches on kind
([src/guardrails/validator.py](../src/guardrails/validator.py)) — so
a fourth kind is a new enum arm plus a check function, not a redesign. That
matters for the standing assumption below.

### The limits are carried three ways, and only one is binding

1. **In the JSON Schema** sent with the request — as documentation. The
   Anthropic SDK strips `maxLength` before the call and checks it client-side,
   so it does not constrain generation. Word counts have no JSON Schema
   equivalent at all.
2. **In the prompt prose** — where the model can actually act on the numbers.
3. **In `layout.validator`** — which decides. Pure function, no I/O, no model.

Only the third is binding, and the design assumes exactly that. The schema is
still worth sending: `additionalProperties: false` and `required` *are*
enforced by structured outputs, which removes two whole violation classes
(missing fields, stray fields) before the first call.

## The pipeline

```
POST /collateral
      │
      ▼
  ┌───────────────────────────────────────────────────────────┐
  │ 202 Accepted + job_id            (returns here, ~instantly)│
  └───────────────────────────────────────────────────────────┘
      │  background task
      ▼
  ingest ──▶ extract ──▶ ground ──▶ draft ──▶ validate ──┐
  (PDF)      (facts)     (verify)   (LLM)     (pure fn)   │
                                       ▲                  │
                                       │   violations     │
                                       └──── repair ◀─────┤ invalid,
                                            (≤3×)         │ budget left
                                                          │
                                     fallback ◀───────────┤ invalid,
                                    (truncate)            │ budget spent
                                                          │
                                      stored JSON ◀───────┘ valid
```

There is no `retrieve` stage. Company context is a handful of PDFs per company,
which fits in a prompt — see *What we did not build* below.

### Trace one request

A reader should be able to follow this without opening the source. Component
names below are the actual module and function names.

**1. Upload context** — `POST /companies/meridian/context` with a PDF and
`role=sender`. `upload_context` validates the role against `{sender, receiver}`,
rejects an empty body, an upload over the 25 MB cap (**413**), and bytes that do
not start with the PDF magic (**422** — a mislabelled JPEG accepted today is a
failed generation job tomorrow, discovered by the wrong person). Then it stores
the bytes via `Store.put_pdf` and returns 201 with a `pdf_id`. Ingest does
**not** happen here: the vision path costs money, and a PDF uploaded but never
used in a brief should not incur it. `GET`/`DELETE` on the same path list and
remove uploads — the recovery route for a bad one.

**2. Request collateral** — `POST /collateral` with
`{sender_company_id, receiver_company_id, prompt, template_id}`.
`request_collateral` does three precondition checks, all synchronous, all
before any job exists:

- `load_template_cached(template_id)` — unknown template ⇒ **404**. Template
  ids are gated to bare `[a-z0-9_]+` names first, because the id reaches a
  filesystem path and would otherwise be a traversal vector.
- `Store.get_pdfs(company_id, role=...)` for **both** sides — missing context
  on either ⇒ **404** naming the side. A partnership brief grounded on one
  company is not a degraded success; it is a request that cannot be served,
  and the caller should hear that now rather than infer it from a hollow
  draft later.

Then the request's dedup key — `sha256(sender, receiver, template, prompt)` —
is checked against the store: an identical request with a queued, running, or
succeeded job returns *that* job instead of billing a second generation, the
same conditional-write idempotency the cloud design puts on the job document.
Otherwise `Store.create_job` writes a `queued` row, `BackgroundTasks` schedules
`run_job`, and the endpoint returns **202** with the `job_id`.

The 202 is not only a latency accommodation. A synchronous endpoint would push
back against retrying — and the retries are where the contract guarantee comes
from. Async is what makes the repair loop affordable.

**3. Ingest and extract** (`run_job`) — the job flips to `running`. For each
side, PDFs are fetched **by company *and* role**:

```
(sender_company_id,   "sender",   state.sender_facts)
(receiver_company_id, "receiver", state.receiver_facts)
```

The role filter is load-bearing, not decoration. The same company can be the
sender in one brief and the receiver in another, so a company-only query would
pull its receiver-role PDFs into `sender_facts` and collapse the very
separation the grounding block is built on.
`test_a_company_on_both_sides_does_not_leak_across_roles` pins it.

`ingest_pdf_bytes` runs a **hybrid** extraction over the three input kinds the
brief names — text, images, and tables:

- **Text path** (pymupdf) — extracts text and records, for each fact, the page
  and character span it came from.
- **Table path** (`ingest/tables.py`) — one fact per data row, rendered against
  the header. See below; tables need their own path because the text path
  actively destroys them.
- **Vision path** — only for pages with fewer than `MIN_PAGE_TEXT_CHARS = 200`
  characters of extractable text, i.e. scans and image-heavy slides. The
  text-sparse pages are rendered once per document and the PNGs travel through
  the port's `images` channel, so the model actually receives the page it is
  asked to read. Facts from this path carry `VISION_CONFIDENCE = 0.7` and no
  verifiable span.

The gate is a cost decision as much as a quality one: vision is charged per
page, and running it over pages that already yielded clean text buys nothing.
Ingest is concurrent where nothing orders it: sender and receiver PDFs in
parallel, vision pages gathered per document, and the pymupdf parse pushed off
the event loop so a large upload does not stall every other client's poll.

If either side produces **zero** facts — scans with no vision credential, a
decorative deck — the job fails with an error naming the side. Generating
anyway would produce an ungrounded brief presented as a grounded one.

#### Why tables are not just text

A PDF table has no sentence terminators, so `get_text()` returns one cell per
line and the sentence splitter glues the whole grid into a single run-on fact:

```
Corridor Volume On-time Chicago-Dallas 184,000 96.2% Newark-Atlanta 141,500 93.8% …
```

Every number is present and every number is unattributed. A model drafting from
that can pair 96.2% with any corridor in the grid and still appear grounded,
because the digits genuinely are in the source. For a brief whose stated
requirement is factual correctness, that is the worst available failure: wrong
and confident, with a citation that checks out.

So the row is the unit. Each data row becomes one fact carrying its own subject:

```
Corridor Chicago-Dallas: Volume 184,000; On-time 96.2%.
```

Cell-level facts would carry no subject; table-level facts would reproduce the
original ambiguity. The row is the smallest span in which a value keeps its
meaning.

Rewriting the row means it can no longer equal its source span, so table facts
declare `origin="table"` and are verified by a different rule: the span must
*contain* every **full cell value** the row asserts, carried on `Fact.cells`
rather than re-parsed from the rendered sentence — parsing back would verify
only the last word of a multi-word cell. A fact whose span drifts onto a
neighbouring row fails that check
(`test_a_row_fact_citing_another_rows_span_is_dropped`), and a table fact
without cells fails closed. The exact-match rule is relaxed for this origin
only, not loosened globally.

Once a page's rows are recovered structurally, the text facts whose spans
overlap those rows' regions are dropped — otherwise the prompt would carry the
ambiguous run-on alongside the precise rows. Only the overlapping region is
superseded: prose sharing a page with a table keeps its facts. `find_tables`
is heuristic, so a page whose tables fail to parse keeps its text facts and
logs the reason rather than failing the upload.

**4. Ground** — `verify_facts` drops any fact whose claimed span does not
resolve in the source text. This is a **block, not a warning**. A fact that
cannot be traced to a span never reaches the prompt, so a hallucinated citation
cannot survive into the draft by being merely low-confidence.

**5. Draft** — `generate_collateral` builds a prompt carrying the field specs
with their limits, the brief, and the grounding facts rendered under `## Sender`
and `## Receiver` headings, plus the instruction that every factual claim must
come from those facts. One call to `LLM.complete_structured(prompt, schema)`.

**6. Validate** — `validate(draft, template)` returns a list of `Violation`s,
each carrying `field`, `constraint`, `actual`, `limit`, and a `repair_hint`
computed in code: *"Shorten 'headline' from 14 to at most 9 words."* Empty list
⇒ done. `state.first_pass_valid` is recorded here; it is the contract-pass-rate
metric.

**7. Repair** (≤3 attempts) — the violations are handed back with the **whole**
draft, not just the offending fields. Fields are not independent: shortening one
column changes how it balances against the other, and a model editing in
isolation returns something that fits the contract but reads as though it were
assembled from parts. The hints are forwarded, never re-derived — the
arithmetic already happened in the validator.

Three attempts is empirical headroom, not a guess at convergence. The feedback
is precise and mechanical, so a model that cannot satisfy it in three tries is
not converging, and a fourth call is unlikely to differ from the third. An
unbounded loop is an unbounded bill and an unbounded latency.

**8. Fallback** — if the budget runs out with violations outstanding,
`fallback(draft, template)` repairs deterministically. Every violation kind has
a mechanical repair:

| Violation | Repair |
|---|---|
| `max_words` | drop trailing words, preferring a sentence boundary |
| `max_chars` | drop trailing words until under the ceiling |
| `min_words` | pad with a neutral filler token |
| `required` | synthesize a minimal value valid for the kind |
| `unknown_field` | remove it |
| `image_placeholder` | replace with `{{field_name}}` |
| `color_ref` | replace with the first theme color |

This path cannot fail *for a satisfiable template* — `validate(fallback(d, t),
t)` is empty for any input `d` — and satisfiability is not left to luck: a
template whose word floor cannot fit inside its character ceiling is rejected
when it loads, so a designer typo fails the deploy rather than the one request
that exhausted its repair budget. The fallback's output is still re-validated
before the job is marked `succeeded`; if the backstop ever fires, the job fails
loudly instead of shipping an invalid draft labelled "degraded". The padding
filler is deliberately semantically empty ("and"): the alternative is inventing
content to reach a word floor, which is a grounding violation dressed up as a
repair.

**9. Store** — `Store.update_job` writes the terminal state: `status`, `draft`,
`used_fallback`, `fallback_fields` (which fields the fallback touched — a
one-field truncation and a wholesale rewrite are different degradations),
`repair_attempts`, `fact_count`. Every exception is caught and recorded as a
`failed` job rather than raised — a background task that raises loses the error
entirely and leaves the client polling a job stuck in `running` forever. The
bookkeeping writes themselves are guarded the same way, and at startup any job
still `queued`/`running` is failed with an explicit "process restarted" error
rather than left for the client to poll forever.

**10. Poll** — `GET /jobs/{job_id}` returns status and, once terminal, the
draft. `used_fallback: true` means the draft fits but was mechanically
degraded. The API never presents a degraded draft as undegraded work.

### What the guarantee actually is

**`POST /collateral` followed by polling to a terminal state returns either a
contract-valid draft or an explicit failure — never an invalid draft.**

Not "usually valid." The fallback makes validity unconditional. What is *not*
guaranteed is that the draft is good: a fallback draft is truncated prose with
filler padding, and it is flagged so the caller can treat it accordingly.

## Numbers

From `uv run python evals/run.py --dry-run` — 12 cases across easy/medium/hard,
run against a scripted provider so the harness is deterministic and costs
nothing:

| Metric | Value | Meaning |
|---|---|---|
| Contract pass rate | 58.3% | valid on first generation, no repair |
| Repair convergence | 0.36 | mean repair attempts, converged cases |
| Fallback rate | 8.3% | needed deterministic truncation |
| Grounding rate | 91.7% | claims traceable to a source span |
| **Contract valid after repair+fallback** | **100.0%** | the guarantee |
| Total provider calls | 19 | for 12 cases |

Read the first and last rows together. First-pass compliance is a coin flip —
which is precisely the argument for not trusting the model with arithmetic. The
100% is not the model getting better; it is the deterministic layer doing its
job.

The one ungrounded case is `no-facts-at-all`: a brief with no source material
at all, which exhausts the repair budget and lands in fallback. It is in the
suite because that is the case a demo would quietly omit.

**These numbers come from scripted fixtures, not from the client's real PDFs.** The
scripted provider replays fixed responses, so the pass rate measures the
*harness*, not a live model. Treat them as a working instrument, not a
benchmark.

## Cost model

Roughly **$0.003 per piece of collateral**, dominated by input tokens: the
grounding facts and field specs are large relative to the nine short strings
that come back. Two consequences drive design decisions:

- **Repairs are cheap.** A repair call resends the draft and the violations —
  small next to the fact block. Three attempts is affordable; this is why the
  budget is 3 and not 1.
- **Vision is not cheap**, being charged per page. Hence the
  `MIN_PAGE_TEXT_CHARS` gate and deferring ingest from upload to generation.

## Storage

SQLite, two tables ([src/store.py](../src/store.py)):

- **`pdfs`** — `(pdf_id, company_id, role, filename, content, created_at)`.
  Queryable by company and role.
- **`jobs`** — `(job_id, company_id, status, dedup_key, payload_json,
  created_at)`. The payload is a JSON blob merged on update; `dedup_key` backs
  the idempotency lookup.

`GALACTUS_DB_PATH` points the store at a file (WAL mode, 5s busy timeout) so
uploads and results survive a restart; unset, it runs in memory — fine for
tests, wrong for anything with two workers or a deploy.

Document-shaped on purpose. The job row is already a document with a status
field and a JSON body, so the Firestore migration in the cloud design is a
driver swap rather than a schema redesign. Connections are per-operation; the
in-memory mode uses a shared-cache URI with a keepalive connection so the
database survives between operations within a process.

## Observability

structlog, JSON lines, span-style events (`gen_ai.generate`, `gen_ai.repair`,
`gen_ai.vision`) carrying `job_id`, `stage`, `attempt`, `violation_count`,
latency and token counts. The `job_id` is bound for the duration of a background
task and explicitly cleared in a `finally` — background tasks share a context
pool, and a leaked id would stamp the next job's log lines.

`violation_count` per repair attempt is the field that makes the loop
debuggable: a count that does not fall across attempts is a non-converging
repair, visible without reproducing the request.

## What we did not build

Each of these is a real option that was considered and declined. The reasons are
short because they should be.

- **No orchestration framework (LangGraph et al.)** — the pipeline is a fixed
  linear DAG with one bounded loop. That is an `async def` with a `while`. A
  graph framework would add a dependency, an execution model, and a debugging
  surface to express control flow that Python already expresses in ten lines.
- **No vector store / RAG** — retrieval solves *too much context*. A company's
  context here is a handful of PDFs that fit in a prompt whole. Chunking and
  embedding them would add an index to maintain, a similarity threshold to tune,
  and a new failure mode (the relevant fact ranks 4th and gets cut) in exchange
  for nothing. This is a scale-dependent call, and it flips: see below.
- **No MCP** — MCP standardizes exposing tools to a model. This pipeline gives
  the model no tools. It has exactly one model interaction —
  *"return JSON matching this schema"* — and a protocol for tool exposure has
  nothing to attach to.
- **No Kubernetes** — the workload is a stateless HTTP service with background
  tasks. Cloud Run and Lambda both run that with no cluster to operate.
- **Not orchestration-agnostic** — the LLM *port* is provider-agnostic
  (`complete_structured(prompt, schema, images=...)`, one Anthropic adapter
  behind it; images travel as raw PNG bytes and each adapter does its own
  encoding), because swapping providers is a real requirement. Abstracting the
  *pipeline* behind a second interface would be building for a migration nobody
  has asked for.

The pattern: each omission is declined against *this* problem at *this* scale,
not in general.

## Standing assumptions

Stated because they are the places this design would need revisiting, not
because they are hedges.

1. **"Fits the layout" means word and character counts, not rendered
   typography.** If the real constraint is measured in pixels after font
   metrics, the validator's structure survives — a `max_rendered_px` constraint
   kind is one new enum arm and one check function — but the constraint values
   in the template would all be wrong, and the repair hints would need to speak
   in rendered width rather than words.
2. **Fixtures are synthesized, not the client's real PDFs.** The ingest gate at 200
   characters per page is tuned against invented documents. Real collateral
   would move that number. The same caveat applies harder to tables: the
   fixtures' grids are ruled and regular, which is the case `find_tables`
   handles best. Borderless or multi-row-header tables are where it degrades,
   and the design's answer there is to fall back to the text path, not to
   guess at structure.
3. **Vision facts are unverifiable by construction.** They carry a confidence
   score and no span, so the grounding rate counts them as ungrounded. That is
   the honest accounting, not a bug — but it means a corpus that is mostly scans
   would report a low grounding rate while behaving correctly.

## What I would do next

In priority order, and honestly:

1. **Run the evals against a live model.** Every number above comes from a
   scripted provider. The first-pass pass rate against a real model is the
   single most informative missing measurement, and it is a day's work.
2. **Per-field repair targeting.** Today an over-long headline resends all nine
   fields. Sending the draft whole is right for *coupled* fields (the two
   columns), but `cta` and `headline` are independent, and a narrower repair
   would be cheaper and less likely to disturb fields that already fit.
3. **A real job queue.** `BackgroundTasks` dies with the process — an in-flight
   job is lost on deploy, with no retry. The startup reconciliation now fails
   such jobs loudly instead of leaving the client polling, but that is
   detection, not recovery; the cloud design's Pub/Sub with dead-letter topics
   is the actual fix.
4. **Real identity.** The `X-API-Key` gate is a shared secret, not tenancy —
   every keyholder can read every company's context and generate against it.
   A production deployment needs per-tenant auth binding companies to callers,
   which the cloud design delegates to the platform's identity layer.
5. **More templates.** One template is enough to prove the contract mechanism
   and not enough to prove it generalizes. A single-column layout and a
   social-card layout would test whether the constraint kinds are actually the
   right vocabulary.

## Cloud

- [architecture-gcp.md](architecture-gcp.md) — five components, the primary design
- [architecture-aws.md](architecture-aws.md) — the same design mapped to AWS

Both describe a **deployment target, not the current implementation**. What runs
today is a single FastAPI process with SQLite and in-process background tasks.
Every component in those documents is marked accordingly.
