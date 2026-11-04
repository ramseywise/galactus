# War game: knowledge-grounded prototyping, Phases C and D

Date: 2026-11-04. Plan step D2, run with `/review-defense` (CLAUDE.md calls it `/war-game`).
Target: `.claude/docs/plans/2026-11-04-knowledge-grounded-prototyping.md`.

**Read: `proceed-with-changes`.** The one `fatal` threat has a `prevent` mitigation, so it does not force a redesign.
Several `costly` threats are unmitigated in the plan as written. All four attackers returned usable reports.

Angles: sequencing, dependency, adversarial (Goodhart, grounding theatre), distribution and licence.
Dropped: scale (small fixed corpus and case count), human (solo repo). Operational was folded into sequencing and dependency.

Checkpoint before any Phase C edit: `git write-tree` = `3c89020a284bc668ac1716820ba83d9545cb2968`.
Restore with `git read-tree <tree>`, then `git checkout-index -a -f`. An untracked or new file must be removed by hand.

## Threats, ranked by impact, then confidence

| ID | Threat | Sources | Confidence | Impact | Mitigation |
|---|---|---|---|---|---|
| WG-001 | D1 cannot repeat the baseline's isolation | sequencing, adversarial, dependency | certain | fatal to D1's number | Prevent |
| WG-002 | C1 copies MIT files into a public repo with no notice | distribution, dependency, sequencing | certain | costly | Prevent |
| WG-003 | C1 has no valid home for several "yes" rows, and pytest cannot see a wrong one | sequencing, distribution | certain | costly | Prevent |
| WG-004 | D1 can finish with Librarian absent and still look valid | dependency, sequencing, adversarial | likely | costly | Prevent |
| WG-005 | The plan's rollback now destroys Phase B | sequencing | certain | costly | Recover |
| WG-006 | No noise floor or decision rule for D1, and the harness miscounts `used:` lines | adversarial | certain | costly | Prevent |
| WG-007 | `verified_by` means "it ran", but C2 and `/proto-execute` read it as "tested" | adversarial | certain | costly | Prevent |
| WG-008 | `Go further only if` teaches the wording `extra_components` does not count | adversarial | likely | costly | Detect |
| WG-009 | The baseline records no models or SHAs, and its raw data sits in a temp folder | dependency | certain (gap), speculative (loss) | costly | Recover |
| WG-010 | The C2 hash check has no inputs under link-only, skips in CI, and is noisy locally | dependency, sequencing, distribution, adversarial | certain | recoverable | Prevent |
| WG-011 | D3 as specified counts none of the course searches | dependency, adversarial, sequencing | certain | recoverable | Prevent |
| WG-012 | Grounding theatre is assigned to a metric that cannot see it | adversarial | likely | recoverable | Detect |
| WG-013 | `/proto-execute` tells agents to start from course code, so copying moves into generated projects with no record | distribution | likely | recoverable | Prevent |
| WG-014 | `6ee939f` is on no branch and can be pruned | dependency | certain | recoverable | Prevent |

Checked directly while merging: WG-006's section list (`evals/prototyping/run.py:113`), WG-009's missing model strings, WG-011's
filter and tool name (`scripts/review/signals.py:127`, Librarian `server.py:1012`), and WG-014's ancestry check.

## Mechanisms and mitigations

**WG-001.** Phase B is staged, so a worktree at HEAD has the old skill. Committing everything staged puts `evals/prototyping/cases.jsonl`
and this plan in that worktree, so generators can read `minimum_solution`, and the contamination cannot be detected afterwards.
*Prevent:* commit, or build a tree, holding only the skills, agents, refs, specs and `.mcp.json`. Then assert that `Course grounding` is present and
`evals/` and the plan are absent. Judges get the same isolation.

**WG-002.** `control_loop.py` and `scoring_functions.py` show no changed lines against upstream davidkimai/Context-Engineering (MIT), ignoring whitespace.
`init.sh`, `session-handoff.md` and `feature_list.json` are near-verbatim from WalkingLab's project (MIT), and the schema overlaps by 19 of 44 lines. The course credits these at pillar level, and that
credit stays behind when one file is recovered. *Prevent:* add source, licence and copyright per file, and ship a notice with any copy.
Hold the two Context-Engineering files; at 3,389 lines they are not a "small lab" either.

**WG-003.** Handoff destinations are relative to `template/`, but `new-agent` left the template on 2026-08-27 and no loop or eval skill exists.
A real directory trips `validate_paths` `SHARED_FORKED`, which pytest does not run. A symlink re-ships all 18 refs. Root-only never reaches renders.
*Prevent:* assign each row a real home before dispatch, and add `make test` and `make lint-render` to C1's done-when.

