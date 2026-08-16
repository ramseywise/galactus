# runs/_index/ — the run record index

One JSON file per **training execution** — a different grain from the run directory
that produced it, which is why the name is prefixed: `_index` can never collide with a
run under `runs/ml/` or `runs/ai/`.

**Records are committed.** They carry aggregates only (Key Decision 7): metrics,
config, column *names*, a frame hash — never a row, a row index, or an identifier
value. `execution.folds` is a fold-*plan* description (kind, n_splits, reason), never
per-row indices.

**galactus does not define the format.** Records are written and read by
`experiments/io.py` from ai-project-template's registry
([AIT#83](https://github.com/ramseywise/ai-project-template/issues/83)) — versioned
JSON whose loader reconstructs the frozen dataclasses, so every load re-fires the
schema's own validation. A hand-edited record fails at load, not at the point where
its numbers get compared.

## Naming

```
{utc_timestamp}-{frame_hash[:8]}.json      e.g. 20260816T104512Z-5a2a4568.json
```

The frame hash covers the frame **as fitted** (post-drops), never the source file —
two runs whose derivation diverged get different hashes even from the same CSV.

## What lands here

- **Real runs** of a harness (currently `runs/ml/lending/src/run.py`) write here on
  every execution.
- **Dry-runs never write here** — they write the identical format to a temp path, so
  the index only ever contains records of real frames.

## Reading a record diff

Same `code.git_sha` + same `data.frame_hash` ⇒ the `metrics` block must reproduce. A
diff showing only `code.versions` or `resolved_config.toolkit` changed is the system
*working* — it names precisely which recorded input moved before any number did.
