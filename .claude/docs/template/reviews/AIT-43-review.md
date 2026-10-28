# Review — PR #46 / AIT-43 Wire Python agent-support modules into the LangGraph graph

Scope: **lightweight** (no plan doc for AIT-43; feature branch, 4 commits).
Reviewed at branch tip `de75e98`, against `origin/main` `2fe7b63`.
Covers issues #40, #41, #42, #43, #44.

## 1. Overall Understanding

#43 wires `verification_loop`, `observability.spans`, `context_budget` and
`stall_detector` into the rendered LangGraph agent, and adds mutation-style wiring
tests that fail if any module is un-wired. The work is complete and correct; CI was
red for a reason unrelated to the wiring itself.

## 2. Issue Status (verified against main, not labels)

| Issue | Claimed | Verified | Note |
|---|---|---|---|
| #40 flat-layout answer | in-progress | **merged** (PR #48) | `fee6954`, `d4f7ff3` on main |
| #41 four TS modules unreferenced | in-progress | **resolved by #42** | see below |
| #42 wire TS modules | in-progress | **merged** (PR #47) | `01c4e2a`, `3f14460` on main |
| #43 wire Python modules | in-progress | **code complete**, PR #46 open | CI red — root cause fixed, see §4 |
| #44 CI guard for unimported modules | backlog | **not started** | correctly still open |

`#41`/`#42`: on `origin/main`, `agent.ts` now imports `startChatSpan` (tracing.ts),
`wrapToolsWithSpans` (traceTools.ts), `createStallDetector` (stallDetector.ts) and
`trackUsage`/`shouldCompact` (context-budget.ts). `verificationLoop.ts` is documented
as un-wireable (stream-consuming, incompatible with `streamText`) at
`agent.ts.jinja:22-25` — which is exactly what #42's title promised
("document the two that cannot be wired"). #41's table is fully discharged.

## 3. What Looks Strong

