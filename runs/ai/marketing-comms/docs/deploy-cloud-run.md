# Deploying the prototype to Cloud Run

**What this deploys:** the single-process prototype — FastAPI, SQLite,
in-process background tasks — packaged by [the Dockerfile](../Dockerfile). It
is a stepping stone for demos and pilots, **not** the five-component target in
[architecture-gcp.md](architecture-gcp.md). Every constraint below follows
from that difference; none of them apply once the Pub/Sub + Firestore design
replaces this shape.

## Build and deploy

From the repo root:

```bash
gcloud artifacts repositories create galactus --repository-format=docker \
    --location=europe-west1   # once

gcloud builds submit \
    --tag europe-west1-docker.pkg.dev/$PROJECT/galactus/marketing-comms:latest .

gcloud run deploy marketing-comms \
    --image europe-west1-docker.pkg.dev/$PROJECT/galactus/marketing-comms:latest \
    --region europe-west1 \
    --min-instances 1 \
    --max-instances 1 \
    --concurrency 40 \
    --timeout 300 \
    --memory 1Gi \
    --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest,GALACTUS_API_KEY=galactus-api-key:latest" \
    --set-env-vars "GALACTUS_DB_PATH=/tmp/galactus.db"
```

Store both secrets in Secret Manager first (`gcloud secrets create ...`);
never pass credentials via `--set-env-vars`.

## Why these flags

- **`--max-instances 1` is load-bearing, three times over.** SQLite is a
  single-writer file on instance-local disk; the per-caller rate limiter and
  the concurrent-job semaphore both live in process memory. A second instance
  would mean a second database, a second rate window, and a second job gate —
  each silently halving the guarantee it implements. Scaling out is the
  point at which you adopt the real design: Firestore for state, an edge
  quota (API Gateway / Cloud Armor) for rate limiting, Pub/Sub for the queue.
- **`--min-instances 1`.** Generation jobs run in `BackgroundTasks`, which
  die with the instance. Keeping one instance warm avoids both cold starts on
  the interactive path and needless job loss from scale-to-zero. Jobs
  orphaned by a restart are failed loudly at the next boot
  (`fail_stale_jobs`), so clients see an explicit error, not an eternal poll.
- **`--timeout 300`.** Generation is up to four sequential model calls behind
  a 202; the request that matters (`POST /collateral`) returns instantly, but
  the instance must live long enough for the background work. Cloud Run only
  guarantees CPU while a request is in flight — with `min-instances 1` and
  steady polling this is fine in practice for a demo; it is another reason
  the real design moves work to a worker tier.
- **`GALACTUS_DB_PATH=/tmp/galactus.db`.** Instance-local and **ephemeral**:
  a deploy or instance restart wipes uploads and job history. Acceptable for
  a demo, unacceptable for a pilot with real client PDFs — that is the
  Firestore migration. (A GCS FUSE volume is not a fix: SQLite's locking does
  not survive object storage.)

## Configuration knobs

All optional, validated at startup — an invalid value fails the deploy, not a
later request.

| Env var | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Provider credential (Secret Manager) |
| `GALACTUS_API_KEY` | unset = open | Shared-secret `X-API-Key` gate |
| `GALACTUS_MODEL` | `claude-sonnet-5` | Generation model |
| `GALACTUS_MAX_REPAIRS` | `3` | Repair-loop budget |
| `GALACTUS_DB_PATH` | unset = in-memory | SQLite file path |
| `GALACTUS_MAX_PDF_PAGES` | `40` | Ingest page cap per PDF (upload 413s over it) |
| `GALACTUS_RATE_LIMIT_PER_MINUTE` | `10` | `POST /collateral` per caller; `0` disables |
| `GALACTUS_MAX_CONCURRENT_JOBS` | `4` | Simultaneous generations; excess waits as `queued` |
| `GALACTUS_RETENTION_DAYS` | `30` | Sweep age for finished jobs and PDFs; `0` disables |
| `GALACTUS_LOG_LEVEL` | `INFO` | structlog level (JSON lines on stdout → Cloud Logging) |

## What this deployment does not give you

Unchanged from the architecture doc's gap list: per-tenant identity (the
shared key means every keyholder sees every company) and a hard spend cap
(the rate limit and page cap bound the *rate* of spend, not its total).
Treat both as blockers for anything beyond a controlled pilot.
