# fog evals

Two tiers, per `akira/references/behavioral-eval-scaffold.md`.

## 1. Triggering eval (default, cheap) — `trigger-eval.json`

20 queries, roughly half should-trigger. The should-nots are the interesting half: fog
sits between three neighbours it must not steal work from —

| Near-miss | Why it isn't fog |
|---|---|
| `/war-game` | attacks a plan's **execution** (premortem, adversary, competing pressure) |
| `/assumption-audit` | finds the **load-bearing guesses**, not the uncertainty-handling surface |
| `/akira scan` | concrete **code defects in a diff**, not design-level not-knowing |
| `/proto-review` | plan fidelity + **merge verdict**; fog never decides ship/no-ship |

Plus the two shapes that look analytical but aren't: asking for an **observed metric**
("what's our p99 right now") and asking for a **summary** of a spec. fog interrogates a
design; it does not explain one or look one up.

```bash
python -m scripts.run_loop \
  --eval-set .claude/skills/fog/evals/trigger-eval.json \
  --skill-path .claude/skills/fog \
  --model <session-model-id> --max-iterations 5 --verbose
```

## 2. Behavioral eval — `evals.json` + `fixtures/` + `assertions/`

fog *decides* — which uncertainty is a defect, which is handled, what rank it carries — so
it earns a behavioral eval. Two cases, two distinct judgment paths:

| Case | Judgment tested |
|---|---|
| `finds-planted-defects` | Does it find four planted defects **without** flagging three correctly-handled controls? |
| `empty-target-is-error` | Handed a zero-byte target, does it report an **error** rather than a clean pass? |

### The planted-defects fixture

`fixtures/finds-planted-defects/input/SPEC.md` is a plausible, competent spec for a weekly
research-digest service. It is not uniformly broken — that is the point.

**Four planted defects**, one per fog stage that has a checkable output:

| id | Defect | Stage |
|---|---|---|
| D1 | `except Exception: continue` — a down category is indistinguishable from a quiet week | 2, collapse |
| D2 | empty `match_topics` → skipped email, same observable as a failed match | 2, collapse |
| D3 | topic migration drops `topics_freetext` in the same release; input to the backfill is destroyed | 3, reversibility |
| D4 | quality checked once at launch; §6 monitors only liveness — no detector for regression | 1 + 6, missing detector |

**Three negative controls**, written to *look* like the defect classes above:

| id | Correctly handled | The trap |
|---|---|---|
| N1 | `Summary = Ok \| Unavailable`, handled in `render_email` | word-matches "unavailable"; is actually a typed abstention done right |
| N2 | `(subscriber_id, week)` unique-constrained, written pre-send | looks like a double-send risk; is a named harness mechanism |
| N3 | 900-char cap counted in code | looks like a Stage 5 target; is already deterministic |

Two additional traps are baked into the prose rather than the structure: §3 justifies the
migration with a **successful rehearsal** (completion is not correctness — D3 stays
`fatal` regardless), and §5 offers `DIGEST_ENABLED` as "our rollback" when it covers the
**send path only** and does nothing for a dropped column. A run that reads §5 as covering
§3 has been taken in by the spec.

`expected.md` names every one of these with its grading rationale. It is prose, not a
golden output — fog has no single correct output.

### Scoring — precision and recall are separate scores

**This is the rule that makes the case worth running.** Recall invariants are `R*`,
precision invariants are `P*`, structural ones are `S*`. Do **not** average them into one
number:

> A run scoring **4/4 recall and 0/3 precision is a FAILING run**, not a 4/7 run.

A skill that flags everything scores perfect recall by construction — and is useless. The
negative controls exist so that over-firing is *visible in the score* rather than hidden
behind a good recall number. Report the two rates side by side, per run and across the N.

`P4`/`P5` catch the diffuse form of the same failure: ungrounded claims and an
all-`speculative` finding set. Both are fog's own stated failure mode ("producing fog
about the fog") and both are cheap script checks.

### Running + variance analysis (required)

Run each case **N=3–5 times** into separate scratch workspaces (copy `input/`, never
mutate the fixture), save each run's output, and grade the scripted subset:

```bash
python3 scripts/grade.py --case finds-planted-defects --output run1.md
python3 scripts/grade.py --case empty-target-is-error  --output run1.md --json
```

It parses claim blocks per `claim-schema.md`, scores every `check: script` invariant,
prints recall / precision / structural as **separate rates**, and lists the `judge`
invariants as a manual checklist. Grade every run, report **per-invariant pass rate** —
not a boolean.

- **Flaky recall invariant** (e.g. D2 found 3/5) → fog is non-deterministic on that defect
  class, or the assertion is under-specified. Both are findings.
- **Flaky precision invariant** → worse than flaky recall. It means the negative control
  fires sometimes, which is exactly the noise that makes a reviewer stop reading output.
- **Always-passes-regardless** → non-discriminating. Tighten or drop it. If a defect is
  found 5/5 by a model that never read `agent-uncertainty.md`, the fixture planted it too
  loudly.
- **Content variance with 100% invariant pass** → expected and healthy. Different phrasings
  and orderings across runs while every invariant holds means fog is free within its
  guardrails. The *set* of flagged sections should be stable; the prose should not be.

`script` invariants are deterministic and free — every rule that could be one is. The
judge is reserved for the residue that genuinely needs it: whether a claim names a
*mechanism* vs restates the code (R1, R2), whether a missing detector was named rather
than surprises enumerated (R5), and whether the blind-spots line is substantive (S4).

> **Advisor note.** `S1`/`S2` grade the dispatch: `fog-advisor` must be handed the spec and
> scope **only**, never the inline stage 1–3 findings, and its `FA-NNN` ids survive the
> merge. D1/D2/D3 sit deliberately inside the advisor's empty-input and reversibility
> passes, so independent corroboration is the expected result — and a run that briefs the
> advisor and then reports its agreement as corroboration has broken the check while
> appearing to pass it. That is why S1 is a judge invariant and not a grep.

## Not yet built

`war-game` and `assumption-audit` have no evals. This directory is the mold for both —
same two tiers, same precision-and-recall-scored-separately rule. Their fixtures want the
same treatment: negative controls alongside planted defects, because both skills fail in
the over-firing direction too (a war-game that finds every plan doomed, an audit where
every line is a load-bearing assumption).