- The wiring tests are **mutation tests**, not coverage theater. Each docstring names
  the edit that makes it fail ("Remove the `with invoke_agent_span(...)` block from
  main.py and this test fails: enter_count stays 0"). This is the right enforcement
  shape for #41's failure mode.
- `.env.example.jinja` gating `VECTORDB_PATH` on `has_corpus_pipeline` matches the
  conditional `Path` import in `main.py.jinja` — the two stayed in sync.
- 39/39 tests pass on a clean render.

## 4. Blocking Findings

### B1 — `make lint-check` fails with ruff `I001` in every `backend`-layout render (FIXED in working tree)

13 of 27 CI legs failed. `main` fails only `layout-persistence`, so all 13 are
branch-introduced. Single root cause, not thirteen:

```
I001 Import block is un-sorted or un-formatted
  --> backend/src/agents/assistant/main.py:1:1
  --> backend/src/agents/assistant/nodes/generate.py:1:1
  --> tests/unit/agents/test_generate.py:275:5
```

**Root cause.** `[tool.ruff.lint.isort] known-first-party` pinned only
`["agents", "middleware"]`. The other packages under `{{ ai_source_root }}` —
`observability`, `context_budget`, `security`, `integrations` — were unpinned, so ruff
classified them by src-based resolution. That resolution succeeds when
`py_project_root == "."` and **fails when it is a real directory** like `backend`,
demoting them to third-party and demanding a different import grouping.

**Why it only appeared now.** #40's `fee6954 "make python layout choice a recorded
answer"` landed on main and changed the default render to the `backend/` layout. CI
tests the PR *merge* commit (main ∪ branch), so it rendered `backend/`; the branch tip
alone still renders `.`. That is why the branch looks clean locally and red in CI, and
why the previous fix attempt (`de75e98 "ruff-format rendered test templates"`) missed —
`ruff format` does not sort imports; `I001` is a lint rule, not a formatter rule.

**Fix applied** — `template/_scaffold/pyproject.toml.jinja:132`: pin every package
under the AI source root, making import order layout-invariant rather than
layout-dependent. This is the same remedy the surrounding comment already prescribed
for `middleware`, extended to the full set. No source or test file needed to change.

Verified by rendering and running the real CI command (`uv sync --only-group dev`,
`UV_NO_SYNC=1 make lint-check`, ruff 0.16.1) against the PR merge ref:

| Render config | Layout | Before | After |
|---|---|---|---|
| defaults-tested (merge ref) | `backend/` | I001 ×3 | pass |
| full-chain | `backend/` | I001 ×4 | pass |
| ml | `backend/` | fail | pass |
| flat-layout | `.` | pass | pass (no regression) |
| defaults (branch tip) | `.` | pass | pass (no regression) |

`pytest -q` on the fixed render: **39 passed**, exit 0.

### B2 — Branch is 7 commits behind main

`git rev-list --left-right --count origin/main...HEAD` → `7  4`. #40 and #42 merged
underneath this branch. The B1 fix is only *provably* correct post-merge, and CI is
already testing the merge ref. Rebase onto `origin/main` before pushing.
`template/_scaffold/pyproject.toml.jinja` is byte-identical between branch and main,
so the B1 edit is rebase-safe (no conflict).

## 5. Important Findings

### I1 — Issue labels are stale caches; three issues misreport state

#40 and #42 are merged but still labeled `in-progress`; #41 is fully discharged by #42
but still open. Anyone reading the board sees five live AIT issues when there is one.
Close #40, #41, #42 (see §8).

## 6. Suggestions and Nits

### N1 — OTel span exporter writes after pytest closes stdout (FIXED)

After the (passing) test summary, the rendered project printed
`ValueError: I/O operation on closed file` from `opentelemetry/sdk/trace/export`.
`ConsoleSpanExporter` binds `sys.stdout` at construction; `BatchSpanProcessor`'s final
flush runs at interpreter shutdown, after pytest has closed the stdout it captured.

Fixed at `observability/spans.py.jinja:76` — skip the console exporter when
`"pytest" in sys.modules`. Production behaviour is unchanged (OTLP path untouched,
console still wired for real runs), and no test depended on it: the one test that
asserts on spans installs its own `InMemorySpanExporter`.

Verified: `pytest -q` → 39 passed, exit 0, zero occurrences of the error string.

### N2 — Two leftover worktrees — DO NOT DELETE, they carry unmerged work

`/private/tmp/ait40` and `/private/tmp/ait42` are clean worktrees, but their branches
are **not** ancestors of main. Each holds one commit that never reached the remote
(the GitHub head branches were auto-deleted on merge, so `git branch -vv`'s "ahead 1"
was measured against a ref that has since been pruned — the work is local-only):

| Branch | Unmerged commit | Verified against main |
|---|---|---|
| `AIT-40-flat-layout-answer` | `5bc7372` ci(test-render): fix layout-persistence leg to use working-tree re-render | **Not in main.** Main still runs `copier update --trust --defaults --vcs-ref HEAD`, which is precisely why `layout-persistence` is main's only red leg — `copier update` resolves `_commit` via `git describe` and the template repo carries no tags, and it refuses to run against the dirty workspace the render step leaves behind. `5bc7372` replaces it with `copier copy --overwrite`. |
| `AIT-42-ts-wire-agent-modules` | `ba70aeb` test(traceTools): replace flaky duration assertion with monotonic ordering | **Not in main.** Main still has `expect(duration).toBeGreaterThanOrEqual(DELAY_MS)` at `traceTools.test.ts.jinja:86` — the flaky assertion the commit removes. |

`5bc7372` in particular is the fix for the only failing leg on `main`. Both should be
landed (cherry-picked onto fresh branches off current main), not deleted.

## 7. Testing Assessment

Adequate and better-shaped than typical. 39 tests, all passing. The new wiring tests
are mutation-anchored, so they will actually detect regression of the thing #43 fixed.
Gap: the wiring tests cover the Python side only — the equivalent TS wiring from #42
has no mutation test, which is part of what #44 is for.

## 8. Definition of Done

| Item | Status | Note |
|---|---|---|
| Code complete | met | wiring + tests present |
| Tests pass | met | 39/39, exit 0 |
| Lint clean | met **after B1 fix** | was the sole CI blocker |
| CI green | **gap** | needs rebase + push + re-run |
| Branch current with main | **gap** | 7 behind (B2) |
| No unrelated changes | met | 1-line config + comment |
| Issue linkage | met | commits carry `(#43)` |
| Labels accurate | **gap** | I1 — #40/#41/#42 stale |

## 9. Reporter Dispatch Summary

| Reporter | Status | Findings |
|---|---|---|
| plan-fidelity | skipped | no plan doc (lightweight scope) |
| akira-scan | skipped | lightweight scope |
| SANYI | skipped | lightweight scope |
| lint (rendered) | ran | 1 blocker → fixed, re-verified |
| tests (rendered) | ran | pass (39) |
| CI leg triage | ran | 13 failures → 1 root cause |
| workspace hygiene | ran | 1 nit (N2) |

## 10. Merge Verdict

**request_changes** — not for code defects, but because the PR is objectively red and
stale. No defect remains in #43's implementation; the wiring and its tests are sound.
Remaining work is mechanical and belongs to Ramsey: rebase onto main, commit the
`pyproject.toml.jinja` fix, push, confirm CI green.

---

## 11. Follow-up — resolution as of 2026-08-01

`origin/main` is now `13241c7`. Re-verified **by content**, not by label or commit
message (the AIT-43 fix landed under a message naming only `spans.py`, while the
commit also carried the `pyproject.toml.jinja` root-cause fix):

| Item | State on `origin/main` | Evidence |
|---|---|---|
| B1 ruff `I001` root cause | **landed** | `known-first-party` lists `context_budget, integrations, observability, security` |
| N1 OTel pytest noise | **landed** | `spans.py.jinja` contains `skipped_under_pytest` |
| #43 wiring | **merged** (PR #46) | — |
| #40 persistence leg | **NOT landed** | main line 291 still `copier update` |
| #42 traceTools deflake | **NOT landed** | main still asserts `toBeGreaterThanOrEqual(DELAY_MS)` |

N2 revised again: the "old branches" were never one-per-fix. Each of #40 and #42 had
**three** branches carrying the same unlanded commit on three different bases — the
original (whose PR merged without it, remote pruned) plus two re-basings. Trees are
byte-identical within each trio; only the base differs. Consolidated to one branch per
fix, rebased onto `13241c7`:

| Keep | Delete (identical tree, stale base) |
|---|---|
| `AIT-40-persistence-rerender` `5561506` | `AIT-40-flat-layout-answer`, `AIT-40-flat-layout-ci-fix` |
| `AIT-42-detflake-tracetools` `64cb5fb` | `AIT-42-ts-wire-agent-modules`, `AIT-42-tracetools-deflake` |
| `AIT-44-unimported-module-guard` `3cdcc10` | — |

`bug/rendered-ts-eslint` is a true ancestor of main and is safe to delete.

### #44 — implemented, with one finding it produced immediately

Mechanism changed during execution. `eslint-plugin-import`'s
`import/no-unused-modules` cannot run under ESLint 9 flat config without an
`.eslintrc` shim, and **with** the shim a planted orphan module still passed clean
(import-js/eslint-plugin-import#3079). That was caught by a negative test, not by
reading docs — shipping it would have meant a guard that always passes, the exact
failure #44 exists to prevent. Replaced with `scripts/check-unimported.mjs`, which
builds the import graph directly. Verified both directions: clean render → exit 0
("all 16 modules have an importer"); planted orphan → exit 1 naming the file.

The guard's first run found **`src/security/guards.ts`** — 229 lines of input guard,
content filter and output scrubber that nothing in a rendered project imported. Same
class as AIT-41 but worse: a scaffold shipping security code no code path runs looks
protected and is not. The Python twin (`security/guards.py`) is equally unreferenced.
`tests/guards.test.ts` is now its importer of record (18 tests).

Two findings that came out of writing those tests, both **deferred, not fixed**:

- **I2 — the security layer is documented but unwired.** `checkInput`/`filterContent`/
  `checkOutput` have a README describing where each belongs in a turn, and nothing
  calls them. Wiring `checkOutput` around a streaming response is a real design
  decision (what does a mid-stream block do to the stream?), not a test fixture.
  Needs its own issue, both languages.
- **N3 — `INJECTION_PATTERNS` misses `"Disregard the above"`.** The pattern requires
  `previous|prior|above` immediately after an optional `all|any`, so an intervening
  `the` slips through. Found by a test fixture that failed; fixture changed to a
  covered phrasing rather than widening a security pattern inside an unrelated issue.

Also folded in: the `ts_agent_framework=none` prune took only `tests/agent.test.ts`,
leaving `agent-wiring`/`traceTools`/`verificationLoop` tests importing a removed
`src/agent` — an unconditional suite failure in a config with no matrix row. Fixed on
the same line, and that config now renders and passes clean (4 modules, 19 tests).

### Verification run (all three branches, rebased onto `13241c7`)

| Branch | Check |
|---|---|
| `AIT-44` | lint 0 errors · check:unimported OK · typecheck OK · 6 suites / 35 tests · build OK · negative test exits 1 |
| `AIT-44` (`ts_agent_framework=none`) | lint OK · check:unimported OK · 2 suites / 19 tests · build OK |
| `AIT-40` | flat render → `src/` present, `py_project_root` absent → re-render → `src/` survived, `backend/` absent |
| `AIT-42` | 4 suites / 11 tests · build OK |

Verdict for #40/#42/#44: **approve** — all three verified by execution, none pushed.
