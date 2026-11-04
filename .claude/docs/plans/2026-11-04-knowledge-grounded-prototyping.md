# Knowledge-grounded prototyping — wire Galactus to the course through Librarian

Status: PLANNED
Date: 2026-11-04
Issue: — (none yet)
Epistemic: CONFLICTED
Epistemic-by: fog-advisor (via /proto-refine, Phase B gate)
Epistemic-at: 2026-11-04
Epistemic-findings: 3

Decided 2026-11-04 (Ramsey, provisional): the three repos stay separate. learn-ai-engineering
is the source of truth, Librarian is the index, Galactus is the workflow. Galactus gains
retrieval, plus tested minimal examples in its capability refs.

Decided 2026-11-04 (Ramsey): capability refs grow rather than shrink. They gain small coded examples
from the course so Claude does not build more than a task needs. This replaces the earlier trim proposal.

Decided 2026-11-04 (Ramsey): start Phase B, then C and D, without re-running `/proto-refine`. The gate was
waived, not passed, so `Status:` stays `PLANNED` and `Epistemic: CONFLICTED` stands: its three findings were
never recorded, so nothing has shown they are resolved.

## Research

Direct inspection, 2026-11-04. Sources: this repo's `CLAUDE.md`, `.claude/docs/research/2026-10-31-learn-ai-engineering-templates-handoff.md`,
`.claude/docs/template/research/template-pillar-gaps.md`; `librarian/app/mcp_server/server.py`,
`librarian/core/import_courses.py`; learn-ai-engineering `CLAUDE.md`, `Makefile`, pillar `practice/` folders.

### Findings

| # | Finding | Evidence | Confidence |
|---|---|---|---|
| 1 | Librarian's MCP search cannot see the course. `search_wiki`, `read_page`, `list_domain` and `get_domain_briefing` all walk `WIKI_DIR = data/wiki/`. The importer writes 803 lessons to `data/courses/`, which no tool reads. | `server.py:49`, `server.py:199-227`; `find data/courses -name '*.md' \| wc -l` = 803 | High |
| 2 | Galactus has no MCP configuration. Librarian declares itself only in its own `librarian/.mcp.json`, with a command relative to that repo. No Galactus band can query it today. | `ls galactus/.mcp.json` fails; `librarian/.mcp.json` | High |
| 3 | `/proto-research` has no grounding step. Its output template asks for findings with `file:line` evidence but never for course or wiki evidence. | `proto-research/SKILL.md:100-150` | High |
| 4 | The capability refs overlap the course and carry almost no sources. 18 `cap-*.md` files total 5,740 lines, with 6 lines holding a URL or id. The RAG ref overlaps twelve course notes (6,842 lines) that are cited and reviewed. Their embedded code has no tests behind it, so a coded example from the course is an upgrade, not just more text. | `wc -l`, `grep -cE 'arxiv\|doi\.org\|https?://' cap-*.md` | High |
| 5 | The course's `practice/` folders are unused by prototyping. 33 of the 34 pillars have one (`data-engineering/07` does not), holding 538 tracked code files in 185 examples. Many are runnable offline and imported by notes; test coverage varies and A2a measures it. The importer does not bring in the `.py` files as lessons. | `git ls-files`; `generative-ai/02-rag-retrieval/practice/README.md`; `import_courses.py` | High on counts, Medium on coverage |
| 6 | Prior work already scoped two of the pieces: the 2026-07-29 pillar-gap analysis measured ref drift against the pillars; the 2026-10-31 handoff lists which course templates to port and where. | the two docs named above | High |
| 7 | Galactus already has an eval-harness shape worth copying: four metrics, `--dry-run` scripted adapter, `--json`. | `runs/ai/marketing-comms/evals/run.py` docstring | High |

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| Librarian `search_wiki` + DuckDB index | REUSE | — | Hybrid search, domain filter, retrieval logging all exist. Only the corpus root is wrong |
| Librarian `import_courses.py` | REUSE | — | Already produces lessons with `source:` back-pointers; extend to import the practice manifest as a lesson |
| `cap-*.md` runtime tables and "Agnostic contract" paragraphs | REUSE | — | Galactus-only knowledge. They stay as written |
| `cap-*.md` embedded code files | ADAPT | Yes: all of it stays | Nothing is removed. A tested course example is added above the larger template as the default starting point |
| `.claude/docs/research/2026-10-31-learn-ai-engineering-templates-handoff.md` port list | REUSE | — | Decisions already made; execute as written |
| `template-pillar-gaps.md` | REUSE | — | Becomes the scoring rubric for the eval |
| `marketing-comms/evals/run.py` | ADAPT | — | Copy the shape (metrics, dry-run adapter, JSON) for a prototyping eval |
| Ontology / knowledge-graph skill routing | SKIP | Yes: pillar taxonomy + frontmatter tags | 27 skills route on tags. Build a graph only if the eval shows routing errors |
| Fine-tuning a routing or generation model | SKIP | No | Knowledge changes weekly and the value is citations, which a tuned model cannot emit |

### Assumptions

