# Cloud architecture — AWS mapping

**Status: design target, not implemented.** Appendix to
[architecture-gcp.md](architecture-gcp.md), which carries the reasoning. This
document covers the mapping and the three places where it is *not* a
one-to-one swap.

## Mapping

| Role | GCP | AWS |
|---|---|---|
| PDF bytes | Cloud Storage | S3 |
| Job queue | Pub/Sub | SQS (+ EventBridge for scheduled work) |
| API tier | Cloud Run | Lambda + API Gateway, or App Runner |
| Worker tier | Cloud Run (push subscriber) | Lambda (SQS event source) |
| Model | Vertex AI | Bedrock |
| Jobs + documents | Firestore | DynamoDB |
| Dead letter | `jobs-dlq` topic | SQS redrive policy → DLQ |
| Logs | Cloud Logging | CloudWatch Logs |

The architecture is unchanged: upload to object storage, enqueue a job id,
process on a worker, call a model behind a port, write a document, poll it.

## Where the mapping is not clean

Three differences change design decisions rather than just names.

### 1. Lambda's timeout ceiling

Lambda caps at **15 minutes**. Generation is up to four sequential model calls
plus PDF ingest — comfortably inside that today, but it is a hard ceiling where
Cloud Run's is configurable. Two consequences:

- A larger PDF corpus, or a bigger repair budget, brings the ceiling into play.
- Vision ingest over a long document is the realistic path to hitting it, since
  it is per-page.

If generation ever approaches the limit, the worker moves to Fargate or App
Runner. The pipeline code does not change — it is a plain async function — but
the deployment target does.

### 2. SQS FIFO versus Pub/Sub ordering keys

The GCP design uses the dedup key as a Pub/Sub `orderingKey`. On AWS:

- **Standard SQS** — at-least-once, no dedup. The dedup key must be enforced at
  the DynamoDB write with a conditional put.
- **FIFO SQS** — provides 5-minute content-based deduplication and exactly-once
  processing within that window, at lower throughput.

FIFO's 5-minute window is shorter than a sensible dedup window for this workload
(a user resubmitting the same brief an hour later should still be deduped). So
the queue-level dedup is a convenience, not the mechanism: **DynamoDB
conditional writes on `dedup_key` are the actual guarantee** in either case.
Same conclusion on GCP — Pub/Sub ordering keys are not a dedup primitive either.
Correctness belongs in the datastore.

### 3. Bedrock structured output

Vertex and Bedrock both expose Claude, but structured-output enforcement differs
by model and API surface. The pipeline depends on `additionalProperties: false`
and `required` actually being enforced — that is what removes the missing-field
and stray-field violation classes before validation
([DESIGN.md](DESIGN.md#the-limits-are-carried-three-ways-and-only-one-is-binding)).

This is the one item worth verifying against current docs before committing,
because it is load-bearing rather than cosmetic. If enforcement is weaker on a
given Bedrock model, the fix is contained: those two violation kinds already
exist in the validator (`required`, `unknown_field`) and both already have
deterministic fallback repairs. The loop absorbs them — at the cost of a higher
first-pass failure rate and more repair calls. Degraded, not broken.

## What does not change

- **The layout contract.** `validate` and `fallback` are pure functions of a
  draft and a template. No cloud dependency, and the contract guarantee holds
  identically on either provider.
- **The LLM port.** `complete_structured(prompt, schema)` — Bedrock is another
  adapter alongside the Anthropic one.
- **The document shape.** The job document maps to a DynamoDB item as directly
  as to a Firestore document; `job_id` is the partition key.
- **The observability model.** structlog JSON lines are ingested by CloudWatch
  as readily as by Cloud Logging; the span fields (`job_id`, `stage`, `attempt`,
  `violation_count`) are unchanged.

## Choosing

There is no strong technical argument either way for this workload — it is five
commodity components, and both platforms provide all five. The decision should
follow existing infrastructure, existing IAM, and where the team already
operates.

One asymmetry worth noting: Cloud Run has no execution-time ceiling to design
around, which makes it the lower-friction choice if generation is expected to
grow longer — more repair attempts, larger corpora, heavier vision ingest.
