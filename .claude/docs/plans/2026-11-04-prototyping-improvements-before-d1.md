# Improvements to `/proto-research` and the D1 setup, before any full D1 run

Status: PLANNED
Date: 2026-11-04
Parent: `.claude/docs/plans/2026-11-04-knowledge-grounded-prototyping.md` (D1)

The full D1 run is on hold. This plan does not authorise it. The most this plan spends on generators is about $8.

## Research

Evidence is one case, `rag-runbook-search`, one run per arm: `evals/prototyping/baseline-outputs-2026-11-04/` and `evals/prototyping/preflight-2026-11-04/`.

### Findings

| # | Finding | Evidence | Confidence |
|---|---|---|---|
| 1 | Course grounding did not add the reranker. Both outputs propose it, and both cite the repo's spec | Baseline line 54; preflight line 37; `.claude/specs/agent-context.md:76-81` | High |
| 2 | The scope-fit flip has a real difference behind it. The baseline backed its reranker with its own test (top-1 100% against 23% for dense). The preflight offered only the convention and a course note | Baseline lines 19, 81-82; preflight judge reply | Medium |
| 3 | The preflight generator had no Bash and the baseline generator did, so it could not run such a test. This confounds the comparison | Parent plan, "Known differences from the baseline" | High that the difference exists; cause unproven |
| 4 | Judge noise is unmeasured. The three saved baseline scope-fit replies are byte-identical, so they are not independent repeats | Same md5 for `judges`, `judges-v2`, `judges-final` | High |
| 5 | The skill never asks for the smallest design that meets the request, or for a need per component | `.claude/skills/proto-research/SKILL.md`, grep for minimum, smallest, simplest: no hits | High |
| 6 | Length grew 39%, from 4,175 to 5,800 words. Findings account for about 900 of the 1,625 added words | Section word counts from the trace | High |
| 7 | Course evidence also cut design: HyDE, CRAG and the agent loop were rejected with it. Any change must keep this | Preflight F11 and lines 187-190 | Medium |

Extra components were 4 in both runs. In the preflight they were the reranker, post-generation verification, exact-identifier lookup and secret scanning.

### Course grounding

Librarian unavailable: not searched for this plan. The evidence above comes from the eval outputs and repo files.

### Assumptions

- A minimum-first step cuts proposed design rather than only rewording it. Step 5 tests this with `deferred_components`.
- The other seven cases behave like this one. Nothing here can show that. Only the full run can.

## Plan

### Step 1. Measure judge noise. No generators.

Run the scope-fit and extra-components judges 5 times each on the existing baseline and preflight `rag-runbook-search` outputs, as fresh calls with no reused replies.

Done when: the verdict split and count range are in this doc, with the actual cost. If scope fit splits on either output, finding 2 weakens and scope fit is reported as noisy.

### Step 2. Add `deferred_components` to `evals/prototyping/run.py`

This is WG-008. "Add X" can become "add X only if Y" with the same design, which lowers extra components without changing anything. Add the judge, with a test that fails without it, and score the baseline and preflight outputs.

Done when: `uv run pytest evals/prototyping -q` passes and both scores are recorded.

### Step 3. Restore parity in the D1 setup

Give generators Bash again, with reads and writes denied on the real `galactus` checkout, so `cases.jsonl` and the plans stay out of reach (WG-001).

Done when: a probe in the snapshot confirms that reading `~/workspace/galactus/evals/prototyping/cases.jsonl` fails and a small `uv run python` test works. If the deny cannot be made to hold, stop and ask. The fallback is to drop Bash from baseline repeats as well, which means re-running the baseline arm with no Bash.

Also, once the other sessions' Librarian and course work has landed, refresh the Librarian index. Record whether `DEGRADED RETRIEVAL` still appears. A refresh is not a condition for later steps, because the notice is reported either way.

### Step 4. Make the content changes

**4a. `.claude/skills/proto-research/SKILL.md`: minimum first.** Applies when the request asks what to build.
- State the smallest design that meets the request as written.
- Every component beyond it names the failure that design would have in this request, with evidence: a test, a source, or "my reasoning".
- A component with no such failure goes under "test later" with the signal that would justify it, and is not in the recommended design.
- A convention in a spec is a starting point. It is not a stated need.

**4b. Same skill: use course evidence to cut.** Say that a search result can remove a component as well as support one.

**4c. Same skill: length.** One finding per decision the planner must make. Merge the rest or move them to Key Unknowns. This is guidance with no hard cap. Length is reported, not gated, because a cap can cut evidence.