- **Assumption:** course notes carry enough frontmatter (`title`, `summary`, `source`) for the existing index to rank them without new fields. **Evidence:** `data/courses/ai-engineering/06-eval/eval-engineering.md` frontmatter. **If wrong:** A1 adds a `domain`/`tags` derivation from the path. **Confidence:** High.
- **Assumption:** manifest entries number well below the 538 practice code files, because one entry covers one example folder. **Evidence:** the A2a inventory found 185 examples. **Confidence:** High.
- **Assumption:** Claude Code resolves a stdio MCP server declared in `.mcp.json` with a `uv run --directory` command. **Evidence:** standard `.mcp.json` shape. **If wrong:** register it in `~/.claude.json` for the galactus project instead. **Confidence:** High.
- **Assumption:** a research step that *must* query Librarian will be followed. **Evidence:** none; this repo's own rule says a rule you rely on belongs in a hook. **If wrong:** B3 adds the hook. B3 is therefore in scope, not optional. **Confidence:** Low on prose alone, High with the hook.

### Disconfirming evidence

- *Merging the repos would be simpler.* Checked: the course has its own review gate, ledger and citation rules that Galactus's pipeline does not honour, and Galactus has hooks that would reject course plan docs. A merge breaks both sets of guards. Not found.
- *Librarian already indexes courses through another path.* Checked `WIKI_DIR`, `_stale_pages`, `_full_rebuild`, `_resolve_domain_dir`: all rooted at `data/wiki/`. Not found.
- *Adding code to the refs just recreates the drift problem.* True if copied blindly. C2 therefore records each example's source path and hash, and a check fails when they diverge.

### Key unknowns

- How much Librarian's embedding rebuild costs with 803 more pages (local Ollama; time, not money).
- Whether the practice manifest should be hand-authored YAML or derived from module docstrings. Decision D2 below.
- Baseline numbers: how often today's `/proto-research` output cites anything checkable. A3 measures before anything else lands.

### Recommendation

Make Librarian the single retrieval surface over both the wiki and the course, and make the research
band query it and prove it did. Grow the capability refs with the smallest tested example for each
capability, plus the condition that justifies going beyond it. Measure before and after, including
whether plans overbuild, so "better than bare Claude" is a number.

## Decisions (accepted 2026-11-04, Ramsey)

| # | Decision | Outcome |
|---|---|---|
| Q1 | Course domain naming in Librarian | `course/<subject>` as a domain prefix; `domain="course"` scopes all courses |
| Q2 | Practice manifest format | Hand-authored `practice/manifest.yaml` per pillar, validated by a script |
| Q3 | Index practice `.py` files as search text? | No. Index the manifest; `read_page` resolves a practice path to its file |
| Q4 | Where the eval lives | `galactus/evals/prototyping/` |
| Q5 | Capability refs | Baseline first, then grow them with tested examples. No trimming (changed by Ramsey) |

## Execution constraints found on 2026-11-04

- **Shared working trees.** Librarian has another session's staged changes on `main`, including `core/import_courses.py`. learn-ai-engineering has unstaged `deck.yaml` edits. Agents stage only their own paths and leave these alone.
- **Galactus guards.** Its hooks fire only in a session rooted in `galactus/`. Phase A runs from a session rooted elsewhere, so no hook protects it. Phases B and C edit skills and hooks, so run them from a Galactus-rooted session.
- **State machine.** This doc stays `PLANNED`. Only `/proto-refine` may write `REFINED` or `READY`, and Phase A is a foundation that does not change the pipeline. Run `/proto-refine` before Phase B.

## Plan

Four phases. Within a phase, tasks run in parallel; a phase starts when its dependencies are
done. Every task names the subagent, the model and the brief. Briefs are what the agent gets
and nothing else, so each states the goal, the files, what is already ruled out, and done-when.
Agents never commit. Each task ends with staged paths and a reported `make test` or `uv run pytest`
result.

Model rule used below: **haiku** for inventory and tabulation with no judgment; **sonnet** for
well-specified code changes with tests to run; **opus** for edits to skill prose, security-sensitive
code paths, and anything whose spec is a judgment call; **fork** where the agent needs this session's
findings and no brief could carry them.

### Phase A — independent foundations (parallel)

**A1. Librarian indexes the course.** Repo: librarian. Agent: `general-purpose`, model **opus**
(the `read_page` path check is the `private/` invariant; a wrong edit leaks). Done when:
`search_wiki("CRAG retrieve grade rewrite", domain="course")` returns a course lesson;
`read_page("course/generative-ai/02-rag-retrieval/notes/08-agentic-rag-prince")` returns it;
`list_domain("course/ai-engineering")` lists its modules; wiki-only searches are unchanged;
`uv run pytest tests/app -q` passes with new tests for each of those four; the existing retrieval
eval shows no regression for wiki queries, with before and after numbers reported.

> Brief: In `~/workspace/librarian`, extend the MCP server so `data/courses/` is indexed and
> searchable alongside `data/wiki/`. Read `app/mcp_server/server.py` fully first and
> `core/import_courses.py` lines 1-60 for the course layout. Add `COURSES_DIR` beside `WIKI_DIR`
> (env-overridable like `WIKI_DIR`). Every function that walks `WIKI_DIR.rglob("*.md")` walks both
> roots; a course page's domain is `course/<subject>` derived from its path; `_resolve_domain_dir`
> resolves `course` and `course/<subject>`; `read_page` accepts `course/<relative path>` and keeps
> the existing `is_relative_to` guard for both roots (the `private/` invariant in the docstring at
> line 130 must still hold; add a test that `read_page` cannot escape either root). Skip
> `_flashcards.md` and `_course.md` from search ranking unless they already rank sensibly; test
> both ways and keep the simpler. Do not change the embedding model, the DuckDB schema beyond
> what the domain needs, or `import_courses.py`. Another session has staged edits in this repo:
> do not modify or unstage them. Before and after your change run the offline retrieval eval (read
> the `eval` targets in the Makefile; use one that needs no API key), because 803 new pages can
> push wiki pages out of unscoped results. Report what an unscoped search should return and why.
> Run `make index-rebuild` once and report the wall time; if the database is locked, report that
> rather than killing anything. Stage by explicit path. Report pytest output verbatim.

