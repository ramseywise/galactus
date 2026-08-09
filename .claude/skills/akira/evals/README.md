# akira evals

Two tiers, per the skills norm (`2026-07-18-skills-refs-evals-norm.md`) and
akira's `references/behavioral-eval-scaffold.md`.

## 1. Triggering eval (default, cheap) — `trigger-eval.json`

20 realistic queries, ~half should-trigger / half should-not. Covers 3 primitives + full
flow (`scan`/`wander`/`dao`/bare `/akira`), fires on natural phrasings
("quality check", "what did I miss", "interrogate the intent, find the bugs, fix what's
safe"), and — critically — does
NOT false-trigger on the near-misses akira sits between: `/workflow-review` (plan
fidelity + merge verdict), `/sanyi audit` (contract), plain `make test`, and
commit/refactor/debug requests.

Run via skill-creator's Description Optimization loop:

```bash
python -m scripts.run_loop \
  --eval-set .claude/skills/akira/evals/trigger-eval.json \
  --skill-path .claude/skills/akira \
  --model <session-model-id> --max-iterations 5 --verbose
```

## 2. Behavioral eval (akira is judgment-shaped) — `evals.json` + `fixtures/` + `assertions/`

akira *decides* — which tier a finding is, which questions matter, when to revert — so it
earns a behavioral eval. Three cases, each a **distinct judgment path**, not a distinct
input:

| Case | Judgment tested |
|------|-----------------|
| `wander-question-quality` | Does wander name the *decisions the diff walked past* (unbounded cache, cached-error) vs restating the code? |
| `dao-triage-tiering` | Does dao tier a dead import **low** (auto-apply) and an error-path/contract change **high** (surface-only)? |
| `dao-revert-on-failure` | When an auto-applied low-radius fix breaks tests, does dao revert *that hunk only* and record it, leaving a green tree? |

`fixtures/<case>/input/` is a **pre-state** (a copy is mutated in a scratch dir — never the
fixture itself). `expected.md` is prose describing a good run + the lines a judge checks;
it is NOT a golden output (akira has no single correct output). `assertions/<case>.json`
holds the graded invariants — `check: script` where deterministic (byte-identical file,
test exit code, no-commit, run-summary bullet present), `check: judge` for the residue
(question specificity, tiering rationale).

### Running + variance analysis (required)

A judgment skill run once tells you nothing. Run **each case N=3–5 times** into separate
scratch workspaces, grade every run, and report **per-invariant pass rate across the N
runs**, not a single boolean. Read it as:

- **Flaky invariant** (e.g. 3/5) → either dao is non-deterministic on that rule (a real
  bug — e.g. sometimes batches applies, sometimes leaves the clamp half-touched) or the
  assertion is under-specified. Both are findings.
- **Always-passes-regardless** → non-discriminating; the assertion isn't testing akira.
  Tighten or drop it.
- **Content variance with 100% invariant pass** → the *goal* for `wander`: different
  phrasings/orderings of the questions across runs while every invariant holds means akira
  is free within its guardrails. Zero content variance on wander would mean it's overfit to
  the fixture. For the two dao cases, the *actions* (which fix applied, what reverted)
  should be stable — variance there is a red flag, unlike wander.

The `script`-checkable invariants are deterministic and free — put every rule that can be
one there and reserve the judge for voice/specificity/rationale, so the eval doesn't
inherit judge flakiness. skill-creator's per-eval variance tooling ("high-variance evals
(possibly flaky)") reads the per-invariant pass rates directly.

> **Test-gate note for the dao fixtures.** `dao-triage-tiering` and `dao-revert-on-failure`
> ship a `Makefile` with a real `test` target so the gate is genuinely exercised — dao must
> detect the harness and enter the apply loop. To prove the *refusal* path (criterion 4),
> run `/akira dao` against a repo with no test harness instead — no fixture needed; the
> absence of a harness is the condition.
