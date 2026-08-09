# Cloud architecture — GCP

**Status: design target, not implemented.** What runs today is a single FastAPI
process with SQLite and in-process `BackgroundTasks`
([DESIGN.md](DESIGN.md)). Nothing in this document is deployed. Every component
below is annotated with what the prototype does instead.

The prototype was built so this migration is a driver swap rather than a
rewrite: the storage layer is document-shaped, the LLM sits behind a port, and
the pipeline is a pure function of its state.

## Five components

```
   client
     │  POST /collateral
     ▼
┌──────────────┐   publishes    ┌───────────────┐   pushes   ┌──────────────┐
│  Cloud Run   │───────────────▶│    Pub/Sub    │───────────▶│  Cloud Run   │
│  (API tier)  │  job message   │  jobs topic   │            │ (worker tier)│
└──────┬───────┘                └───────┬───────┘            └──────┬───────┘
       │                                │ 3 failures                │
       │ signed URL                     ▼                           │ generate
       ▼                        ┌───────────────┐                   ▼
┌──────────────┐                │  jobs-dlq     │            ┌──────────────┐
│Cloud Storage │                │ (dead letter) │            │  Vertex AI   │
│  (PDF bytes) │                └───────────────┘            │  (Claude /   │
└──────┬───────┘                                             │   Gemini)    │
       │ read at generation time                             └──────┬───────┘
       │                                                            │
       └────────────────────────▶ ┌──────────────┐ ◀────────────────┘
                                  │  Firestore   │  draft + status
                                  │ (jobs, docs) │
                                  └──────────────┘
```

### 1. Cloud Storage — PDF bytes

Company context PDFs, keyed `companies/{company_id}/{role}/{pdf_id}.pdf`. The
role sits in the path because it is part of the identity of the upload, not
metadata on it — see the role-separation discussion in
[DESIGN.md](DESIGN.md#trace-one-request).

Uploads go direct from the client via signed URLs, so PDF bytes never transit
the API tier.

*Prototype:* bytes in a SQLite `pdfs` table, uploaded through the API process.

### 2. Pub/Sub — the job queue

`POST /collateral` validates preconditions, writes a `queued` job to Firestore,
publishes `{job_id}` to the `jobs` topic, and returns 202. The message carries
the id only; the job document is the state.

**Idempotency.** The dedup key is `sha256(sender_id, receiver_id, template_id,
prompt)`, set as the Pub/Sub `orderingKey` and stored on the job document under
a unique constraint. A duplicate submission within the dedup window returns the
existing `job_id` and its 202 rather than generating twice. This matters
specifically because delivery is at-least-once: without it, a redelivered
message is a second billed generation.

**Dead-letter topic.** After 3 delivery attempts a message moves to `jobs-dlq`
with an alert. Three matches the repair budget's reasoning — a failure that
survives three attempts is not transient.

Note the two distinct retry layers, which are easy to conflate: Pub/Sub retries
are for *infrastructure* failure (worker crashed, timed out). The repair loop is
for *contract* failure (draft did not fit), and is not a retry at all — it is a
new prompt carrying computed violations. A draft that fails the contract must
never be redelivered as a queue failure; it is handled in-process and lands in
the deterministic fallback.

*Prototype:* `BackgroundTasks` in the API process. No retry, no dedup, and an
in-flight job is lost on restart. This is the most significant gap between the
two designs.

### 3. Cloud Run — API and worker tiers

Two services from one image, split by role:

- **API tier** — the FastAPI app as it exists today, minus the background task.
  Fast, cheap, scales on request count, `min-instances=1` to avoid cold starts
  on the interactive path.
- **Worker tier** — Pub/Sub push subscriber running ingest → generate →
  validate → repair → store. Long timeout (generation can be four sequential
  model calls), `min-instances=0`, scales on queue depth.

They split because their scaling profiles are opposite: the API is high-QPS and
low-latency, the worker is low-QPS and high-latency. One service sized for both
is sized wrong for both, and a slow generation would occupy a container that
should be answering polls.

*Prototype:* one process, both roles, no scaling.

### 4. Vertex AI — the model

Behind the same `LLM.complete_structured(prompt, schema)` port the prototype
uses. Vertex is the deployment reason rather than a capability one: IAM instead
of a raw API key, VPC-SC reachability, and billing consolidated with the rest of
the project.

Structured-output support is the requirement the port depends on. The
`additionalProperties: false` guarantee removes the missing-field and
stray-field violation classes before the first validation, and losing it would
push those back into the repair loop.

*Prototype:* `AnthropicAdapter` against the public API, key from the
environment. Swapping to Vertex is a new adapter class implementing the same
port — the pipeline does not change.

### 5. Firestore — jobs and documents

Two collections mirroring the SQLite tables:

- **`jobs/{job_id}`** — `status`, `template_id`, `draft`, `used_fallback`,
  `repair_attempts`, `fact_count`, `dedup_key`, timestamps.
- **`companies/{company_id}/pdfs/{pdf_id}`** — filename, role, GCS URI,
  extracted facts once ingested.

The prototype's job row is already a status field plus a merged JSON payload —
which is a Firestore document. That shape was chosen for this migration.

`GET /jobs/{job_id}` reads the document directly. Clients that prefer push over
polling can use a Firestore realtime listener with no server change.

*Prototype:* SQLite, same fields.

## Cost at scale

Per piece of collateral, LLM input tokens dominate — everything below is noise
next to the ~$0.003 model spend ([DESIGN.md](DESIGN.md#cost-model)).

| Component | Driver | Notes |
|---|---|---|
| Vertex AI | ~$0.003/piece | dominant; repairs add ~30% on hard cases |
| Cloud Run (worker) | CPU-seconds | scales to zero between jobs |
| Cloud Run (API) | request count | `min-instances=1` is the floor cost |
| Pub/Sub | per message | negligible at any realistic volume |
| Firestore | reads/writes | polling drives reads — realtime listeners cut this |
| Cloud Storage | GB-months | PDFs are small and cold |

The one line worth watching is Firestore reads: aggressive client polling on a
long generation multiplies reads against a document that changes twice. Either
back off the poll interval or switch to listeners.

## Failure modes

| Failure | Handling |
|---|---|
| Model call fails | Job marked `failed` with the error; message acked. Not retried — a provider error is not a contract error, and blind retry doubles the bill. |
| Worker crashes mid-job | Message unacked, redelivered. Dedup key prevents a duplicate *submission* creating a second job; the redelivered job re-runs from the start. |
| Repair budget exhausted | Deterministic fallback. Not a failure — a degraded success, flagged `used_fallback`. |
| Poison message | Dead-lettered after 3 attempts, alert fires. |
| PDF unreadable | Job `failed` at ingest with the specific error, before any model spend. |

**Not implemented anywhere:** per-tenant rate limiting, a spend cap, and
authentication. The prototype has no auth at all. For a production deployment
the spend cap is the urgent one — a loop of duplicate submissions against a
per-call-billed model is the failure mode that costs real money.

## AWS

The same five roles map cleanly onto AWS — see
[architecture-aws.md](architecture-aws.md). No component here is GCP-specific
in a way that constrains the choice.