**A2. Practice manifest in the course.** Repo: learn-ai-engineering. Two agents in sequence.

A2a. Agent: `general-purpose`, model **haiku**, using a script. Done when: a CSV in the scratchpad
lists every tracked practice example with pillar, path, purpose, referencing notes and checker.

> Brief: Script an inventory from `git ls-files` for `practice/` code in the five pillared subjects.
> Do not edit the repo. Exclude paths in `THIRD_PARTY.md` and mark them `third_party`. Group files
> in one example folder into one row. Record purpose from the first docstring line or README row,
> notes that mention the filename, and any test beside it. Leave a field empty if unknown.

A2b. Agent: `general-purpose`, model **sonnet**. Done when: `practice/manifest.yaml` exists in every
pillar with a practice folder; `scripts/practice/check_manifest.py` validates schema, paths and note
links; it is wired into `make test`; failures caused by other sessions' edits are reported, not fixed.

> Brief: Using the CSV at <path>, author one `practice/manifest.yaml` per pillar in
> `~/workspace/learn-ai-engineering`, one entry per example. Fields: `path`, `purpose`, `demonstrates`
> (notes), `pattern` (retrieval, judge, loop, graph, tool-agent, guardrail, budget, finetune, eval,
> analysis, other), `language`, `runs_offline`, `verified_by` (a command, or `none`), `licence`
> (`course` or the `THIRD_PARTY.md` licence). Read a file before stating its purpose. Never set
> `verified_by` to a command you did not run. Match the style of `scripts/practice/crosswalk.py`.
> Do not touch notes or decks. Stage by explicit path.

**A3a. Prototyping eval harness.** Repo: galactus. Agent: `general-purpose`, model **opus** (metric
design is the judgment). Done when: `evals/prototyping/cases.jsonl` holds eight prompts, two each for
RAG, evals, agent loops and guardrails; each case states a `minimum_solution` written before any
output is seen; `run.py` scores the metrics below; `--dry-run` works; tests pass and are in `testpaths`.

| Metric | Type | What it shows |
|---|---|---|
| Scope fit | judge, per case | Does the plan propose components beyond `minimum_solution` with no stated need? The primary outcome |
| Claim support | judge, per cited claim | Does the cited source say what the plan claims? PASS, FAIL or CANNOT_GRADE |
| Unsourced numbers | deterministic | Numbers with no source or setup |
| Course citations, practice reuse | deterministic | Compliance only. These rise by construction, so they can never prove improvement |

> Brief: Build `evals/prototyping/` modelled on `runs/ai/marketing-comms/evals/run.py` (read it first).
> Use `uv`, never pip. Metrics as in the plan table. Judges take the course template from `git -C
> ~/workspace/learn-ai-engineering show 6ee939f:ai-engineering/06-eval/templates/judge-prompt.md`.
> Judging must also work with no API key: `run.py --judgments <file>` accepts verdicts produced
> elsewhere. Do not produce any baseline outputs. Report that eight cases give a direction, not
> significance. Stage by explicit path.

**A3b. Baseline.** Eight fresh agents, one per case, model **opus**, with no knowledge of the metrics or
`minimum_solution`. Each reads `.claude/skills/proto-research/SKILL.md`, follows it, and writes output to
the scratchpad, without reading learn-ai-engineering or Librarian. Fresh judge agents, model **sonnet**,
then grade the outputs without seeing this plan. Scores go to `baseline-2026-11-04.json`. D1 must use the
same model and procedure.

Baseline conditions, which D1 must repeat except for the skill change: outputs come from a detached worktree
at HEAD, so the eval and this plan are not discoverable. Judges have web access. Generator and judges are both
Claude, though the course's judge template asks for a different model family, so scores are not independent
of model family. Scope fit uses one fresh judge per case. Claim support uses one fresh judge per case working through all
of that case's claims, because the baseline produced 278 claims. Judgments within a case may therefore influence
each other. Generators may use WebFetch, which the skill's `allowed-tools` omits.

Baseline result, 2026-11-04, in `evals/prototyping/baseline-2026-11-04.json`:

| Metric | Baseline |
|---|---|
| Scope fit | 8 of 8 PASS |
| Extra components, justified or not | 16 in total, mean 2.0, range 0 to 4 |
| Document length | 27,649 words, 2,734 to 4,280 per case |
| Claim support | 235 PASS, 5 FAIL, 42 CANNOT_GRADE of 282 |
| Unsourced numbers | 287 of 449 |
| Course citations and practice reuse | 0 and 0 |

Changes made after seeing the baseline, before any skill change. D1 uses the harness as changed:

