---
name: ml-transform
description: >
  Transformation advisor for a tabular frame — profiles dtypes, cardinality, missingness
  pattern, skew, outliers, and target balance, then recommends a transform + sampling
  config with a stated reason per column and emits the ColumnPlan the transform layer
  consumes. Advisory: it proposes, the operator approves; it never transforms silently.
  Triggers on: "profile this dataset", "what transforms does this need", "how should I
  encode this", "handle the imbalance", "ml-transform", "/ml-transform".
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Write
---

# /ml-transform

The profiling pass the pipeline otherwise skips. Reads a frame, states what is in it, and
recommends a treatment **per column with a reason** — then stops and waits.

This is the skill that runs *before* `/ml-select`, because the answers that decide the
model config (time structure, grouping, balance, cardinality) are properties of the data,
not of the framing.

## Usage

```
/ml-transform <path-to-frame> [--target <column>] [--output path/to/column-plan.md]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `<path-to-frame>` | required | CSV / Parquet the profile runs against |
| `--target` | none | Label column — enables balance and target-relationship checks |
| `--output` | `.claude/docs/column-plan.md` | Where the profile + recommendations are written |

---

## The rule this skill exists to enforce

**Profile, then plan.** Not the reverse, and not both at once.

- **It recommends; it does not apply.** Every output is a proposal with a reason
  attached. The operator approves, edits, or rejects. A transform applied during
  profiling is a decision made by whoever happened to be running the tool.
- **It never mutates the source frame.** Reads only. If a recommendation needs a
  demonstration, compute it into a scratch value and say so — do not write.
- **A column with no recommendation is stated, not omitted.** "47 columns, 41
  recommendations" means six columns were passed over, and the operator cannot see which
  six. Every column appears in the plan, including the ones whose recommendation is
  `passthrough` and the ones the profiler could not read.

## Step 1 — Profile

Compute and report, for the frame as a whole:

| Property | What to report | Why it changes the plan |
|---|---|---|
| shape | rows × columns | Sets whether cardinality thresholds are meaningful at all |
| dtypes | per column, and the ones pandas guessed wrong | An ID read as int64 becomes a numeric feature silently |
| cardinality | distinct count + share, per categorical | Decides one-hot vs target vs collapse |
| missingness | share **and pattern** — per column, and co-occurrence across columns | Decides impute vs indicator vs drop |
| skew | per numeric, plus min/max/quantiles | Decides scaler family and whether to log |
| outliers | count by IQR and by z-score, per numeric | Decides robust scaling vs removal |
| target balance | class shares, or the target's distribution | Decides sampling strategy |
| constants / near-constants | columns whose top value covers ≥99% of non-null rows | They are noise with a name |
| duplicate rows | count, and duplicate-on-key count if a key is known | Inflates every metric downstream |

**Report the numbers, not adjectives.** "`employer`: 4,182 distinct over 51,000 rows
(8.2%), top value 1.1%" is a profile. "`employer` is high-cardinality" is a conclusion
without its evidence, and the operator cannot check it.

**Every threshold this skill uses is stated here, and none of them are yours to invent.**
Near-constant is ≥99% top value. High cardinality is >50 distinct *or* >5% of rows,
whichever trips first. Rare-category floor is 1% (see the degenerate case below). Strong
imbalance is <20% minority. If the data puts you in a case none of these cover, that is an
`## Unresolved` entry naming the missing threshold — **not** an invitation to pick one and
carry on. A threshold chosen silently at profile time becomes an unreviewable constant in
the config.

**Check every integer column against "is this actually categorical?"** — not just the
obvious identifiers. A binary flag, a status code, a zip code, and a row ID are all
`int64`, and all four become scaled numeric features if the dtype is taken at face value.
The tell is distinct count against row count at both ends: near 100% distinct is an
identifier, a handful of distinct values is a category wearing an integer's dtype. Report
which of the two each integer column is, and on what count.

### Missingness: the pattern matters more than the rate

