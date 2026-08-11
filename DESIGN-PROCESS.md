# How this repo is built

A working Claude Code setup: 33 skills, 4 subagents, 9 hooks, and 14 specs, wired into a
design → research → plan → execute → review pipeline.

This document explains the five things underneath it — **prompt, context, harness, loop,
graph** — and where each one is implemented. Every claim below points at a file you can
open. Where something is deliberately absent, it says so.

> Also published as a [formatted page](https://claude.ai/code/artifact/569486e9-5228-415e-8984-bea79a79928c)
> (same content, easier to read).

> The organising idea: **prompt ⊂ context ⊂ harness.** A prompt is what you say. Context
> is everything the model can see when you say it. The harness is what happens regardless
> of what the model decides. Loops and graphs are what you build once those three hold.

---

## 1. Prompt — the layer everyone starts and stops at

A prompt is an instruction, and an instruction is *probabilistic*. It shifts the odds. It
does not constrain.

That single property decides where everything else in this document goes. The rest of the
stack exists because instructions are the weakest available enforcement mechanism, and
most systems that feel unreliable are systems that used only this layer.

**Where prompts live here:** `.claude/skills/*/SKILL.md`. Each skill is a prompt that
loads on demand — its frontmatter `description` decides *when*, its body decides *what*.

Two properties matter more than wording:

**Prompts are addressed to a role, not to "the model."** `akira-scan` is told it is a
fast parallel defect scanner and that style is the linter's job. `sanyi-review` is told
it judges a diff against a *written contract* and must return zero findings when no
contract exists. Same underlying model, different job, different failure mode to guard.

**A prompt should say what to do when the input is wrong.** The most common defect in a
prompt is that it describes only the happy path. Compare:

> **A brief with an empty diff is an error, not an empty review.** Fail loudly and stop.
>
> A reporter handed nothing will return no findings, and no findings is indistinguishable
> from a clean review — so a broken diff command reads as an approval.
> — `.claude/skills/review-shared/references/context-brief.md`

Without that line, a review whose diff command silently failed produces "no findings,"
which renders as *approved*. The dangerous case is not the model being wrong. It is the
model being **empty** and that emptiness being read as a pass.

---

## 2. Context — a minimization problem, not a filling problem

The instinct is to give the model everything available. That is backwards. Every
irrelevant token competes with the relevant ones, and a long context is not a neutral
container — it actively dilutes.

Four levers, applied **in this order**, because cost rises left to right:

| Lever | What it means | Here |
|---|---|---|
| **Write** | Put it somewhere durable instead of in-context | The plan doc; `review-findings.jsonl` |
| **Select** | Load only what this step needs | Skill frontmatter; `references/` loaded on demand |
| **Compress** | Summarise before passing on | `/compact` at phase boundaries |
| **Isolate** | Give it its own context window | Subagent reporters |

**Isolate is last on purpose.** It is the only lever that multiplies token spend — you
now pay for N contexts instead of one. It is also the only one that gives a hard
guarantee: a subagent *cannot* see what it was not given.

### The four types, and the one that has no natural bound

Static (specs, conventions), dynamic (the current diff), retrieved (a spec fetched
on demand), and historical (what happened earlier in the session).

**Historical is the only type without a natural bound.** The others are sized by
something external — the spec is as long as it is, the diff is as big as it is. History
grows monotonically with the session and never shrinks by itself. Every context strategy
is, in practice, mostly a strategy for history.

This repo's answer is that **the plan doc is the bus**. Research writes `## Research`;
plan writes `## Plan`; execute reads the plan and writes code. Each phase then runs in a
*fresh session*:

```
Spawn prompt (execute — fresh session):
│ cd <repo-path>
│ Read <plan-doc-path>
│ /proto-execute <slug>
```
— `.claude/skills/proto-plan/SKILL.md`

The deliberation that produced a decision is exactly what the next phase should *not*
inherit. Write beats compress; a decision recorded in a file is worth more than the same
decision summarised in a transcript, because the file survives the session.

---

## 3. Harness — the part that is not optional

> **Agent = Model + Harness.**

The harness is everything that happens whether or not the model cooperates. It does four
jobs: it **constrains** what can happen, **informs** the model of what it needs,
**verifies** what came back, and **corrects** when verification fails.

### The enforcement ladder

The central practical claim of this whole document:

```
hook  >  linter  >  test  >  tool schema  >  instruction line
 ←── deterministic                        probabilistic ──→
```

**A rule in documentation is probabilistic; a rule in a hook is deterministic.** Any rule
you actually depend on should move as far left as it can go. This repo's own `CLAUDE.md`
states the rule and then applies it to itself:

> **A rule you rely on belongs in a hook, not here.** This file is a table of contents.
> If an agent can ignore a line here with no consequence, that line is documentation.

### What is actually enforced

Nine hooks, wired in `.claude/settings.json`, each exiting `2` to block:

| Hook | Event | Blocks |
|---|---|---|
| `pip_guard.sh` | PreToolUse:Bash | `pip install` — this project uses `uv` |
| `secrets_scan.sh` | PreToolUse:Write\|Edit | AWS/Anthropic/OpenAI/GitHub keys reaching disk |
| `destructive_cmd_guard.sh` | PreToolUse:Bash | Irreversible shell commands |
| `plan_status_validate.sh` | PostToolUse:Write\|Edit | A `Status:` outside the state machine |
| `docs_hygiene.sh`, `docs_drift_warn.sh` | PostToolUse:Write\|Edit | Docs contradicting the code |
| `function_complexity_warning.sh` | PostToolUse:Write\|Edit | Complexity growth in `*/src/*.py` |
| `todo_write_nudge.sh` | PostToolUse:Bash | Multi-step work running untracked |
| `task_complete_check.sh` | Stop | Finishing with work left open |

Five of these block (exit `2`); the four `PostToolUse:Write|Edit` advisors —
`function_complexity_warning`, `docs_hygiene`, `docs_drift_warn`, `todo_write_nudge` —
warn on stderr and exit `0`.

That split is deliberate and worth stating as a rule: **only checks that are decidable
are allowed to block.** "This content matches an AWS key regex" is decidable. "This
function is getting complex" is a judgement, and a guard that blocks on a judgement gets
disabled within a week — at which point it protects nothing. A warn-only hook that
survives is worth more than a blocking one that gets removed.

Verified live, both directions:

```
pip_guard      pip install requests  → exit 2  "Use uv, not pip."
pip_guard      uv add requests       → exit 0  (silent)
secrets_scan   AKIA…                 → exit 2  "AWS access key detected"
secrets_scan   x = 1                 → exit 0  (silent)
```

Testing only the block direction is how you ship a guard that blocks everything. Testing
only the allow direction is how you ship one that blocks nothing. `plan_status_validate`
has an end-to-end suite asserting both — **41 passed, 0 failed**
(`.claude/hooks/tests/test_plan_status_validate.sh`).

### The four parts, and which one is usually missing

| Part | Question | Here |
|---|---|---|
| Acceptance baseline | What does correct mean? | The plan doc's `## Plan`; the DoD table |
| Execution boundary | What can it touch? | `tools:` frontmatter; PreToolUse guards |
| Feedback signals | How does it learn it failed? | Hook exit 2 + reason; test output; findings |
| Rollback | How do we undo it? | Branch-only work; `dao`'s revert-on-test-failure |

**The most commonly missing part is rollback. The most commonly *faked* one is the
acceptance baseline** — a criterion vague enough that it cannot fail is not a baseline,
and "improve the code" passes every time.

Rollback here is structural: all work happens on a branch, agents never push, and `dao`
applies one fix at a time, running tests after each and reverting the hunk on failure.
Where no test harness exists it refuses to mutate code at all, and **it will not install a
test runner to manufacture its own gate.** A harness that can create its own acceptance
criterion has no acceptance criterion.

The gate is scoped precisely rather than absolutely: doc-sync still runs in a
harness-less repo, because no test suite was ever going to tell you whether the README
matches the tree. Withholding doc edits there would protect nothing while leaving the
docs wrong. **A gate should cover what it can actually verify, and no more** — an
over-broad gate is how safety rails become the thing people turn off.

---

## 4. Loop — five components, or it does not terminate

A loop is the model acting, observing the result, and acting again. Five components are
required, and dropping any one produces a specific failure:

| Component | Missing → |
|---|---|
| A **testable** goal | Never terminates |
| A tool set | Cannot affect anything |
| Context management | Dies of context exhaustion |
| Termination logic | Runs until the budget is gone |
| Error handling | First failure ends the run |

"Testable" is the load-bearing word. **"Improve the app" is an infinite loop** — not
because it is ambitious but because nothing can ever evaluate to done.

### The worked example

The ai-marketing-comms case study is a loop with all five present:

```
draft ──▶ validate ──┐
   ▲                 │
   └── repair ◀──────┤ invalid, budget left  (≤3 attempts)
   fallback ◀────────┤ invalid, budget spent
   stored  ◀─────────┘ valid
```

Goal: *every field satisfies the layout contract* — a pure function, so it is decidable.
Termination: valid, or three repairs, then deterministic truncation. **The loop cannot
fail to terminate and cannot terminate invalid.** The model's cooperation is an
optimisation, not a dependency.

That is the thesis in one diagram: counting characters is a job for code.

### The streaming variant

Everything above assumes a turn that ends. When audio flows both directions at once, no
protocol event marks the end of a turn — it is inferred from the stream, which makes turn
end a judgement rather than a signal, and the five components above do not describe the
shape. `.claude/skills/design-system/SKILL.md` §4b names the variant;
`.claude/specs/agent-voice.md` is the depth. The test is whether you can point at the
event that ends a turn. Nothing in this repo is duplex — ai-marketing-comms is request/response — so the
variant is documented here, not demonstrated.

### Four capability levels

1. **Agent loop** — act, observe, repeat
2. **Verification loop** — a checkable signal gates each iteration
3. **Event-driven** — something other than a human starts it
4. **Hill-climbing** — the loop improves its own criterion over runs

**Levels 1–3 automate work; level 4 automates improvement.** This repo runs at level 2:
every phase is gated on a checkable signal — hook exit codes, test results, the merge
verdict. Level 4 is not implemented, and the honest reason is that it needs an evaluation
set good enough to hill-climb against. Without one, a self-improving loop optimises a
proxy and drifts. **`.claude/specs/agent-eval.md` is the prerequisite; the eval set is the
gap.**

---

## 5. Graph — a cost, not a maturity level

> **A loop is a graph with one node and an edge back to itself.**

Graphs are not the advanced version of loops. They are a loop that paid for structure, and
the payment is real: more coordination, more failure modes, more places for state to
diverge. Five signals justify it:

| Signal | Present here? |
|---|---|
| Genuinely distinct specialties | **Yes** — quality vs. questions vs. contracts |
| Parallel fan-out + join | **Yes** — reporters run concurrently, orchestrator joins |
| Per-step model/tool variation | **Yes** — reporters are haiku, read-only |
| Auditable control flow | **Yes** — the verdict ladder is fixed, not judged |
| An overloaded verifier | **Yes** — this was the actual trigger |

**The most common "we need a graph" is really an overloaded verifier** — one step asked to
check correctness, security, style, and intent at once, doing all of them adequately and
none well. That was precisely the state of review here before this consolidation.

Before promoting anything to a node, apply the **true-dependency test**: *does the next
step actually read the previous step's output?* If not, it is not a pipeline stage — it is
a parallel branch, and sequencing it only costs latency.

### The review graph

In Claude Code the mapping is direct: **subagents are nodes, orchestration decisions are
edges, and hooks are deterministic edges** — the ones no model chooses to take.

```
                    ┌─────────────┐
                    │ context brief│   one diff, read once
                    └──────┬──────┘
            ┌──────────────┼──────────────┐      fan-out (concurrent)
            ▼              ▼              ▼
      ┌───────────┐  ┌───────────┐  ┌────────────┐
      │akira-scan │  │akira-wander│ │sanyi-review│   haiku, read-only
      │ defects   │  │ questions │  │ contracts  │
      └─────┬─────┘  └─────┬─────┘  └─────┬──────┘
            └──────────────┼──────────────┘      fan-in
                           ▼
                  ┌─────────────────┐
                  │ proto-review    │  dedupe → rank → verdict
                  └─────────────────┘
```

Three properties make this a graph rather than three prompts in a trenchcoat:

**The reporters never see each other's findings.** Corroboration is only meaningful if it
is independent. Two reporters that read each other's output produce agreement, which is
not evidence.

**None of them grades its own work.** The orchestrator is an edge, not a fourth node — it
merges and decides, it does not also report. A verifier that authored what it verifies is
not a verifier.

**The verdict is computed, not judged:**

```
1. any dispatch failure  → insufficient_context
2. any blocker           → request_changes
3. any important         → comment
4. otherwise             → approve
```

Rule 1 is first deliberately. A review that could not see part of the diff has not
approved it. **Reporter silence is a dispatch result, not a clean scan** — the failure
mode where a broken reporter reads as a passing review is the one this ordering exists to
kill.

### Evidence state ⊥ merge impact

Findings carry two independent axes: how well-established the claim is
(`verified` / `supported` / `hypothesis` / `question`) and what it means for shipping
(`blocker` / `important` / `suggestion` / `nit`).

They are orthogonal, and collapsing them loses real information. **A `hypothesis` can be a
`blocker`** — "this may silently drop writes under concurrency, and I could not fully
trace it" is exactly the finding you want to stop a merge, precisely *because* it is
unresolved.

---

## 6. HITL — a cut across all five layers

Human-in-the-loop is not a sixth layer. It appears at every level, and the design question
is always the same: **at which points is a human's judgement worth more than the latency
it costs?**

| Layer | Where the human enters |
|---|---|
| Prompt | Ambiguity that changes the work → ask, don't assume |
| Context | Approving the plan doc before execute reads it |
| Harness | Hook exit 2 — a hard stop needing a human decision |
| Loop | `dao` surfaces logic changes; it only auto-applies mechanical ones |
| Graph | The merge verdict is reported; submitting a review is authorised separately |

The standing rules are structural rather than advisory: **agents never push**, work is
always on a branch, and the review is read-only by default. The default is that a human
sees the diff before it becomes permanent.

`dao`'s triage is the sharpest version. Findings are sorted by **blast radius**, not by
confidence: mechanical fixes auto-apply behind a passing test suite, and anything
behavioural is surfaced for a human regardless of how certain the model is. Confidence is
the wrong axis — a confident wrong behavioural change is worse than an uncertain one,
because it is the one that gets applied.

---

## 7. This repo as the worked example

The consolidation that produced this setup was itself the pipeline's first real input, and
it found problems that only running it could find.

| | Before | After |
|---|---|---|
| Skills | 31 | **14** |
| Hooks | 17 + `lib.sh` | **9** + `lib.sh` |
| Specs | 26 | **12** |
| Agents | 5 | **4** |
| Symlinks to a private repo | 5 | **0** |
| Hooks actually wired | **0** — no `settings.json` | **9**, verified firing |

The single highest-value fix was a file that did not exist. Every hook in the repo was
dead — not broken, not misconfigured, simply never invoked, because nothing declared
them. Each one was a rule the operator believed was enforced.

That is the enforcement ladder's own failure mode, and it is worth stating plainly:
**documented-but-unwired counts as absent.** A hook that is not registered is a comment.
The rule "encode it in a hook" is necessary but not sufficient — the hook has to be
*reachable*, and the only way to know is to fire it and watch the exit code.

Other findings the consolidation surfaced, all now fixed:

- Hooks wrote logs to `$HOME/.claude/` — a repo-shipped hook writing outside the
  checkout. Now repo-local and gitignored.
- Review orchestration shelled out to `review-cli`, a binary in a private repo. Rewritten
  as native subagent dispatch — the graph above.
- `pyproject.toml` declared a build backend expecting `src/galactus/`, so `uv sync` failed
  and **no dev tooling could install at all** — including the `ruff` the hooks invoke.
- Three hook test suites tested hooks that no longer existed.

### What is deliberately not here

- **`ai-marketing-comms/` is preserved as delivered.** Its imports do not resolve against the current
  layout. Fixing it was out of scope; it is here to be read.
- **No level-4 loop.** It needs an eval set that does not exist yet.
- **No CI.** The hooks run locally; nothing enforces them on a server.
- **Skills are vendored on purpose.** `.claude/` duplicates a private global config so a
  clone works standalone. Canon lives upstream; see the *Vendoring exception* in
  [CLAUDE.md](CLAUDE.md).

An inventory of gaps with stated reasons is more useful than a claim of completeness. The
review pipeline's own rule applies to this document: **a requirement without a citation is
a gap.**