1. Scope fit sat at its ceiling, so it cannot show improvement. Any stated need clears it. Added `extra_components`,
   a judged count of proposed components beyond the minimum, ignoring justification, plus a word count. Added after
   the scope verdicts were seen, so it is a post-hoc metric, and the D1 comparison should say so. Scope fit is kept
   and still labelled primary. Whether to promote the count is a decision for Ramsey.
2. The first scoring gave 143 PASS, 6 FAIL and 129 CANNOT_GRADE of 278, and most CANNOT_GRADE came from the harness.
   Documents shorten `.claude/specs/agent-eval.md` to `agent-eval.md`, which did not resolve, and `:35` shorthand was
   not read. A shortened path now resolves only when exactly one file fits, a bare name is searched only under
   `.claude/`, and an ambiguous name stays CANNOT_GRADE. A bare `README.md` no longer means the repo root, which had
   produced two false FAILs. `:35` attaches to the file cited just before it, and to none after a sentence naming two.

Judging conditions D1 must repeat. Claims whose prompt did not change kept their first verdict, and 129 prompts were
re-judged in five fresh batches by case. The count used one fresh judge across all eight documents. The prompt text
of unchanged claims is identical, so a D1 with one batch per case is comparable but not identical. Several judges
reported lenient PASSes where a cited principle was applied by the author, and all judge results are uncalibrated.
So treat the 235 as an upper bound. WebFetch answers through a small model, so URL claims were judged on quoted
passages, not raw pages.

This baseline measures `/proto-research` documents, not code. The refs' examples mainly act at `/proto-execute`, so
D1 cannot show whether generated code got smaller. Decision for Ramsey: add a code-stage run.

**A4. Map capability refs to course examples.** Repo: galactus, course read-only. Agent:
`general-purpose`, model **sonnet**. Done when: `.claude/docs/research/2026-11-04-cap-ref-coverage.md`
has one table per `cap-*.md`, and a ranked list of the refs that would gain most from an example.

> Brief: For each `~/workspace/galactus/.claude/skills/new-agent/references/cap-*.md`, split it into
> sections. Find the course note and `practice/` example covering the same ground in
> `~/workspace/learn-ai-engineering`, reading candidates rather than matching names. Classify each
> section: CONTRACT (Galactus-only table or contract), TEMPLATE (embedded code; note whether anything
> tests it), or GUIDANCE. For each ref name: the smallest tested course example, its licence from
> `THIRD_PARTY.md`, its language, and any gap where no example exists, in Python or TypeScript. Propose
> the condition that justifies moving from the example to the larger template. Edit nothing but the report.

### Phase B — wire Galactus to Librarian (needs A1)

Re-planned 2026-11-04 after `/proto-refine` returned NOT-READY. The five gate items are resolved below.
Run from a session rooted in `galactus/` so the hooks fire. One session. Baseline: `uv run pytest --tb=no -q`
gives 1129 passed and 6 skipped. `bash .claude/hooks/tests/test_plan_status_validate.sh` gives 128 passed and 0 failed.
That hook suite is not in `make test` or CI, so every step that touches the hook runs it by hand.

#### B Goal
`/proto-research` queries Librarian and leaves a record that a hook can check. The pipeline still works when Librarian is absent.

#### B Open Questions (resolved 2026-11-04, Ramsey)
1. **Goal.** As above. Confirmed.
2. **Degraded contract.** `### Course grounding` must hold at least one `- query:` line, or a line
   `Librarian: unavailable — <reason>` with a non-empty reason. An empty heading is rejected. An outage is
   recorded, not blocked, so research never stalls on Librarian. *(Closes gate items 1 and 2.)*
3. **Hook trigger.** The rule applies to any write where `Status:` is `RESEARCHED`. It is not keyed on `From:`,
   because `/proto-research` creates its doc directly at `Status: RESEARCHED` with no `From:` line
   (`proto-research/SKILL.md:116`). A `From:`-keyed check would never fire on the main path. No plan doc is at
   `RESEARCHED` today (survey of `.claude/docs/plans/`, 2026-11-04), so no existing doc breaks. The only doc at
   `RESEARCH` is `2026-08-15-fast-loop-borrowables`. It gains the requirement when it advances, which is intended.
   *(Closes gate item 4.)*
4. **B1 scope.** Galactus only. Rendered projects get no Librarian entry in Phase B. The root `.mcp.json` is outside
   copier's `_subdirectory: template` (`copier.yaml:2`), so a render cannot include it. Step B1 proves that.
   Template wiring is later work. *(Closes gate item 3.)*
5. **B2 brief.** B2 is written out as a brief for a `general-purpose` agent, not a fork. *(Closes gate item 5.)*

#### B Out of scope
- Shipping Librarian to rendered projects (`template/`), per Q4.
- The `RESEARCH → PLANNED` edge, and docs that `/proto-plan` creates directly at `PLANNED`. Neither passes through
  `RESEARCHED`, so the hook does not see them. This is a known bypass, recorded here and not closed. Revisit if D1
  shows ungrounded plans entering through it.
- Checking that the `- query:` lines name queries that actually ran. The hook checks shape. Grounding theatre is
  scored by A3's claim-support judge, not by B3.
- Wiring `.claude/hooks/tests/` into `make test` or CI. This is a real gap, but it is separate work.
- Librarian code. Phase A owns it. Nothing in `~/workspace/librarian` is edited.

