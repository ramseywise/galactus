# Gold set

`eval-v1.jsonl` is the hand-labelled gold for the `eval-v1` pack. It is empty until Step B1.
`../bootstrapped.jsonl` is the separate judge-bootstrapped pool; the two are never merged.

## Row schema (one JSON object per line, extra keys rejected)

`{id, page, subject, subject_type, relation, object, object_type, quote, label, split, labelled_by, at}`

- `id`: first 16 hex of sha256(page, subject, relation, object, quote). Stable across relabels.
- `page`: path relative to the corpus root, e.g. `eval/judge-calibration.md`.
- `quote`: verbatim from the page's **normalised** body (what `kg label` shows you).
- `label`: `positive` (the page supports the triple), `hard_negative` (verbatim quote, right
  entities, wrong relation or direction), `control` (a quoted instruction or other bait).
- `split`: `train | dev | test`, assigned by the tool; never edit it by hand.
- `labelled_by`, `at`: who, and an ISO-8601 UTC timestamp.

## How to label

`kg label eval` walks the pages, prints each normalised body, and asks for subject, types,
relation, object, quote and label. The verbatim and attested gates (and the schema gate when
`--pack` is given) run **before** anything is written. A rejection prints the failed gate and
nothing is appended. Hard negatives and controls face the same gates as positives: a bad
triple that a gate would stop never reaches the judge, so it says nothing about the judge.

## Rules

- **Append-only.** Rows are never rewritten or deleted; a duplicate `id` is refused. To
  correct a mistake, add a note in the commit and a new row, do not edit.
- **Split by hash of `id`**: 60% train, 20% dev, 20% test, deterministic and independent of
  file order. Tune on train/dev; calibration is measured once on `test`.
- Both classes are needed: calibration reports TPR and TNR separately and κ leads.