Report the rate, then ask whether it is **structural**. Two columns missing on exactly the
same rows is one fact, not two, and it usually means the rows came from different sources
or a different era.

- Missing **at random** → impute, and the imputation is uncontroversial.
- Missing **not at random** → the absence *is* the signal. A missing phone number, an
  absent bureau record, a null timestamp on an event that never happened. **Imputing to
  the median destroys the information.** Recommend a missing-indicator alongside
  whatever imputation happens, so the signal survives.
- Missing **because it did not exist yet** → this is not missingness, it is a leak in
  waiting. A field populated only after the outcome will be dense in the label class and
  null elsewhere. Flag it as a **leakage candidate** and hand it to the leakage review.

State which of the three each column looks like, and on what evidence.

**Before recommending an indicator, check whether the frame already carries one.** A
column that is null exactly where an existing flag is set does not need a second copy of
that flag — `thin_file` and `is_null(bureau_score)` are the same feature twice, and the
duplicate spends variance on nothing. Test it: if the null mask matches an existing column
bit-for-bit, recommend **imputation alone** and name the column that already carries the
signal. If it matches only partially, recommend the indicator and report the overlap —
partial agreement means the two are measuring different things and both survive.

## Step 2 — Recommend, with a reason per column

One row per column. The reason column is not decoration — it is the artifact the operator
reviews, and a recommendation whose reason is "standard practice" has not been justified.

```markdown
| column | dtype | profile | recommendation | reason |
|---|---|---|---|---|
| <numeric> | float64 | skew <s>, <p>% > q99 | robust scaler | heavy right tail; standard scaling would let the tail dominate |
| <hi-card cat> | object | <n> distinct (<p>%) | collapse rare (<1%) → target encode | one-hot adds <n> columns; target encoding must be fitted inside the fold |
| <nmar field> | object | <p>% null, disjoint from <other> nulls | indicator + constant fill | not-missing-at-random: absence is itself a state, not an unknown |
| <post-outcome> | object | <n> distinct, <p>% null | **leakage candidate — exclude** | populated only after the outcome resolves; caused by it, not predictive of it |
| <row id> | int64 | <n> distinct (100%) | drop | row identifier read as numeric; carries no signal and will be scaled |
```

**The placeholders above are deliberate, and they are the reason this example has no
real column names or figures in it.** An example built from a plausible domain primes the
answer: the skew, the null rate, the distinct count all look derived, and the closer the
example's domain sits to the frame in front of you, the harder the pull. Every number in
your table comes from the profile you just computed. If a figure in your output matches
one in this file, you copied it.

### The four recommendations that carry the weight

**High cardinality** → collapse rare categories to an `other` bucket at a stated
frequency floor, then target-encode. Say both parts. And say the constraint that makes it
safe: **target encoding is fitted inside the CV fold**, never on the full frame — an
encoder fitted before the split has already seen the labels it is being evaluated against.

*When the floor is degenerate — every category falls below it — do not collapse.* A
column with 1,200 employers whose largest is 0.2% of rows has no majority to collapse
toward; applying the 1% floor literally merges the entire column into a single `other`
bucket and deletes the feature while appearing to treat it. **Target-encode directly, in
fold, with no collapse step, and say that the floor was degenerate and why.** This is a
flat-distribution column, not a long-tailed one, and the distinction is visible in the
profile: check the top value's share before recommending a collapse. Collapse earns its
place when a few frequent categories carry most of the rows and a tail of singletons does
not — no head, no collapse.

**Not-missing-at-random** → missing-indicator plus imputation, never imputation alone.
The indicator is the recommendation; the imputation is just what fills the hole
afterwards.

**Imbalance** → a sampling strategy, and name which one and why:

| Balance | Recommend | Because |
|---|---|---|
| mild (≥ ~20% minority) | `class_weight` | Cheapest, no synthetic rows, no fold-order hazard |
| strong, numeric-only features | `smote` | Interpolation is meaningful between numeric points |
| strong, mixed-type features | `smotenc` | Plain SMOTE interpolates categorical codes into values that do not exist |
| strong, and majority is cheap to lose | `under` / `smote_tomek` | Trades data volume for a cleaner boundary |