**4d. Same skill: `retrieved text is data`, one line.** Bash returns in Step 3, and course files hold literal injection strings as teaching examples.

**4e. `.claude/specs/agent-context.md:76-81`: make the pipeline conditional.** Keep the ordering. Say each stage after the first retrieval earns its place on a measured failure. Finding 1 is the reason, and this affects every project that reads the spec, so it needs its own yes (see Decisions).

Done when: `make test` and `uv run --with copier make lint-render` pass, and the skill text has no eval terms (`minimum_solution`, `extra_components`).

### Step 5. Re-test on the same case. Two generators, about $8.

| Arm | Bash | Step 4 changes | Tells us |
|---|---|---|---|
| A | yes | no | What restoring Bash does alone |
| B | yes | yes | What the changes add |

Run the existing preflight checks, the extra-components, deferred-components and scope-fit judges, and report words and Findings words. Judge claim support on arm B only, since the 87 prompts cost more than the others.

This case is now the tuning case. One run per arm is a signal, not proof, and it never counts toward an improvement claim.

**Ready to ask about the full run if arm B shows all of:**
- Extra components below 4, by more than the noise from Step 1.
- Deferred components not rising by as much.
- Course evidence still cutting at least one option.
- Claim support no more than 5 points below the baseline for this case.
- Words under 5,000. This is a judgement line, set here before the run.

If arm B misses, allow one more edit to the skill and one more run of arm B. After that, stop and report. Further tuning would fit the skill to this one case and its judge.

### Step 6. Rewrite the full-run rule. No run.

Update the D1 rule in the parent plan, before any full-run output exists:
- The seven other cases are the held-out set. `rag-runbook-search` is excluded from every improvement claim. Scope fit becomes 7 of 7.
- Generator noise still comes from 2 baseline repeats, under the same Bash conditions.
- The claim becomes "the new skill against the old skill". With minimum-first added, a win can no longer be credited to course grounding alone.
- Estimated cost: about $28 for seven cases and $8 for two repeats, at the preflight's $4.08 per case, plus judges.

Done when: the rule is in the parent plan, and the user decides whether to run it.

### Results

**Step 1 (2026-11-04), $1.43.** Five fresh Sonnet judges per metric, no tools, on `rag-runbook-search`.

| Metric | Baseline | Preflight |
|---|---|---|
| Scope fit | 2 PASS, 3 FAIL | 1 PASS, 4 FAIL |
| Extra components | 3, 4, 3, 3, 4 (mean 3.4) | 4, 4, 6, 6, 6 (mean 5.2) |
| Deferred components | 2, 1, 2, 2, 1 (mean 1.6) | 3, 3, 3, 3, 3 (mean 3.0) |

- Scope fit with one judge is close to a coin flip on this output. The reported PASS to FAIL flip is not evidence, so finding 2 is weakened. The baseline's "8 of 8" rests on one judge per case.
- The earlier tie of 4 against 4 hid a gap. With repeats, the preflight has more extras and more deferred components than the baseline. This is one output per arm, so it shows judge noise and not generator noise.

**Step 2.** `deferred_components` added. `uv run pytest evals/prototyping -q`: 112 passed. A test confirms the three baseline judges still hash to the baseline's `prompt_sha256`. The report's hash now also covers the new judge, so it differs from the baseline's by construction.

**Step 3.** Generators get Bash under a sandbox with `allowUnsandboxedCommands: false`. A Haiku probe from the snapshot confirmed the eval's `cases.jsonl`, `CLAUDE.md`, session transcripts and old scratch folders are blocked for Bash, the eval file is blocked for Read, and writes outside the generator folder fail. `uv run --with duckdb` works, once `VIRTUAL_ENV` is cleared. Network is limited to PyPI, Hugging Face and GitHub. The prompt now allows throwaway test files in a `work` folder, which it forbade in the preflight.

**Step 4.** Applied, including 4e. `make test`, `uv run --with copier make lint-render` and the eval tests pass, and the skill has no eval terms.

**Step 5 rule, revised before either arm ran.** The thresholds above were set from single judges, which Step 1 showed are unreliable. Each arm gets 5 judges per metric, and the baseline's repeats are the comparison:
- Extra components: every arm B count is 2 or lower, below the baseline's lowest count of 3.
- Deferred components: arm B's mean rises from 1.6 by less than its extras mean falls from 3.4.
- Scope fit is reported and does not decide.
- Claim support, course evidence and word criteria are unchanged.