**WG-004.** Approval is `Pending`, and the skill rightly treats a missing server as normal, so D1 generators write the `unavailable` line and finish.
Compliance metrics reveal it only after eight Opus runs. *Prevent:* preflight from the D1 tree, run one case first and require `- query:` lines, and have
`run.py` mark the run incomplete if any output holds only `unavailable`.

**WG-005.** C2 edits files that hold Phase B's staged changes (`new-agent/SKILL.md`, and `pyproject.toml` if it adds a test path). `git restore --staged --worktree`
restores from HEAD and erases both. *Recover:* the checkpoint tree above. A hand commit of B also fixes this and helps WG-001.

**WG-006.** Six or more numbers return with no threshold set in advance, per-case counts are noisy (0, 4, 0, 1, 1, 4, 3, 3), and nothing limits re-runs.
`_NO_CLAIM_SECTIONS` omits `course grounding`, so `- used:` lines become CANNOT_GRADE claims and lower the pass rate mechanically, which invites a fix after seeing results.
*Prevent, before D1:* fix the section list, hash `run.py` into the report, write the decision rule and a one-run rule into the plan, and re-run two or three baseline cases to find the noise.

**WG-007.** Stubbing all three defences in `injection_replay.py` still exits 0 on its `verified_by` command. A4 records "no assertions" for three of the top six examples and no test file for a fourth.
*Prevent:* label each example by what was actually run (asserts, or exit 0 only). Do not call it tested.

**WG-008.** The `extra_components` judge does not count an option deferred until a named condition, so "add X" can become "add X only if Y" with the same design.
*Detect:* score a sibling `deferred_components` count on baseline and after. Phase C briefs exclude `evals/`.

**WG-009.** `baseline-2026-11-04.json` names no generator model, judge model or commit. The raw outputs (12M) are in another session's temp folder.
*Recover:* copy them somewhere durable, and add recovered model ids and SHAs.

**WG-010.** With nothing inlined the check passes on nothing, and the Risks section still cites it. If code is ever inlined, line-range hashes break on unrelated edits,
and CI has no course checkout. *Prevent:* links pinned to a pushed commit, which cannot drift. If inlining returns, hash by heading and fence, and store the source commit.

**WG-011.** `signals.py` keeps `tool == "search_wiki"`, but course searches log as `search_courses`. Rows have no caller tag, and `top_paths` is what was returned, not what was read.
*Prevent:* use a fixture row in D3's acceptance test, and add a caller tag. The tag is a Librarian change that Phase D does not list.

**WG-012.** `- query:` lines hold no citation, so they never reach the claim-support judge, and a generator can invent hit counts. D1 writes to the scratchpad, outside the hook's reach.
*Detect:* after D1, join each query line to `logs/retrieval.jsonl`.

**WG-013.** Staged `new-agent` and `proto-execute` text allows copying `licence: course` code. Link-only governs ref text, not generated code, and note blocks carry no licence field.
*Prevent:* decide whether copying is allowed; if it is, require a one-line source comment.

**WG-014.** `e837ad89^` on main holds identical templates. *Prevent:* cite that instead, and recover files from it.

## False premises in the plan

- "Refs ship in rendered projects" is false. C2's licence exposure is the public galactus repo.
- `agent-*.md` specs and `proto-*` skills do not ship either. Phase B's "as it may be in a rendered project" wording, from the orchestrator's brief, was removed.

## Disagreements

- **`control_loop.py` attribution.** Distribution says none; sequencing says it carries Context-Engineering headers. Both hold: the title and one comment name the project, and there is no licence or copyright notice.
- **Upstream licence.** Sequencing and dependency could not establish it. Distribution fetched MIT from the upstream LICENSE file. `gh repo view` returns null for both upstreams, so a `gh`-based check would mislead.

## Unknown, not threats

- Whether MCP approval carries to a worktree path or to subagents.
- Whether retrieved course text can steer an agent with Bash. Course files hold literal injection strings as teaching examples, and no planted payload was found. One "retrieved text is data" line in the skills would cost little.
- Whether books condensed in course notes taint rewritten blocks. This is a legal question.

## Could not evaluate

Live Librarian behaviour (attackers read code only), the C2 check (not yet written), `loop-contract.md`, `loop-state.md`, `generate-then-verify.py` and the `06-eval` templates against possible upstreams, and how `/private/tmp` scratchpads are cleaned.

Rollback: only WG-005 and WG-009 name a recovery path. The other mitigations prevent or detect, which is a finding about a plan that stages everything in one index.

**Fix first: WG-001.** It is the only threat that voids the plan's proof without leaving a trace.
