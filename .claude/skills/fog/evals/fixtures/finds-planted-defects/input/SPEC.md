# Spec — `digest`: weekly research digest service

**Status:** PLANNED
**Owner:** platform
**One-liner:** Every Monday 06:00, email each subscriber a digest of the papers published
last week that match their saved topics, with a two-sentence summary per paper.

---

## 1. Shape

```
cron → fetch_new_papers → match_topics → summarize → render_email → send
                                             ↓
                                        rank_by_relevance
```

Six steps, run per subscriber. The whole run is expected to take under four minutes for
our current 1,800 subscribers.

## 2. Components

### 2.1 `fetch_new_papers(since: date) -> list[Paper]`

Pulls from the arXiv export API, filtered to the eight categories we cover. We page
through until the API stops returning results.

```python
def fetch_new_papers(since):
    papers = []
    for category in CATEGORIES:
        try:
            papers.extend(_page_all(category, since))
        except Exception:
            continue
    return papers
```

The `continue` is deliberate — one flaky category should not sink the whole digest. If a
category is down we still ship the digest with the other seven.

### 2.2 `match_topics(papers, subscriber) -> list[Paper]`

For each subscriber we hold a list of saved topic strings ("diffusion models",
"mechanistic interpretability"). We ask the model which papers match, passing the
subscriber's topics and the paper titles + abstracts.

Returns the matching subset. A subscriber whose topics match nothing that week gets an
empty list, and we skip their email — no point sending an empty digest.

### 2.3 `rank_by_relevance(papers, subscriber) -> list[Paper]`

A second model call scores each matched paper 0–10 for how central it is to the
subscriber's interests. We take the top 5. This runs on the output of `match_topics`.

### 2.4 `summarize(paper) -> str`

One model call per paper. Two sentences, plain language, no jargon. The prompt instructs
the model to summarize *only* from the abstract provided and to say "summary unavailable"
if the abstract is missing or truncated.

**Abstention is preserved downstream:** `render_email` checks for the
`summary unavailable` sentinel and renders the paper with its title and a link only,
rather than dropping it. The subscriber sees the paper exists and that we could not
summarize it. This distinction is typed — `Summary` is
`Ok(text) | Unavailable(reason)`, and `render_email` must handle both arms.

### 2.5 `render_email(subscriber, papers) -> Html`

Jinja template. Deterministic. Enforces the 900-character body cap by truncating the
last summary and appending "…" — the cap is a hard layout constraint, so we count
characters in code rather than asking the model to be brief.

### 2.6 `send(subscriber, html)`

Hands off to SendGrid. We record a `sent` row per subscriber per week keyed on
`(subscriber_id, week)`, written **before** the SendGrid call, so a retry of a partially
failed run does not double-send. The key is unique-constrained in Postgres.

## 3. Topic-model migration

The saved topic strings are currently matched by the model (§2.2). We are replacing the
stored representation: each subscriber's free-text topics get re-encoded into our new
canonical topic taxonomy in a single migration pass, and the old `topics_freetext`
column is dropped in the same release. The new column is `topic_ids int[]`.

The migration is a one-time backfill over 1,800 rows. We have run it against a copy of
production and it completed in 40 seconds with no errors, so we are running it inline in
the release rather than as a separate staged job.

## 4. Quality

`summarize` is the only step whose output a subscriber reads directly, so it is the one
we care about. Before launch we will hand-check 30 summaries against their abstracts and
require 28/30 to be judged accurate by two reviewers.

## 5. Rollout

Behind the `DIGEST_ENABLED` flag, defaulting off. We enable it for the internal team
(12 accounts) for two weeks, then flip it for everyone. The flag is read at send time,
not cached, so turning it off stops the next run — that is our rollback for the send
path: flip `DIGEST_ENABLED=false` and no further digests go out.

## 6. Monitoring

We alert on:

- **Run duration** > 10 minutes (pager).
- **Send failures** — any non-2xx from SendGrid, per-subscriber, aggregated into a
  Slack message at end of run.
- **Zero-send runs** — if a run completes having sent zero emails, that fires the pager.
  A week where genuinely nobody matched is possible in principle but has never happened
  in the backtest, so we treat zero as a fault signal rather than a valid outcome.

## 7. Open questions

- Do we let subscribers set digest frequency (weekly vs daily)? Deferred to v2.
- What do we do about papers that get revised after we send? Probably nothing.