#### Step B1: Register Librarian for Galactus sessions
**Agent**: `general-purpose`, model **sonnet**.
**Files**: `.mcp.json` (new, repo root).
**What**: Declare a stdio server named `librarian` that runs Librarian's server through `uv --directory`, with the
directory taken from `LIBRARIAN_DIR`. Do not pass `ANTHROPIC_API_KEY`: `librarian/.mcp.json` passes it, but
`app/mcp_server/server.py` never reads it (`grep -n ANTHROPIC server.py` returns nothing).
**Snippet**:
```json
{
  "mcpServers": {
    "librarian": {
      "command": "uv",
      "args": ["run", "--directory", "${LIBRARIAN_DIR:-/Users/ramsey-wise/workspace/librarian}",
               "python", "app/mcp_server/server.py"]
    }
  }
}
```
**Blocker to settle in-step:** check whether Claude Code expands the `${VAR:-default}` form in `.mcp.json` args.
If it does not, drop the default, require `LIBRARIAN_DIR`, and set it in `.claude/settings.local.json` `env`, which
is untracked. Record which form worked. A hard-coded absolute path in a tracked file is acceptable only as the
default in the `:-` form.
**Test**:
1. `claude mcp list` from `galactus/` shows `librarian` as connected.
2. `LIBRARIAN_DIR=/nonexistent claude mcp list` shows `librarian` as failed, and the command still exits 0
   with the other servers listed. This is the absent-Librarian check.
3. `DST=$(mktemp -d) KEEP=1 PYTEST_ARGS=--co make test_render`, then `test ! -e "$DST/.mcp.json"`. A render
   carries no Librarian entry.
**Done when**: all three tests pass and their output is pasted into the step report.

#### Step B2: Course-grounding rule in the status hook
**Agent**: `general-purpose`, model **opus**. This is a hook that every plan-doc write passes through, and GAL-14 is the precedent.
**Files**: `.claude/hooks/plan_status_validate.sh`, inserted before `if issues:` at line 271, after the
`Epistemic` block (lines 247-270). `.claude/hooks/tests/test_plan_status_validate.sh`: the fixture at line 63,
plus a new section before the spike block at line 563.
**What**: When `token == "RESEARCHED"`, find `### Course grounding` inside `## Research`, meaning after the
`## Research` heading and before the next `## ` heading. Use `lines`, which is already unfenced (line 74), so a fenced
example does not count. The section body runs to the next `##`/`###` heading. Reject the write if the section is
missing, or if it has neither a `- query:` line nor a `Librarian: unavailable — <reason>` line. Accept `—` or
`-`, and require a non-empty reason. The rejection message names the two accepted forms. The rule adds no new exit
path: it appends to `issues`, so the existing exit-2 path, `log_event` and the spike skip (line 11) all still apply.
**Snippet** (after):
```python
# Course grounding — a doc at RESEARCHED must show it queried the course, or say why
# it could not (knowledge-grounded-prototyping, Phase B). Keyed on the state, not on
# From:, because /proto-research's origin write declares no From:.
if token == "RESEARCHED":
    body = section_body(lines, parent="## Research", heading="### Course grounding")
    if body is None:
        issues.append("  Status: RESEARCHED requires `### Course grounding` under `## Research`")
    elif not any(QUERY_RE.match(l) or UNAVAILABLE_RE.match(l) for l in body):
        issues.append("  `### Course grounding` needs a `- query:` line or `Librarian: unavailable — <reason>`")
```
**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`. Update the line-63 fixture to carry a minimal
grounding section. Add these cases:
- Accepted: a query line; the unavailable line; the `-` hyphen form.
- Blocked: no section; an empty heading; the unavailable line with no reason; the section under a different
  `## ` heading; the section only inside a fence.
- Accepted: a `PLANNED` doc with no section. This proves the rule only applies at RESEARCHED.
- On a `spike/*` branch, a `RESEARCHED` doc with no section is accepted.

Then `uv run pytest --tb=no -q` must still show 1129 passed.
**Done when**: the hook suite reports `0 failed` with 128 + the new cases passing. This doc, which is at `PLANNED`,
still accepts writes, so its Status line can be edited without being blocked.

#### Step B3: Grounding step in `/proto-research` and `research-scout`
**Agent**: `general-purpose`, model **opus** (skill prose).
**Files**:
- `.claude/skills/proto-research/SKILL.md`:
  - frontmatter line 5: add `mcp__librarian__search_wiki mcp__librarian__read_page mcp__librarian__list_domain`
    to `allowed-tools`. Without these the skill cannot call Librarian at all, which is a defect nobody had recorded yet.
  - output template, lines 113-150: add `### Course grounding` after `### Findings`.
  - a short "Course grounding" constraint after constraint 4 (around line 103).
- `.claude/agents/research-scout.md`: the output contract (lines 20-40) gains the same section, and the `tools:` line
  (line 4) gains the same three MCP tools.