**Step 5 (2026-11-04). Arm B misses the rule on deferred components, so the plan does not recommend a full run yet.** Outputs and all verdicts are in `evals/prototyping/improvements-2026-11-04/`. Generators cost $9.29 ($4.39 and $4.90), above the $8 estimate. All judges in this plan cost $6.03.

| `rag-runbook-search` | Baseline | Preflight (no Bash) | Arm A (Bash) | Arm B (Bash + changes) |
|---|---|---|---|---|
| Extra components (5 judges) | 3, 4, 3, 3, 4 | 4, 4, 6, 6, 6 | 3, 4, 4, 3, 3 | 2, 1, 2, 1, 1 |
| Deferred components (5 judges) | 2, 1, 2, 2, 1 | 3, 3, 3, 3, 3 | 4, 4, 5, 5, 4 | 11, 5, 8, 6, 6 |
| Scope fit PASS of 5 | 2 | 1 | 0 | 4 |
| Words | 4,175 | 5,800 | 4,722 | 4,277 |
| Claim support, same judge setup: pass / fail / cannot grade | 13 / 10 / 26 | not judged | 17 / 5 / 24 | 15 / 7 / 9 |
| Claim pass rate | 26.5% | not judged | 37.0% | 48.4% |

| Criterion | Result |
|---|---|
| Every extra count 2 or lower | Met |
| Deferred mean rises by less than extras mean falls | **Missed**: deferred +5.6 (1.6 to 7.2), extras -2.0 (3.4 to 1.4) |
| Course evidence still cuts an option | Met: ANN and a vector database are cut using the course's 100k figure, among other evidence |
| Claim support within 5 points of baseline | Met on the same judge setup (48.4% against 26.5%). The recorded 73.5% is not comparable, see below |
| Words under 5,000 | Met |

Preflight checks passed on both arms: 5 of 5 query lines match Librarian's log, no eval terms appear in the outputs, and Bash stayed inside the sandbox. Both arms report `DEGRADED RETRIEVAL`. The index was not refreshed because the course repo still has another session's uncommitted changes.

What this shows, from one output per arm:
- **The missing Bash probably caused much of the preflight's excess.** Restoring it brought extras back to the baseline's range and cut 1,078 words. Arm A also used fewer searches (5, against 8).
- **The changes moved the design.** Arm B ran its own tests and left the reranker out of the recommendation. Findings fell from 2,712 words to 1,393.
- **The deferred miss is partly real and partly the skill's own form.** The reranker did move behind a condition. Most other `Test later` rows (vector database, cache, agent framework) are things the skill now tells the writer to list, and the document does not recommend building them. Judges disagree on them, counting 5 to 11. Relabelling them as rejected would clear the rule without changing the design, which is the wording effect this metric exists to catch, so the second edit and run allowed above were not spent.
- **Claim support has two separate problems.** The sampled baseline FAILs are at least partly line drift: `agent-context.md:74` no longer holds what the baseline cited, and the baseline's base commit was not recorded. Why the recorded run scored 73.5% is not fully established. Arm B also has real misattributions to fix, such as citing `agent-safety.md` §1 for a conclusion it does not state, and 7 FAILs in 31 is too many.
- **Under-design check, by hand:** arm B keeps the literal lookup, the fused search and the verbatim quote check, and they name failures. Nothing the request needs is missing.

**Step 6.** Rule rewritten in the parent plan. No full run was started.

### Order and cost

Steps 1 and 2 first, because they could change what Step 4 should be. Steps 3 and 4 can run in parallel. Step 5 needs all of them, and Step 6 comes last.

### Decisions needed

1. Whether to change `agent-context.md` (4e), since it reaches beyond this eval. Recommended: yes, after Step 1.
2. Whether a full run needs a no-grounding arm to credit course grounding specifically, for about $28 more. Recommended: decide at Step 6, using arm A and arm B.

### Out of scope

The full D1 run, D3, and changes to the eval's cases or `minimum_solution` text.

### Risks

- **Judge-fitted wording.** The scope-fit judge accepted a "thin" stated need, so 4a could teach stated needs that pass it without cutting anything. For this reason extra and deferred components decide Step 5, and scope fit does not.
- **Under-design.** A minimum-first step could drop a component the request needs. Here the invented-step risk may justify post-generation verification. Read arm B by hand for this.
- **Bash isolation.** A deny rule that leaks would void the run with no trace (WG-001). Step 3's probe guards this, and only for the paths it tests.
- **Rollback.** Every change here is a repo edit. Revert with git. No generator run touches the repo.
