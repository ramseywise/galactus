# galactus

Two things live here:

1. **`pocs/ai/marketing-comms/`** — a case study: constrained marketing-collateral generation, where an LLM
   writes the content and deterministic code decides whether it fits.
2. **`.claude/`** — the engineering setup that builds things like it. Skills, subagent
   reporters, hooks, and specs, wired into a design → research → plan → execute → review
   pipeline. See [CLAUDE.md](CLAUDE.md) and [DESIGN-PROCESS.md](DESIGN-PROCESS.md).

The rest of this README describes the case study.

---

## pocs/ai/marketing-comms — constrained collateral generation

Given two companies and a prompt, it produces a two-column brief whose
every field satisfies a declared layout contract — word floors and ceilings,
character limits, theme colors. The model never gets the last word on whether
the output fits, because that is arithmetic.

> **Counting characters is a job for code. The model's job is content.**

Full reasoning in [pocs/ai/marketing-comms/docs/DESIGN.md](pocs/ai/marketing-comms/docs/DESIGN.md).

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest                              # deterministic core; no network, no API key
uv run python pocs/ai/marketing-comms/evals/run.py --dry-run
```

The whole deterministic core — contract, validator, repair-hint generation,
fallback — runs with no credential and no network. Only the provider-backed
paths need a key.

To run against the real model:

```bash
export ANTHROPIC_API_KEY=...          # or put it in a gitignored .env
uv run uvicorn galactus.api:app --app-dir pocs/ai/marketing-comms/src --reload
```

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required only for provider-backed paths |
| `GALACTUS_MODEL` | see `pocs/ai/marketing-comms/src/galactus/config.py` | Model id |
| `GALACTUS_MAX_REPAIRS` | 3 | Repair budget before deterministic fallback |
| `GALACTUS_LOG_LEVEL` | INFO | structlog level |

## API

Four endpoints. Generation is asynchronous: `POST /collateral` returns 202 with
a `job_id`, and the client polls.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `POST` | `/companies/{company_id}/context` | Upload a context PDF (`file`, `role=sender\|receiver`) → 201 |
| `POST` | `/collateral` | Request collateral → 202 + `job_id` |
| `GET` | `/jobs/{job_id}` | Poll status and retrieve the draft |

```bash
curl -F file=@meridian.pdf -F role=sender \
     localhost:8000/companies/meridian/context

curl -X POST localhost:8000/collateral -H 'content-type: application/json' -d '{
  "sender_company_id": "meridian",
  "receiver_company_id": "northwind",
  "template_id": "two_column_brief",
  "prompt": "A partnership brief emphasising supply-chain reliability."
}'

curl localhost:8000/jobs/{job_id}
```

## How it works

```
ingest ──▶ extract ──▶ ground ──▶ draft ──▶ validate ──┐
 (PDF)      (facts)    (verify)    (LLM)    (pure fn)  │
                                      ▲                │
                                      └─── repair ◀────┤ invalid, budget left
                                          (≤3×)        │
                                    fallback ◀─────────┤ invalid, budget spent
                                   (truncate)          │
                                  stored JSON ◀────────┘ valid
```

The guarantee is structural, not probabilistic. `validate` is a pure function
of a draft and a template; when the model's draft violates the contract, the
violations are computed and fed back as a repair prompt. After three attempts
the deterministic fallback truncates to fit. **The output always satisfies the
contract** — the model's cooperation is an optimisation, not a dependency.

Facts are grounded before drafting: claims that cannot be resolved to a span in
an uploaded PDF are dropped rather than flagged. Sender and receiver context are
kept separate end to end.

[pocs/ai/marketing-comms/docs/DESIGN.md](pocs/ai/marketing-comms/docs/DESIGN.md) traces a single request through all ten steps,
and states plainly what is *not* implemented.

## Evaluation

```bash
uv run python pocs/ai/marketing-comms/evals/run.py --dry-run   # scripted adapter, no spend
uv run python pocs/ai/marketing-comms/evals/run.py --json      # live, machine-readable
```

Four metrics: contract-compliance rate, repair-attempt distribution,
fallback rate, and grounding precision.

## Layout

```
pocs/ai/marketing-comms/src/galactus/
  api.py            FastAPI surface — 202, background task, the pipeline itself
  generate.py       Prompt + JSON Schema construction, the repair loop
  models.py         Pydantic types — PipelineState, Violation, Fact, templates
  store.py          SQLite, document-shaped for a Firestore migration
  config.py         Environment-backed Settings
  model/
    gateway.py      Provider port + Anthropic adapter — the only `anthropic` import
  guardrails/
    validator.py    The binding constraint. Pure function. Emits repair hints.
    fallback.py     Deterministic truncation. Cannot fail.
  observability/    structlog span helpers
  layout/
    contract.py     Strict template loading — malformed fails at load
  ingest/
    text.py         pymupdf text path — verifiable spans
    vision.py       Vision path, used only when the text path comes up thin
    facts.py        Fact extraction and span grounding
pocs/ai/marketing-comms/templates/      Layout contracts as JSON
pocs/ai/marketing-comms/evals/          Eval harness and cases
pocs/ai/marketing-comms/tests/          Test suite
pocs/ai/marketing-comms/docs/           DESIGN.md, cloud architecture, presentation
```

## Docs

- [pocs/ai/marketing-comms/docs/DESIGN.md](pocs/ai/marketing-comms/docs/DESIGN.md) — the reframe, the contract, one request traced end to end, and what was deliberately not built
- [pocs/ai/marketing-comms/docs/architecture-gcp.md](pocs/ai/marketing-comms/docs/architecture-gcp.md) — production design target (not implemented)
- [pocs/ai/marketing-comms/docs/architecture-aws.md](pocs/ai/marketing-comms/docs/architecture-aws.md) — AWS mapping and the three places it is not one-to-one
- [pocs/ai/marketing-comms/docs/presentation.html](pocs/ai/marketing-comms/docs/presentation.html) — 10 slides, self-contained, opens offline

## Status

A prototype built as a take-home exercise. It is not deployed and has no
authentication, rate limiting, or spend cap — see the *What we did not build*
and *Standing assumptions* sections of [pocs/ai/marketing-comms/docs/DESIGN.md](pocs/ai/marketing-comms/docs/DESIGN.md), which
are deliberate omissions with stated reasoning rather than an inventory of
oversights.