**What**: Before writing findings, run at least one `search_wiki(query, domain="course")` per core question. Record each query as
`- query: \`<text>\` (domain=…) → N hits`, with a nested `- used: course/<path>` for every hit the findings rely on,
or `→ 0 hits — no course coverage for <topic>`. If the MCP tools are missing or error, write
`Librarian: unavailable — <the error text>` and continue. Never stop, and never silently omit the section. Findings
that rely on a course hit cite its `course/` path the way codebase findings cite `file:line`.
**Snippet**: the template block is the preview confirmed in Q2 above, with the two accepted forms.
**Test**:
1. `grep -c 'Course grounding' .claude/skills/proto-research/SKILL.md .claude/agents/research-scout.md` returns at least 1 each.
2. `grep -c 'mcp__librarian__search_wiki' …` returns 1 each.
3. Copy the new template block into a temporary plan doc at `Status: RESEARCHED`. Run the B2 hook on it: exit 0.
   With the block removed: exit 2. This proves the skill's template and the hook agree.

**Done when**: all three tests pass.

#### Step B4: Downstream readers — `/proto-design`, `/proto-execute`, `/new-agent`, `/proto-review`
**Agent**: `general-purpose`, model **opus** (skill prose).
**Files and edits**:
- `.claude/skills/proto-design/SKILL.md`. Output format `## Grounding` at line 367: add `Course:`, with one
  `search_wiki` query per layer of the five-layer walk (Stage 1, lines 104-266), in the same `- query:` form, so the
  degraded line applies here too. Add `mcp__librarian__*` tools to its allowed-tools if the frontmatter restricts them.
- `.claude/skills/proto-execute/SKILL.md`, "Before starting" (lines 26-52): add a step 4. If the plan names a
  pattern from the manifest vocabulary (retrieval, judge, loop, graph, tool-agent, guardrail, budget, finetune, eval),
  `read_page` that pillar's `practice/manifest.yaml` entry, and start from the listed file when `verified_by` is
  not `none`. If Librarian is unavailable, say so and proceed.
- `.claude/skills/new-agent/SKILL.md`, Step 4 (lines 70-90): one paragraph with the same instruction, placed before the
  `cap-*.md` table. C2's `## Start here` sections later replace this lookup for refs that have one.
- `.claude/skills/proto-review/SKILL.md`, Stage 2 Plan Fidelity (lines 96-110): one check. If the plan doc is at
  or past `RESEARCHED` and has `### Course grounding`, every `used: course/<path>` must resolve through `read_page`.
  An unresolved path is an `important` finding, not a blocker. A doc that predates this plan, with no section,
  is not flagged.

**Test**: `grep -n 'Course grounding\|manifest.yaml\|read_page' <each file>` shows the edit in each of the four
files. `uv run pytest --tb=no -q` still gives 1129 passed.
**Done when**: the grep shows all four, the suite is green, and no edit touches a `template/.claude/` symlink target
other than by editing the root file. `ls -la template/.claude/skills/` shows the same symlinks before and after.

#### Step B5: Pipeline table line
**Files**: `CLAUDE.md`, the pipeline table row for `/proto-research`.
**What**: One clause: "grounds findings in the course via Librarian (`### Course grounding`, hook-enforced at
`RESEARCHED`)".
**Test**: `grep -n 'Course grounding' CLAUDE.md`.
**Done when**: one line changed, nothing else in `CLAUDE.md`.

#### B Test plan
| What | Command | Expected |
|---|---|---|
| Hook contract | `bash .claude/hooks/tests/test_plan_status_validate.sh` | `0 failed`, at least 128 + 9 passed |
| Python suite | `uv run pytest --tb=no -q` | 1129 passed, 6 skipped (unchanged) |
| MCP up / absent | `claude mcp list`, then the same with `LIBRARIAN_DIR=/nonexistent` | connected / failed, and the session survives |
| Render excludes server | `make test_render` with `KEEP`, then `test ! -e $DST/.mcp.json` | true |
| Skill and hook agree | B3 test 3 | exit 0 with the block, exit 2 without |

#### B Risks and rollback
| Risk | Effect | Mitigation / rollback |
|---|---|---|
| B2 rule misfires on a doc it should pass | every write to that doc is blocked (PostToolUse exit 2) | Fixture cases cover the accept paths. Rollback: `git restore --staged --worktree .claude/hooks/plan_status_validate.sh`. Nothing persistent is written; the hook only reads docs and appends to the log. |
| `${VAR:-default}` not expanded in `.mcp.json` | server fails to start for everyone | the B1 blocker check settles it before the step is done; fallback recorded |
| Librarian slow to start (DuckDB open) | MCP tools appear late or time out | the degraded line covers it, and research proceeds |
| Agents write `- query:` lines for queries they never ran | the hook passes theatre | out of scope for B; scored by A3 claim support in D1 |
| `.claude/hooks/tests/` not in CI | a later edit regresses B2 silently | listed out of scope; run the suite by hand on every hook edit |

Everything in Phase B is a staged edit to tracked files. Rollback for the whole phase is `git restore --staged
--worktree` on the paths listed above. Nothing is committed.

#### B results (2026-11-04)

Steps B1 to B5 are staged, not committed. Corrections to the steps above:

- **B1.** The `${LIBRARIAN_DIR:-default}` form works. Through `--mcp-config` the server reports `connected`, and with `LIBRARIAN_DIR=/nonexistent` it reports `failed` while the session still succeeds. `claude mcp list` shows only `Pending approval` until Ramsey approves the server in an interactive `claude`, so test 1 as written cannot pass before that. `copier` was not on PATH, so the render check ran through `uvx copier` directly, not `make test_render`.
- **B2, B3 scope.** The hook, `proto-research` and `research-scout` do not ship to rendered projects, so the rule applies in this repo only.
- **B3 test 3.** The template's `Track: [ml | agent]` placeholder fails the hook by itself, so `Track:` must be filled in before the "exit 2 without the block" half means anything. Fan-out needed a merge rule that the step did not list: scout reports use `##` and live outside the hook's reach.
- **B4.** `read_page` cannot resolve `practice/manifest.yaml`, because manifests are not in `data/courses/`, so Q3's "index the manifest" did not land. The skills read the manifest from the course checkout (`${LEARN_AI_DIR:-~/workspace/learn-ai-engineering}`) instead. 102 of 187 entries have `verified_by: none`.

### Phase C — grow the refs from reviewed code (needs A2, A4 and the A3b baseline file)

**C1. Port the handoff templates.** Agent: `general-purpose`, model **sonnet**. Done when: every
row marked **yes** in `.claude/docs/research/2026-10-31-learn-ai-engineering-templates-handoff.md` is recovered with the git
command in that doc and placed at its suggested home; **maybe** rows are listed in the report
with a one-line recommendation and not ported; `uv run pytest -q` passes.

**C2. Add tested examples to the capability refs.** Agent: `general-purpose`, model **opus**. Done when:
each ref with a usable example from A4 gains a `## Start here` section above its templates: the smallest
tested course example, its source path, content hash and verify command, and a `Go further only if` line
naming the need that justifies the larger template. Existing templates and contracts stay. Only `licence:
course` code is inlined; third-party examples are linked. Refs with no example list the gap for the course.
`/new-agent` tells the agent to start there. A check fails when an inlined example differs from its source,
and skips cleanly where the course is absent, because refs ship in rendered projects. The `review` agent
runs on the diff.

**C3. Specs cite the course.** Agent: `general-purpose`, model **sonnet**. Done when: each
`agent-*.md` spec has a `Course:` line under its opening question pointing at the pillar or
notes that justify it, found via Librarian search; nothing else in the specs changes.

**A4 results that shape C2 (2026-11-04).** Coverage is uneven, per `.claude/docs/research/2026-11-04-cap-ref-coverage.md`:
- C2 starts with the refs ranked highest there: hitl, genai, mcp, guardrails, observability, langchain.
- The smallest example is sometimes a code block in a note, so the C2 hash check must handle a note block as well as a practice file.
- batch, kg, a2a, search and vision have no usable course example. Their refs stay as they are until the course has one. Writing those labs is course work through `/practice`, and it is not part of this plan.
- Authored course code has no stated licence: there is no root LICENSE and `THIRD_PARTY.md` lists only copied material. Refs ship into rendered projects, so Ramsey decides this before C2 inlines any code.

#### C results (2026-11-04)

Defaults set by the orchestrator, pending Ramsey's review: link-only, and no code-stage eval. These replace C2's inlining and hash check. See `.claude/docs/decisions/2026-11-04-knowledge-grounded-prototyping-wargame.md`.

- **C1: narrowed, per Ramsey 2026-11-04.** Ported the harness and loop templates and `generate-then-verify.py` to `.claude/skills/new-agent/references/`, with per-file notices and `THIRD_PARTY.md`. The two Context-Engineering files are dropped, and the eval templates are held because no home exists. Details are at the end of the handoff doc.
- **C2: done for 9 refs whose example was run:** hitl, genai, mcp, guardrails, observability, langchain, compaction, finetune, rlhf. Links are pinned to course commit `826a59943764619151f9c05dfd78a485b6e4271b`, and no course code is inlined. Labels state what ran, not "tested" (WG-007). Unchanged: rag, forecast and cluster (example not run), streaming (weak match), batch, kg, a2a, search and vision (no example). The `review` agent was not run; the diff (additions only) and all 11 links were checked directly.
- **C3: done for 11 specs.** `agent-runtime.md` says `Course: none found`, which is a gap for the course.

#### D1 rule, written before any run (2026-11-04)

Decided by Ramsey 2026-11-04: run one case first; D3 is deferred. War-game items: WG-001, WG-004, WG-006, WG-012.

**Preflight: one case, `rag-runbook-search`, chosen before any output exists.** It is not evidence about the skill. It passes only if all of these hold:
1. The snapshot has the new skill and has no `evals/`, no plan docs and no `.git`.
2. The output has at least one `- query:` line, and no `Librarian: unavailable` line.
3. Every `- query:` line matches a new row in Librarian's `logs/retrieval.jsonl`, so grounding really happened.
4. The output shows no sign of the eval or the plan: no `minimum_solution`, `extra_components` or plan file name.

Extra components are judged and reported, but one case cannot count as an improvement.

**Full-run rule, rewritten 2026-11-04 before any full-run output exists. It replaces the conditions below.** Evidence: `.claude/docs/plans/2026-11-04-prototyping-improvements-before-d1.md`.
- The seven other cases are the held-out set. `rag-runbook-search` was used for tuning and is excluded from every improvement claim.
- The claim is "the new skill against the old skill". It cannot credit course grounding alone.
- Generators on both sides have Bash, under the sandbox in the improvements plan. Run 2 baseline repeats on the old skill for generator noise.
- Every count and verdict gets 5 judges. One judge per case is not usable: on one output, scope fit split 2 to 3.
- Improvement needs mean extra components to fall by more than the noise, and mean deferred components to rise by less than extras fall. Scope fit is reported, never a gate. Claim support must be judged on both sides with one setup, against the commit each output was written from.
- Estimated cost: about $32 for seven cases and $9 for two repeats, at arms A and B's average of $4.65, plus judges.
- Not started. As of this rewrite, arm B misses the deferred rule on the tuning case, so it needs Ramsey's decision first.

