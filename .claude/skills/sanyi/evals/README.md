# SANYI evals

Two tiers, per the skills norm and akira's `references/behavioral-eval-scaffold.md`.

## 1. Triggering eval (default, cheap) — `trigger-eval.json`

20 realistic queries, ~half should-trigger / half should-not. Covers all three modes
(init/review/audit), fires on natural phrasings ("check for cross-layer violations",
"does this PR downgrade any invariants"), and — critically — does NOT false-trigger on
the near-misses SANYI sits between: `/akira scan` (quality, not contract),
`/workflow-review` (plan fidelity + merge verdict), `make test`,
refactoring/debug/commit requests, and akira wander/dao.

Run via skill-creator's Description Optimization loop:

```bash
python -m scripts.run_loop \
  --eval-set .claude/skills/sanyi/evals/trigger-eval.json \
  --skill-path .claude/skills/sanyi \
  --model <session-model-id> --max-iterations 5 --verbose
```

## 2. Behavioral eval (SANYI is judgment-shaped) — `evals.json` + `fixtures/` + `assertions/`

SANYI *decides* — which violation code applies, whether a bypass is semantic (BY-2) or
direct (BY-1), whether a candidate's evidence is real — so it earns a behavioral eval.
Two cases, each a **distinct judgment path**, not a distinct input:

| Case | Judgment tested |
|------|-----------------|
| `review-catches-by2` | Does review identify BY-2 (invariant made bypassable) rather than BY-1 (directly modified)? Does it name the env var as the bypass vector? |
| `init-valid-contract` | Does init verify candidates against implementation? Does it catch a module with zero call sites? Does it produce all 6 SANYI.md sections? |

`fixtures/<case>/input/` is a **pre-state** (copied to a scratch dir — never the fixture
itself). `assertions/<case>.json` holds the graded invariants — `check: script` where
deterministic (violation code present, file created, section exists), `check: judge` for
the residue (bypass vector named, gap presented with verification result).

### Running + variance analysis (required)

Run **each case N=3-5 times** into separate scratch workspaces, grade every run, and
report **per-invariant pass rate across the N runs**, not a single boolean.

- **Flaky invariant** (e.g. 3/5) → either SANYI is non-deterministic on that rule or
  the assertion is under-specified. Both are findings.
- **Always-passes-regardless** → non-discriminating; tighten or drop the assertion.
- **Content variance with 100% invariant pass** → expected for init's interview phrasing;
  structural output (sections, codes) should be stable.