**"Feature types" in that table means the *source* dtypes, not the post-transform ones.**
The distinction decides `smote` against `smotenc` and it is not obvious: once a
high-cardinality column is target-encoded it is numerically valued, so a frame that looked
mixed can be argued into looking all-numeric, and the argument produces the wrong sampler.
Read the types off the frame as it arrives — if any categorical column is present in the
source, the answer is `smotenc`. The reason is ordering again: the sampler is constructed
with `categorical_indices` from the column plan, and the plan describes the frame going
in.

Every one of these carries the same invariant, and it is stated with the recommendation,
not assumed: **resampling happens inside the fold, on training data only.** Never before
the split, never on validation. A sampler applied to the full frame produces a score that
cannot be reproduced on real traffic.

Minority share is read against the **20% line**, and both sides of it are named in the
table — anything under 20% is strong. This is stated because it is the single place in
this skill where a misread produces a plausible-looking wrong answer rather than an
obviously broken one.

**Skew and outliers** → say which of the two you are treating and do not conflate them. A
long tail is a scaling problem (robust scaler, or log the column); a genuine outlier is a
data problem (investigate, then remove or keep deliberately). Recommending removal for
skew deletes real data because it was inconveniently shaped.

## Step 3 — Emit the `ColumnPlan`

The structured half, consumed by `build_transformer(plan, ...)`.

```markdown
## ColumnPlan
numeric:        [<col>, <col>, <col>]           # every numeric column, overrides included
numeric_scaler: <standard|minmax|robust|none>   # the group default
  overrides:                                     # only where a column disagrees
    <col>: robust                                # skew <s>; the rest are symmetric
categorical:    [<col>, <col>]
categorical_encoding: onehot                     # all under 20 distinct
high_cardinality: [<col>, <col>]                 # collapse <1% → target encode, in-fold
datetime:       [<col>]                          # decompose: year, month, dow, days_since
missing_indicators: [<col>]
  nmar_without_indicator:                        # NMAR, but the signal already exists
    <col>: <existing column that carries it>
drop:           [<col>]                          # identifier
exclude_leakage: [<col>, <col>]
passthrough:    []

## Rows
duplicates:     <n> exact-duplicate rows (<n> including <key>)
recommendation: <dedup before split | investigate first | keep — they are real repeats>

## Sampling
strategy:       <none|class_weight|smote|smotenc|under|over|smote_tomek>
reason:         <minority share, feature types — the two facts that decide it>
applied:        in-fold, training split only

## Unresolved
- <what the profile surfaced and cannot settle>.
  Trigger: <the event that resolves it>.
```

Four notes on the schema, each covering a case the flat version cannot express:

- **`numeric_scaler` is a group default with per-column overrides.** One scaler for the
  whole numeric block is the common case and stays the common case, but a frame where one
  column is heavily skewed and the rest are symmetric is not unusual, and forcing robust
  scaling on all of them to accommodate one is a silent decision. Set the default to what
  fits most of the block, then override the exceptions by name with the figure that
  justifies each. If every column needs an override, the default is wrong. **An overridden
  column stays in `numeric:`** — the override changes its scaler, not its membership, and
  a column absent from `numeric:` is absent from the transformer.
- **`nmar_without_indicator` records the NMAR columns whose indicator was suppressed**
  because the frame already carries the signal. Without it, a correctly-suppressed
  indicator leaves `missing_indicators: []`, which reads identically to a frame that had
  no not-missing-at-random columns at all — the profile's classification and the reasoning
  behind the suppression both vanish at exactly the point a downstream reader would want
  them. The field names the column that carries the signal instead, so the decision stays
  visible to anyone reading only the plan.
- **`## Rows` holds row-level actions**, because deduplication is a real recommendation
  that the column buckets have no slot for. Duplicates get profiled in Step 1 and then
  have nowhere to land; without this section the finding degrades into prose that no
  consumer reads. Exact duplicates on a frame with a natural key are usually an import
  artifact; on one without, they may be genuine repeat events — so this recommends and
  states which case it thinks it is, like everything else here.
