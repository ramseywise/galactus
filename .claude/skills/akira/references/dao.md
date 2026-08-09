# akira dao — the actuation contract

dao is the only akira mode that mutates. Everything here exists to make that mutation
safe: it never commits, it never touches a repo without a working test harness, and it
only auto-applies fixes whose blast radius is small enough that a passing test suite is
real evidence they're correct.

## 1. Get findings

If invoked bare (`/akira dao`), run `scan` first and use its merged, source-verified
findings. If dao runs as part of the full flow, reuse the scan output already produced.

## 2. Test gate (the hard precondition)

Probe for a working test harness:
- `make -C <repo> -n test 2>/dev/null` → if a `test` target exists, that's the harness.
- Else stack fallback: Python `uv run pytest`, TS `npm test` (only if the script exists
  in `package.json`).

**No harness → dao refuses to mutate _code_.** Surface every code finding read-only, and
state in the report that dao applied no code fixes because `<repo>` has no test harness.
Never install a test runner to manufacture a gate. (This is why a repo with no test
harness by design is never auto-edited: don't let an agent rewrite hand-authored seed
files just because a gate is missing.)

**The gate covers code, not docs.** Doc-sync (step 5) still runs in a harness-less repo. A
test suite is evidence a *code* change didn't regress behavior; it says nothing about
whether a README matches the tree, so withholding doc edits for a missing harness protects
nothing. The review valve for docs is the mandatory human commit (step 6), which is
unchanged. A harness-less repo therefore gets: no code mutation, doc-sync as normal.

**Opt-out repos — dao never mutates, docs included.** A repo may declare itself off-limits
to actuation regardless of harness or file type. dao skips it entirely and reports why.

- **Docs-only repos with no test harness by design** — e.g. one holding hand-authored
  seed files whose exact wording is the artifact. An agent rewriting them destroys the
  thing being kept.
- **Compile-pipeline output directories** — generated docs, not source. If a `CLAUDE.md`
  states a directory is compiled output (source elsewhere, this directory regenerated on
  each compile), a generic doc-sync edit both fights the compiler and is overwritten on
  next compile. The source directory and repo code remain fair game.
- Any repo whose `CLAUDE.md` says akira must not edit it.

**Generated output is never a doc-sync target.** Beyond the named repos: if a doc is built
from another source in-repo (compile pipeline, codegen, `README` assembled from templates),
fix the source or report it — never the artifact.

Check the opt-out list *before* the harness probe: "harness-less" and "opt-out" are
different states, and the doc-sync carve-out above applies only to the former.

## 3. Triage — blast-radius tiers

Classify each finding by how far a wrong fix would propagate:

| Tier | Examples | dao action |
|------|----------|------------|
| **low (nit / mechanical)** | rename a local var, tighten a type, remove dead code with no callers (verify via Grep), fix an off-by-one with an obvious correct bound, dead-import removal | **auto-apply candidate** |
| **high (logic / behavioral)** | anything that changes control flow, an error path, an external contract, a concurrency decision, or that requires a judgment call about intent | **surface-only — never auto-apply** |

When unsure which tier, treat as **high** (surface-only). The test gate catches regressions
but is not a substitute for judgment — a fix can pass tests and still be wrong if coverage
is thin, so only low-radius fixes ride on the tests as evidence.

## 4. Apply loop (test-backed repos only)

For each low-radius finding, one at a time:
1. Apply the single fix (Edit).
2. Run the test harness.
3. **Pass** → keep the fix, move to the next finding.
4. **Fail** → revert *that hunk only* (`git checkout -- <file>` if the file was otherwise
   clean, else `git stash`-based selective revert), record it as "attempted, reverted on
   test failure", move on. Never leave a failing tree from an auto-apply.

Never batch-apply low-radius fixes before testing — one fix per test run, so a failure
is attributable. Never touch a surface-only (high-radius) finding.

## 5. Doc-sync

Runs whether or not code was applied — including in harness-less repos (step 2), and
including when the drift is between committed docs and the committed tree rather than
anything in the diff. When a doc contradicts the tree, update the doc (working tree only):
- **Machine-consumed docs** (`.claude/`, `CLAUDE.md`, `SANYI.md`): edit freely — this is
  the feedback loop the docs.md rule already permits.
- **Human-consumed docs** (README, DESIGN.md): this is the akira exception in
  the doc-writer boundary (akira dao exception). Look for the repo's **doc-style ref** — the repo's `Refs:`
  line pointing at a docs-style ref, or repo-local stakeholder guidelines. Conform to it.
  **No style ref found → still edit, but flag prominently in the run report** that a human
  doc was edited without a style guide, so the human reviewer checks tone before committing.
  There is no global default docs-style ref (decided 2026-07-18).

## 6. Never commit — leave the tree dirty, write the summary

dao stops at a dirty working tree. Ramsey commits, always. The run summary goes at the top
of the report:

```markdown
## akira dao — run summary [date, repo]

Test harness: <how detected> · Tests: <pass/fail baseline>

- Applied (kept, tests green): <file:line — what>
- Attempted, reverted on test failure: <file:line — what>
- Surfaced only (high blast radius, your call): <file:line — what>
- Docs synced: <machine: … · human (flagged if no style ref): …>

Committed: nothing (working tree left dirty for your review).
```

## Refusal cases (dao applies no code fixes, surfaces instead)

- No test harness (step 2) — code surfaced only; **doc-sync still runs**.
- Every finding is high-radius (nothing safe to auto-apply).
- `headless` + a human-doc edit with no style ref — apply, but the flag goes to the
  `### Needs input` section, not chat.