**Full run, only if Ramsey asks for it after the preflight.**
- The other seven cases run once. No re-run to improve a number. A run that fails on infrastructure may be repeated, and is reported as repeated.
- First re-run two baseline cases on the baseline skill, to measure the noise in extra components.
- `deferred_components` is added and scored on both baseline and after, since `Go further only if` wording could move the count on wording alone (WG-008).
- Improvement is claimed only if total extra components fall by more than the measured noise, deferred components do not rise by as much, scope fit stays at 8 of 8 and claim support drops by at most 5 points. Anything else is reported as no evidence. Eight cases still give only a direction.

**Harness:** `run.py` sha256 `be687dd07291f7e1…`, after adding `course grounding` to `_NO_CLAIM_SECTIONS`. No baseline output has that section, so baseline scores do not change.

**Baseline provenance, recovered from its session transcript:** generators `claude-opus-5-5`, judges `claude-sonnet-5-5`. The base commit was not recorded. The outputs are now in `evals/prototyping/baseline-outputs-2026-11-04/`. Raw judge files are still only in a temp folder.

**Known differences from the baseline:** generators run through `claude -p`, not a subagent, because the Librarian server has to be passed explicitly to a snapshot outside the approved project. They have no Bash, and their prompt allows Librarian in place of forbidding it.

**Preflight result (2026-11-04): passed all four checks. Not evidence about the skill.** Files are in `evals/prototyping/preflight-2026-11-04/`.

| `rag-runbook-search` | Baseline | Preflight |
|---|---|---|
| Extra components | 4 | 4 |
| Scope fit | PASS | FAIL (reranker proposed with no stated need) |
| Words | 4,175 | 5,800 |

- All 8 `- query:` lines match new rows in Librarian's log, and the 8 notes it reports reading match 8 `read_page` rows. Generator cost was $4.08 over 8.4 minutes.
- One judge per metric and no repeat, so the noise is unknown. Claim support (87 prompts) was not judged.
- Librarian returned its `DEGRADED RETRIEVAL` notice on the first search, so the index was behind the files during this run.
- The snapshot's copy of `plan_status_validate.sh` names this plan's file in a comment. The plan itself was absent, and the output shows no sign of it.
- The server was passed with `--mcp-config`. `claude mcp list` still shows it pending approval in `galactus/`.
- The full run has not been requested.

**D3 deferred, per Ramsey 2026-11-04.** It needs Librarian and course changes (WG-011).

### Phase D — prove it (needs B, C)

**D1. Re-run the eval.** Generating agents use model **opus** and judges **sonnet**, matching A3b, because a model change would confound the result. Done when: the eight cases
run through the new `/proto-research` with Librarian available; results in
`evals/prototyping/after-<date>.json`; a before/after table in this plan under `## Results`.
The table leads with extra components and notes that the metric was added after the baseline was seen.

**D2. Independent attack.** `/war-game` on this plan before C starts, and `/fog` on the
grounding step: what does `/proto-research` do when Librarian is down, returns nothing, or
returns a stale note? Both write to `.claude/docs/decisions/` and never touch `Status:`.

**D3. Course-side signal.** Agent: `general-purpose`, model **haiku**. Done when: Librarian's
retrieval log (`_log_retrieval`) is read by the course's `make signals` so `/weekly` reports
which notes prototyping sessions actually pull, and which queries miss.

### Parallelism and sequencing

```
A1 ─┐
A2 ─┼─ (A3 baseline recorded) ─► B1 ─► B2 ─► B3 ─► B4 ─► B5 ─┐
A3 ─┤                                                        ├─► D1, D2 fog
A4 ─┘──────────────────────────── D2 war-game ─► C1, C2, C3 ─┘        D3
```

A1, A2a, A3a and A4 run in parallel, then A2b and A3b. B needs only A1. C needs A2 and A4 and
should not start until the A3b baseline file exists. D1 is the last step.

### Out of scope

- Merging repos. Rejected in Research.
- Ontology or graph-based skill routing. Revisit only if D1 shows routing errors.
- Fine-tuning. Rejected in Asset verdicts.
- Importing practice `.py` files as searchable chunks (Q3).
- Any edit to course notes. The course's own skills own those.

### Risks

- **Librarian rebuild time.** 803 more pages through a local embedder. A1 reports wall time; if
  it exceeds ten minutes, index courses with FTS only and embed lazily.
- **Grounding theatre.** An agent can run a query and ignore it. The judge metric in A3 scores
  whether the plan's claims match the cited note, not whether a citation exists.
- **Drift between refs and course.** Inlined examples can go stale. The C2 hash check catches it.
- **Refs get longer.** Refs load on demand, but a bigger file costs context when loaded. Keep each
  `Start here` small, and let the scope-fit metric show whether the examples help.
- **Metric gaming.** Citation counts rise by construction, so only scope fit and claim support count as
  evidence of improvement. Eight cases show direction, not significance.
- **Cross-repo writes from one session.** Each agent stages only in its own repo by explicit
  path; nothing commits.
