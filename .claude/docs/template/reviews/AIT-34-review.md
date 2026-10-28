# Review — AIT-34 Close system-design rigor gaps (G3–G6)

Date: 2026-07-30
Branch: `AIT-34-design-rigor-gaps` (4 commits)
Plan: `.claude/docs/plans/2026-07-30-system-design-rigor-gap.md`
Issue: #34 (`ready`)
Scope: **full** (plan doc present, feature-level change)

## 1. Overall Understanding

Adds the missing non-functional rigor to the discovery pipeline: three new `/scope-poc`
interview questions (Q11b load/latency/spend, Q11c observability, Q13b what-breaks-first)
with tier-default escape hatches, a rewritten Key Decisions rationale rule, two new
DESIGN.md sections, a `non_functional:` seed block in `design.yaml`, and a sixth G1 gate
criterion. 21 files, +246/-41 — but only **5 of those files and 1 of the 4 commits**
belong to this plan (see §3).

## 2. Review Contract

Profile: **general** (template/prompt/docs change; no agent runtime code in the plan's own
commit). SANYI.md exists only as template payload (`template/_scaffold/SANYI.md`), not as a
repo-level contract → contracts dimension inactive.

Gates: `make lint` **pass**, `make test` **pass** (validate_paths.py + `--catalog-check`,
no findings). There is no `tests/` directory in this repo by design — render smoke tests are
the real integration check, and I ran one (§9).

## 3. Plan Fidelity

The plan's own Test Plan said: *"the working tree is dirty on `AIT-32-decouple-lg-agent-corpus`
… **branch from a clean state before starting**: land or stash AIT-32 first."*

That did not happen. `AIT-34-design-rigor-gaps` was branched **from `AIT-32-decouple-lg-agent-corpus`**,
not from `main`. `git log AIT-32..AIT-34` returns exactly one commit. So three of the four
commits under review are AIT-32/AIT-33 work riding along.