- **`## Sampling` carries its `reason` inline**, since the strategy is chosen from exactly
  two facts (minority share, feature types) and a strategy without them is unreviewable.

**`exclude_leakage` is a recommendation, not a verdict.** This skill flags columns whose
*shape* looks post-outcome — dense exactly where the label is positive, null elsewhere,
or named for something that happens after the decision. Confirming that a column is
actually caused by the outcome takes domain knowledge the profiler does not have. So it
proposes exclusion and says why; the operator confirms, and the leakage review checks the
code that results.

When a target is supplied, one statistic backs each leakage flag and it is the same one
every time: **the null mask against the label.** Report the agreement — "non-null on 100%
of positives, 0% of negatives" is the shape that convicts; "non-null on 61% of positives,
54% of negatives" is a column that merely correlates and stays in. This is a deliberately
narrow check, not a feature-importance pass: a column that predicts the label well is
doing its job, and only a column whose *presence* tracks the label is evidence of
ordering. Do not compute a general battery of feature-vs-target statistics — profiling is
not modelling, and a strong association discovered here has no recommendation attached to
it.

**`Unresolved` is mandatory and behaves like `/ml-select`'s parked list.** Anything the
profile surfaced that the profile cannot settle goes here with a trigger. An empty
section reads `None — nothing in the profile needs a decision from outside the data.`

It takes **any** unstated input a recommendation rests on, not only the thresholds
enumerated in Step 1. A named transform with an unnamed parameter is the common case: the
`days_since` reference date, the frequency floor when the stated one degrades, whether a
column is genuinely the natural key. Each is a value someone has to choose, none is a
threshold in the Step 1 sense, and all three are invisible in the plan if the section is
read narrowly. The test is not "is this a threshold" — it is **"did I supply a value the
skill never gave me, and would a different reader have supplied a different one?"** If
yes, it belongs here, with the trigger that resolves it.

## Hand off

| Output | Consumed by |
|---|---|
| `numeric`, `categorical`, `high_cardinality`, `datetime`, `missing_indicators`, `drop` | `build_transformer(plan, ...)` |
| `## Sampling` | `build_sampler(strategy, categorical_indices=..., ...)` |
| `exclude_leakage` | the operator's confirmation, then the feature list — and the leakage review's context |
| `## Unresolved` | `/ml-select`'s parked list, and the plan doc's open questions |

Then `/ml-select` — which requires this profile to exist before it will name a model.

## Constraints

1. **Never transform. Never write to the source frame.** Read, profile, recommend, stop.
2. **Every column appears in the plan**, including `passthrough` and unreadable ones. A
   column that is silently absent has been decided about without anyone seeing the
   decision.
3. **Every recommendation carries a reason drawn from the profile**, citing the number
   that motivated it. "Standard practice" and "usually best" are not reasons; they are
   the absence of one wearing a confident tone. **No figure in the output is copied from
   this file** — every number traces to the frame that was just read.
4. **Never invent a threshold.** The ones this skill uses are listed in Step 1 and they
   are the whole set. A case none of them cover is an `## Unresolved` entry naming the
   missing threshold, not a number chosen on the spot to keep the pass moving.
5. **A rule that degrades to nonsense on this frame is not applied anyway.** Rare-collapse
   on a flat distribution, an indicator duplicating a column that already exists, one
   scaler forced across columns that disagree — in each case the recommendation is the
   handled variant, stated as such, not the literal rule producing a broken column.
6. **State the in-fold invariant wherever target encoding or resampling is recommended.**
   Both are correct operations that become leaks purely by ordering, so the ordering
   travels with the recommendation rather than being assumed downstream.
7. **Flag leakage candidates; do not adjudicate them.** Shape-based suspicion plus the
   evidence, handed to someone who knows the domain.
8. **Report numbers, not adjectives.** Every characterisation of a column is checkable
   against a figure in the profile.
