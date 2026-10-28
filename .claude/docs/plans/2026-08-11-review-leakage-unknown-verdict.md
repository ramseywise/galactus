# review-leakage: unrun scan and excluded group key

Status: EXECUTED
Review: pending
Issue: #3
Branch: `GAL-3-review-leakage-unknown-verdict` (based on `origin/spike/consolidate-claude-setup`)

## Plan
Date: 2026-08-11
Based on: direct codebase inspection + the `ml-dryrun` spike (2026-08-11), no `## Research` section

### Goal

Make "no findings" from `review-leakage` mean *no leaks*, rather than *nobody looked*.

### Open Questions

| # | Question | Resolution |
|---|---|---|
| 1 | The task said `verdict=unknown`, but is there a `verdict` field? | **Resolved 2026-08-11 — no.** `ReviewFinding` ([review/models.py:153-170](../../../review/models.py#L153-L170)) has no `verdict`. `EvidenceState.QUESTION` ([models.py:19-23](../../../review/models.py#L19-L23)) already carries the semantics *"missing context prevents judgment ... phrased as a clarification request"* ([evidence-model.md:34-37](../../skills/review-shared/references/evidence-model.md#L34-L37)). **Reuse it; introduce no field.** |
| 2 | Should an unrun scan be able to block a merge? | **Resolved 2026-08-11 — no, report-only** (operator decision). `question_state_constrains_impact` ([models.py:196-206](../../../review/models.py#L196-L206)) caps `question` at `question`/`suggestion`/`nit`. Rule 1 therefore surfaces the unknown without gating the merge. |
| 3 | Does Rule 2 carry the same cap? | **Resolved 2026-08-11 — no.** A group key present in the frame while the split ignores it is directly observable in code, so it is `verified`/`hypothesis`, uncapped, and may block. |
| 4 | Does the plan touch the authoritative Python? | **Resolved 2026-08-11 — no.** See Out of Scope. |

### Approach

Both rules are one bug at two altitudes: a signal that never ran rendering identically to a
signal that came back clean. `SKILL.md` already makes exactly this argument for empty input
(§"Empty input is an error", L146-151), which itself descends from the shared
[empty-input rule](../../skills/review-shared/references/context-brief.md#L36-L43) — *"no
findings is indistinguishable from a clean review — so a broken diff command reads as an
approval."*

So the work is **extending an argument the skill already makes**, not adding a new concept.
That keeps it a pure prose change to one file, using evidence states that already exist and
already validate. The tradeoff accepted: Rule 1 findings cannot gate a merge (Open Question
2), so this buys legibility rather than enforcement.

### Out of Scope

- **`review/models.py` and `review/validate.py` — no edits.** Including relaxing the
  `question` → `merge_impact` cap. That cap governs all ten reporters; changing it from a
  leakage-docs task would be a cross-dimension behaviour change smuggled through a prose
  edit. If enforcement is wanted later it is its own issue.
- **No new schema field** (`verdict` or otherwise) — Open Question 1.
- **`finding-schema.md` / `evidence-model.md`** — unchanged. Both already describe the
  states being reused; no drift is introduced.
- **The `pocs/ml/lending/` tree** — cited as evidence, never edited. It is not present on
  this branch (see Risks).
- **The other nine `review-*` skills** — the reasoning generalises, propagating it does not.
- **The toolkit defect** DESIGN.md records (`group_col` forced *into* the feature matrix) —
  that is a `lebanese-blonde` fix, the inverse of Rule 2, and not ours.

### Steps

Two steps, one file. Both edit
[`.claude/skills/review-leakage/SKILL.md`](../../skills/review-leakage/SKILL.md).

---

#### Step 1: Rule 1 — an unrun single-feature AUC scan reports unknown, never clean

**Files**: `.claude/skills/review-leakage/SKILL.md` — new section after §"Empty input is an
error" (currently L146-151), immediately before §"Output" (L153-158).

**What**: Add a section establishing that the *absence* of a single-feature association scan
is itself reportable. Placed adjacent to the empty-input section because it is the same
argument one level in, and the reader should meet them together.

The section must state:

- The trigger: the diff scores a model, and no single-feature association scan (feature-vs-label
  AUC, or an equivalent correlation pass) exists for that frame.
- The output: one finding, `evidence_state: question`, `merge_impact: question`,
  `category: data`, `LK-` prefix.
- A **resolution trigger** — the concrete thing that closes it ("run a single-feature AUC scan
  over all columns and report any column above ~0.95"), phrased as a clarification request per
  the `question` state's contract in evidence-model.md:34-37.
- The prohibition: returning `[]` on that basis is the failure, not a clean review.
- The `quoted_span` guidance. Constraint 4 (L137-139) requires a literal source quote, and an
  absent scan has no line to quote — so the finding must anchor to the **scoring call or
  reported-metric line** that makes the missing scan matter.

**Snippet** (before → after):

```markdown
  the input was empty and fail loudly rather than reporting no findings.

+## An unrun scan is not a clean scan
+
+[section per the bullets above]
+
 ## Output
```

**Why this rule** — carry into the section as its justification: DESIGN.md's
`last_fico_range_high` / `last_fico_range_low` score **0.9511 with no post-outcome name
pattern and zero nulls** (§"The finding the name heuristic missed"). The name regex cannot
catch it; only the scan can. So an unrun scan is precisely the condition under which the most
dangerous leak class is invisible — and that is exactly when the skill currently returns `[]`.

**Test**:
```bash
cd ~/workspace/galactus && uv run pytest review/tests -q
```
(Regression only — asserts the prose edit broke no skill-loading or prefix test. This step
adds no Python and no test; see Test Plan for why.)

**Done when**:
- The section exists, and names `evidence_state: question` + `merge_impact: question`
  explicitly — a reader cannot infer a blocking finding from it.
- It states a resolution trigger.
- It says returning `[]` for an unrun scan is a failure.
- It gives the `quoted_span` anchor for a finding with no line of its own.
- `review/models.py` and `review/validate.py` are untouched (`git diff --stat` shows one file).

---

#### Step 2: Rule 2 — a group key present in the frame but excluded from the split

**Files**: `.claude/skills/review-leakage/SKILL.md` — §"Group leakage", L71-78 (extend the
existing bullets; do not create a new top-level section).

**What**: The section already gestures at this — L76-78 covers *"a repeated identifier column
(`*_id`) used as a feature or present in the frame while the split ignores it."* That is prose
describing a shape, not a rule with an output contract. Promote it:

- Make present-in-frame-but-absent-from-splitter a **named finding**, not an observation:
  `evidence_state: verified` when both the key's presence and the splitter's argument list are
  readable in the diff; `hypothesis` when the splitter is constructed elsewhere and only the
  key's presence is visible. Uncapped — it may carry `blocker`.
- **The weak-key clause**: where the key's discriminating power is weak, the finding *states
  the weakness* rather than being suppressed. DESIGN.md §"Group structure" is the worked case —
  1.03% of rows in multi-row groups, max group size 3, key inferred rather than observed, and
  the honest reading recorded as *"Group leakage is effectively unexercised on this proxy."*
  That is a finding with a caveat, not a reason for silence.
- Name the `quoted_span` anchor: the **splitter construction line** (the `KFold(...)` /
  `train_test_split(...)` call that omits `groups=`), since that is where the omission lives.

**Snippet** (before → after):

```markdown
 - Look for a repeated identifier column (`*_id`) used as a feature or present in
   the frame while the split ignores it. `GroupKFold` / `GroupShuffleSplit`
   absent where an entity ID exists is the shape.
+
+- **A group key present in the frame but not passed to the splitter is a finding**
+  [+ evidence-state rule, weak-key clause, quoted_span anchor per the bullets above]
```

**Test**:
```bash
cd ~/workspace/galactus && uv run pytest review/tests -q
```

**Done when**:
- The bullet is a rule with an output contract, not a description of a shape.
- Both evidence states are distinguished by what the diff makes readable.
- The weak-key clause says weakness is *stated*, never a reason to suppress.
- The `quoted_span` anchor is named.
- Still exactly one file changed.

---

### Test Plan

**This plan adds no automated test, deliberately.** `review/tests` covers the Python schema —
prefix-map drift, validator behaviour — and this change adds no Python. The rules are prose an
LLM reporter reads at dispatch; the artifact that would test them is a fixture diff plus a
scored reporter run, which is the review subsystem's eval harness and does not exist here.
Asserting on `SKILL.md` string contents would test that the words are present, not that the
reporter obeys them — a test that passes while the behaviour regresses.

| Check | Command | Expectation |
|---|---|---|
| Regression | `uv run pytest review/tests -q` | Passes; unchanged from baseline |
| Full suite | `uv run pytest --tb=no -q` | **339 passed** (baseline captured 2026-08-11) |
| Blast radius | `git diff --stat` | Exactly 1 file: `review-leakage/SKILL.md` |
| No Python | `git diff --name-only \| grep -c '\.py$'` | `0` |

Manual verification, the one that matters: re-read the amended `SKILL.md` against
`probe_frame_two.py` (`single_feature_aucs: {}` at L59, `group_col_available` /
`group_col_used` at L44 and L54-55) and confirm each rule now names an output for that input.

### Risks & Rollback

| Risk | Mitigation |
|---|---|
| **The evidence tree is absent on this branch.** `pocs/ml/lending/` exists only on `origin/GAL-ruff-baseline`; the default branch has no `pocs/` tree. | Verified the branches are **byte-identical** for `SKILL.md`, `review-shared/`, and `review/` (`git diff --stat` empty across all three). The base is sound. Cite DESIGN.md by section heading, not line number — the lines are not resolvable from this branch. |
| Rule 1 makes reviews noisier — any ML diff without a scan now emits a finding. | Bounded to diffs that **score a model**; the skill's existing "What NOT to flag" already exempts EDA/profiling with no scoring claim. `merge_impact: question` keeps it out of the blocking path. |
| Prose rules are unenforceable — a reporter can ignore them. | Accepted and inherent to the reporter design; `SKILL.md:16-20` argues the dimension exists as a reporter *because* these failures are invisible to lint. Not introduced by this change. |
| Vocabulary drift if a future change adds a real `verdict` field. | Open Question 1 records why `question` was reused; the reasoning is in the doc, not just the diff. |

**Rollback**: `git checkout .claude/skills/review-leakage/SKILL.md`. One file, no migration,
no state.

### Open Questions

All four resolved above (see the table under §Open Questions) — none blocking execution.

One item deferred by operator decision, recorded so silence reads as deliberate: **findings
from Rule 1 cannot gate a merge**, because `evidence_state: question` is capped below
`blocker` at [models.py:196-206](../../../review/models.py#L196-L206). Making an unrun scan
merge-blocking is a `models.py` change affecting all ten reporters. Not filed as an issue
(operator declined); if it is wanted later, this paragraph is the description.
