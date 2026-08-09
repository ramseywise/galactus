# Behavioral-eval scaffold — the mold for judgment-shaped skills

Triggering evals (the default tier) answer "does the skill fire on the right prompts?"
Behavioral evals answer the harder question: **"given that it fired, did it do the right
thing?"** Only judgment-shaped skills need one. This file is the fixture + assertion +
variance mold so you stamp them consistently instead of hand-rolling each.

## When a skill earns a behavioral eval

It has a **verifiable output state** and a **non-trivial judgment** in producing it. Both
must hold:

- **State, not vibes.** The skill leaves a checkable delta — files rewritten, entries
  moved, a report emitted. If the only output is prose whose quality is purely subjective,
  grade it qualitatively (skill-creator's blind-comparison flow), not with assertions.
- **Judgment, not a script.** A skill that always does the same mechanical thing (lint,
  wiki-sync, template-update) has nothing to grade beyond "did it run" — that's a
  triggering eval plus maybe a smoke check, not behavioral. Behavioral evals are for skills
  that *decide* — what to keep, where something belongs, when to stop.

The sweet spot is a skill with **hard invariants over soft judgment**: the model exercises
judgment (which section, what to compress) but the result must satisfy checkable rules (no
section lost, length in budget). You grade the invariants; the judgment shows up as
*variance* across runs.

## Directory shape

Sibling to `references/`, per the norm:

```
<skill-name>/
├── SKILL.md
├── references/
└── evals/
    ├── evals.json                 # trigger prompts + behavioral cases (skill-creator format)
    ├── fixtures/
    │   └── <case-name>/           # a pre-state the skill runs against
    │       ├── input/             # files copied into a scratch workspace before the run
    │       └── expected.md        # human-readable "what a good run looks like" (not asserted)
    └── assertions/
        └── <case-name>.json       # graded invariants for that case
```

**Fixtures are pre-states, not answers.** `input/` is the world before the skill runs; the
skill mutates a *copy* of it in a scratch dir. Assertions compare the post-state to the
invariants — they never diff against a golden output file (identity/creative skills have no
single correct output; a golden file would make every valid variation a false failure).

## The assertion format

Reuse skill-creator's grading contract exactly — the viewer depends on it. Each expectation
carries `text` / `passed` / `evidence` (NOT `name`/`met`/`details`). Prefer assertions a
**script** can check over ones needing an LLM judge: state-delta invariants (line counts,
section presence, file existence, "accumulator cleared") are deterministic and free.

```json
{
  "case": "five-pending-entries",
  "invariants": [
    {
      "text": "No section header from any seed file was removed",
      "check": "script",
      "how": "diff section headers (^#{1,3} ) pre vs post for each seed; set must not shrink"
    },
    {
      "text": "Each transformed seed is 60-80% of its original line count",
      "check": "script",
      "how": "wc -l post / wc -l pre in [0.60, 0.80] per file"
    },
    {
      "text": "Accumulator pending section is empty and synthesis date advanced",
      "check": "script",
      "how": "pending block has 0 tagged entries; 'Last synthesized' date > fixture date"
    },
    {
      "text": "First-person voice preserved (vulnerable/identity lines survive)",
      "check": "judge",
      "how": "grader confirms named voice lines from expected.md still present post-run"
    }
  ]
}
```

`check: script` invariants run deterministically and cost nothing — put every rule that can
be one here. Reserve `check: judge` for the genuinely subjective residue (voice, coherence)
and keep it to a minority of the invariants, or the eval inherits judge flakiness.

## Variance — the part triggering evals don't have

A judgment skill run once tells you almost nothing; run each case **N=3–5 times** and record
per-invariant pass rate. What variance surfaces:

- **Flaky invariant** (passes 3/5) → either the skill is non-deterministic on that rule (a
  real bug — e.g. sometimes over-compresses) or the assertion is under-specified.
- **Always-passes-regardless** → non-discriminating; the assertion isn't testing the skill.
  Drop it or tighten it.
- **The judgment itself** → for creative skills, moderate variance in *content* with 100%
  invariant pass is the *goal*: the skill is free within guardrails. Zero content variance
  means it's mechanical (didn't need a behavioral eval) or overfit to the fixture.

Report pass-rate per invariant across the N runs, not a single boolean. skill-creator's
existing per-eval variance tooling ("high-variance evals (possibly flaky)") reads this.

## Building one — the loop

1. Pick 2–4 cases that exercise **distinct judgment paths**, not distinct inputs. For
   synthesize: (a) mixed `[confirmed]`/`[corrected]`/`[discovered]` tags, (b) a learning
   that maps to no seed file (must be *reported*, not forced in), (c) an over-full backlog
   (must batch at 20, not truncate). Each tests a different decision.
2. Build each `fixtures/<case>/input/` as a minimal but real pre-state — a couple of short
   seed files + an accumulator, not the whole repo.
3. Write `expected.md` in prose: what a good run does, and the specific lines that must
   survive (feeds the judge invariants).
4. Derive `assertions/<case>.json` — every checkable rule as `script`, the residue as
   `judge`. Most invariants come straight from the skill's own "Critical Rules" section.
5. Run N times into scratch workspaces, grade, report per-invariant pass rate + content
   variance.

The invariants you assert should be the skill's stated contract turned executable — if the
SKILL.md says "transform, never truncate" and "60–80% length," those are your first two
assertions verbatim.