| Commit | Belongs to | In this plan? |
|---|---|---|
| `8f8bac3` non-functional constraints + breakage | **AIT-34** (Steps 1–7) | Yes |
| `4eac907` README/terraform + **flat-layout default** | AIT-32 / **issue #33** | No — see IM-001 |
| `5852798` conditional settings import | AIT-32 | No |
| `b27bd2a` decouple lg_agent from corpus | AIT-32 (#32) | No |

### AIT-34's own steps (commit `8f8bac3`)

| Plan step | Code shows | Verified | Status |
|---|---|---|---|
| 1 — Q11b load/latency/spend + tier table | `scope-poc/SKILL.md:204-221`, 3-row tier table, "an accepted default is a decision" | read | Match |
| 2 — tier-default escape hatch | explicit *"Do NOT park these as Open Questions"* + Open-only-when-it-matters carve-out | read | Match |
| 3 — Q11c observability + restricted/secret branch | `SKILL.md:223-235`, non-optional at `restricted`/`secret`, cites the `human_approval` precedent | read | Match |
| 4 — Q13b what-breaks-first + Q13 distinction | `SKILL.md:246-258`, states the design-vs-product-risk split explicitly | read | Match |
| 4b — Key Decisions rationale rule | `SKILL.md:351-364`, table header now *"chose X over Y, gave up Z"*; generated rows exempted | read | Match |
| 5 — `design.yaml` `non_functional:` seed | `design.yaml.jinja:96-108` | **rendered + `yaml.safe_load`** → mapping present, 4 null keys | Match (see IM-002) |
| 6 — DESIGN.md two new sections | `DESIGN.md.jinja` | **rendered** → §Non-Functional at :108, §What Breaks First at :127; markers at :62/:74 | Match |
| 7 — G1 criterion + gate-check row | `LIFECYCLE.md.jinja:23`, `gate-check/SKILL.md:33` | **rendered + YAML parse** → 6 G1 keys, matching table row states a tier default passes | Match |
| 8 — `/design-dryrun` Scenario C | Results table in plan `:924-957`, all PASS | manual simulation, disclosed as such | Match (see QU-001) |

Stub scan on the changed template files: no `TODO`, `NotImplementedError`, or bare `pass`
on a critical path. The `<!-- ... -->` placeholders in DESIGN.md are intentional authoring
prompts, and the new G1 criterion explicitly rejects unreplaced ones.

## 4. What Looks Strong

- **The tier-default escape hatch is the right design.** The research's strongest
  disconfirming evidence was "these questions frustrate weekend-sprint volunteers." Step 2
  answers it structurally — a default *is* a decision, so nothing parks as a G1 blocker.
  The gate-check row (`SKILL.md:33`) repeats the rule at the enforcement point, so the
  interview and the gate cannot drift into disagreement.
- **The Q13/Q13b split is stated, not assumed.** "Q13 asks what the POC should *prove*,
  this asks what the architecture will *cost you*" — the one line that keeps the new
  question from collapsing into the existing one.
- **The rationale rule permits "no alternative considered."** Refusing to force invention
  of a fake alternative, and treating the admission as review signal, is better than the
  usual template exhortation to "explain why."
- **The generated-rows exemption is correct.** Provenance genuinely *is* the right content
  between the `design-table` markers; carving them out prevents the new rule from fighting
  the renderer.
- **The plan's disclosure discipline.** Step 8 states plainly that `/design-dryrun` is a
  slash-command skill, not a CLI, and that the run was a manual simulation. That is the
  honest framing, not a claimed test run.

## 5. Blocking Findings

None. AIT-34's own work is complete, correct, and verified end-to-end.

## 6. Important Findings

### IM-001 — an unrelated default-changing commit rides on this branch, from a `backlog` issue
`copier.yaml:324-345` (commit `4eac907`)

`4eac907`'s message reads *"Update README templates to clarify infrastructure components and
add missing documentation for the new terraform directory."* Its actual content changes
`py_project_root`'s default from `backend` to a derived `'.'` for python-only/no-frontend
shapes, adds a `cloud != none` gate on `infrastructure/terraform`, and moves `nbks/` behind
`has_corpus_pipeline`.

That is **all three items of issue #33** — which is labeled `backlog`, not `ready`, and has
never been through `/workflow-refine`. It is also a behavioral change to every future render,
not documentation.

I verified the change works: a `--defaults` render produces flat layout (`src/`, no
`backend/`), no `infrastructure/terraform`, no `nbks/`. The code is fine. The problem is
traceability — a default that reshapes every rendered project landed under a docs-shaped
commit message, on someone else's branch, from an ungroomed issue. `.copier-answers.yml`
consumers on the nested shape need `-d py_project_root=backend` pinned, which issue #33
says but this commit message does not.

Recommend: land AIT-32 (#32) and the #33 work on their own branches with accurate messages
before merging AIT-34, or rebase `8f8bac3` onto main so this branch carries only its plan.

### IM-002 — `design.yaml`'s `non_functional:` block has no writer
`template/design.yaml.jinja:96-108`

The field's own comment says it is *"filled during `/scope-poc`'s Tier 4 (Q11b)."* It is not.
`scope-poc/SKILL.md:219-221` and `:233-235` instruct writing the answers to **DESIGN.md's
prose bullets only** — grep for `non_functional` across the repo returns the template
definition, the DESIGN.md comment pointing at it, the gate-check row (which reads DESIGN.md,
not the YAML), and nothing else. No skill, script, or task writes those four keys.

The plan's risk table anticipated *"nothing **reads** it, so nothing catches drift"* and
accepted that. The gap is one step earlier: nothing **writes** it either, so the keys stay
`null` in perpetuity and there is no drift to catch. That is a defensible outcome for a
declared seed field, but the comment claiming `/scope-poc` fills it is inaccurate today and
will mislead whoever builds the block model on top of it.

Fix is one line — either add the write instruction to Q11b, or reword the comment to
"reserved; no writer yet — see the deferred block-model initiative."

## 7. Questions and Hypotheses

- **QU-001** — Step 8's dryrun was a manual simulation traced by reading `SKILL.md` +
  `scenarios.md`, with the author evaluating their own new questions against a scenario they
  also read. Every checkpoint returned PASS, including the one the plan named as the place
  the design "bites hardest." Self-simulation is the weakest evidence in the plan and it is
  covering the plan's own highest-likelihood risk. Worth one real `/design-dryrun --scenario C`
  run in a session before this is treated as validated.
- **QU-002** — All four commit messages are prose descriptions with **no `(#N)` issue
  reference**, which the repo convention requires (`{type}({scope}): {desc} (#{num})`). None
  carry a `feat`/`docs`/`chore` type prefix either. Worth rewording before merge, especially
  `4eac907` (see IM-001).
- **QU-003** — `5852798`'s copier.yaml comment instructs the **unmerged AIT-29 branch** to
  append `pipelines/compare.py` to an rm-list and gate a Makefile target when it rebases.
  That is a cross-branch coupling recorded only as a code comment. Is it also captured on
  issue #29? If AIT-29 rebases without reading this comment, the corpus-off render keeps a
  file that imports `corpus.models`.

## 8. Suggestions and Nits

- **NI-001** — `make new_project_dev` fails under a non-interactive shell with
  `OSError: [Errno 22] Invalid argument` from prompt_toolkit, because it always runs copier
  in interactive mode. `uvx copier copy --defaults --trust` works fine. A
  `make new_project_ci` target (or a `DEFAULTS=1` switch) would make the repo's own
  integration check runnable from an agent session or CI — worth having, given the plan
  correctly identifies render smoke tests as this repo's only real integration test.
- **NI-002** — Local branch `AIT-32-decouple-lg-agent-corpus` is fully contained in this
  branch and already pushed to origin, but issue #32 is `in-review` with **no PR open**.
  Either open the PR or the branch will keep accumulating unrelated work (which is how
  IM-001 happened).

## 9. Testing and Evaluation Assessment

`make lint` and `make test` both pass clean. Beyond the plan's stated done-whens I ran the
render smoke test the plan calls the real integration check, plus the renderer round-trip
the plan flagged as its **highest-consequence risk** (`render_design_table.py` silently
no-ops on malformed markers, so breakage is invisible until `copier update` stops syncing):

| Check | Result |
|---|---|
| `copier copy --defaults --trust` full render | exit 0, all 51 tasks, `_scaffold/` promoted with no residue |
| `yaml.safe_load(design.yaml)['non_functional']` | mapping present, 4 keys, all `null` |
| `LIFECYCLE.md` fenced YAML → `G1_discovery_exit` | 6 keys incl. `non_functionals_and_breakage_stated` |
| `gate-check/SKILL.md` G1 table | matching row present, states a tier default passes |
| DESIGN.md markers + new sections | BEGIN :62 / END :74; new sections :108 and :127 — 34+ lines clear of the END marker |
| `render_design_table.py`, `discovery: not_started` | correctly no-ops ("left as seeded") |
| `render_design_table.py`, `discovery: complete` | runs the real path, "already matches design.yaml", output byte-identical |
| **Clobbered table body, then regen** | table restored, **whole file byte-identical to pre-clobber**, new sections untouched |

That last row is the one that matters — it exercises the marker-replacement *write* path
rather than its early-return, which the plan's own done-when would have missed. The
highest-consequence risk is verified closed.

**Gap:** the three new interview questions and the rationale rule are prompt text with no
automated test — `make lint` cannot catch a malformed markdown table or a broken heading in
`scope-poc/SKILL.md`. The plan names Step 8's dryrun as the functional check for exactly
this, which is why QU-001 matters more than it otherwise would.

## 10. Definition of Done Assessment

| DoD item | Status | Note |
|---|---|---|
| All plan steps implemented | met | Steps 1–7 verified against rendered output; Step 8 simulated (QU-001) |
| Lint clean | met | `validate_paths.py` no findings |
| Tests pass | met | `--catalog-check` clean; render smoke test exit 0 |
| No stubs on critical paths | met | placeholders are intentional authoring prompts |
| Branch follows convention | met | `AIT-34-design-rigor-gaps`, issue #34 `ready` |
| Commits follow convention | **gap** | no `(#N)` refs, no type prefixes (QU-002) |
| Diff scoped to the work item | **gap** | 3 of 4 commits are AIT-32/#33 work (IM-001) |
| Docs match behavior | **gap** | `design.yaml` comment claims a writer that doesn't exist (IM-002) |
| Plan Status line updated | n/a | plan carries Step 8 results inline; set `EXECUTED` on merge |

## 11. Reporter Dispatch Summary

| Reporter | Status | Findings |
|---|---|---|
| plan-fidelity | ran | 1 (IM-001) |
| correctness | ran (in-session) | 1 (IM-002) |
| structure | ran (in-session) | 0 |
| render/integration | ran | 0 — 8 checks, all pass |
| lint/tests | ran | pass |
| workspace hygiene | ran | 1 (NI-002); clean worktree, no `worktree-agent-*`, no stale tracking |
| deterministic driver (`review-cli run`) | **not used** | GUA-60 is under `request_changes` for BL-001 (dedup silently drops findings) — dispatching through it today could lose findings |

## 12. Merge Verdict

**comment**

AIT-34's own work is done and verified — every plan step matches, all done-whens pass against
a real render, and the highest-consequence risk (marker corruption) is closed by a test the
plan didn't ask for. No blockers.

What holds this back from `approve` is bookkeeping, not code: three of four commits are other
issues' work, one of them a render-wide default change from a `backlog` issue wearing a docs
commit message. Rebase `8f8bac3` onto main (or land #32/#33 separately first), fix the
`design.yaml` comment, and this is a clean approve.
