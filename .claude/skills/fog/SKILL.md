---
name: fog
description: "Interrogate a design or built system for how it handles not-knowing. Maps what is known and unknown, finds the sites where 'I don't know' silently becomes an answer, checks which decisions are irreversible, and dispatches an independent advisor for the worst-plausible-case pass. Callable on a spec, a plan, or code that already ships. Triggers on: 'how does this fail', 'what are we not seeing', 'fog of war', 'stress this design', 'what happens when it does not know', '/fog'."
job: frame
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash Write Agent
---

You are running a fog pass. The output is a ranked list of the places where this system
does not know something and does not say so.

**Read `decide-shared/references/claim-schema.md` before emitting anything.** Claims use
its two orthogonal axes. **Read `.claude/specs/agent-uncertainty.md`** — that spec holds
the rules; this skill runs the questions those rules answer. If a finding here contradicts
the spec, the spec wins and the contradiction is itself worth reporting.

**Report only. Never edit code, never edit the target doc.** This skill finds the fog; a
human decides what to do about it. It does not advance `Status:`.

## Input

`$ARGUMENTS` is a spec path, a plan doc path, a directory of code, a slug, or a
description in the user's words. If it names a file or directory, read it. If it names
nothing, run against the current session's working design — and if there isn't one, ask
what to interrogate rather than inventing a target.

An empty or unreadable target is an **error, not a clean pass.** Say so and stop. This
skill exists to find the place where nothing-found is reported as all-clear; producing
that failure itself would be the joke landing badly.

---

## Stage 1 — Map the quadrants (inline)

Four boxes. Fill all four before assessing anything — the fourth is the one that matters
and it only appears once the first three are on the page.

| | **You know it** | **You don't know it** |
|---|---|---|
| **You know you know/don't** | Known-knowns — facts you can cite | Known-unknowns — questions you have named |
| **You don't know you know/don't** | **Unknown-knowns** — the system holds it but cannot retrieve it | Unknown-unknowns — what surprises you |

**Unknown-knowns are the highest-yield box and the one everyone skips.** The information
exists — in a spec, a hook, a prior decision, a config file — and the system does not
reach it. That is a retrieval failure, not a knowledge gap, and it is fixable in a way the
fourth box is not. This repo has a worked example: nine hooks were dead for weeks while
every session behaved as though they were enforcing.

For the target, ask specifically:

- What does this design assert as fact, and where is that fact actually stored?
- What questions has it named but not answered? (Named unknowns are cheap; go looking for
  unnamed ones.)
- What does the repo already know that this design does not consult — a spec it should
  have read, a hook it duplicates, a decision already made elsewhere?
- What class of surprise would this design have no way to detect? Do not try to name the
  surprise; name the **absence of the detector.**

Unknown-unknowns are not enumerable. Do not pretend otherwise. What you can report is
whether the system has any mechanism that would notice one — a canary, an alert, a
divergence check, a human in the loop. If it has none, that is the finding, stated once.

## Stage 2 — Find the collapse sites (inline)

**Where does "I don't know" get converted into an answer?**

This is the core pass and the highest-yield defect class in this repo's history. Trace
every path where uncertainty enters and check whether it survives to the output or gets
silently resolved.

The shape to look for is: *component receives nothing → returns something that reads as a
result.*

Grep for it, don't just reason about it. Useful probes against the target:

```bash
# handlers that swallow and continue
grep -rn "except.*:\s*pass\|except.*:\s*continue" <target>
# defaults that hide absence
grep -rn "\.get(.*,\s*\[\]\|\.get(.*,\s*{}\|or \[\]\|or {}" <target>
# empty-collection returns
grep -rn "return \[\]\|return {}\|return None" <target>
```

Each hit is a candidate, not a finding. Promote it only when you can answer: **is the
empty result distinguishable from the successful-but-nothing-found result, by the caller?**
If the caller cannot tell, it is a collapse site.

Distinguish carefully between four things — the difference is the whole point:

| Case | Correct behaviour |
|---|---|
| Ran, found nothing, and nothing is the true answer | Report the empty result as a result |
| Ran, could not tell | **Abstain** — say so explicitly, do not answer |
| Never ran (dispatch failed, input missing, tool errored) | **Error** — never an empty result |
| Ran, answered from nothing | The defect |

A system that returns the same value for rows two, three, and four cannot be debugged and
cannot be trusted. Report each collapse site with what the caller *believes* happened
versus what happened.

## Stage 3 — Check reversibility (inline)

**Which decisions here are irreversible, and can any of them be staged?**

For each decision the design makes, place it:

| Decision | Reversible? | Staging available |
|---|---|---|
| … | yes / no / in principle only | soft-delete before purge, canary before rollout, propose before execute, flag before default |

The rule: **prefer the option that keeps the most options open, at equal expected value.**
When two paths are close, take the one you can walk back.

Two things to be strict about:

- "We could roll it back" is not a rollback. Name the branch, the flag, the retention
  window, the backup. Reversibility is a property of the harness, not a promise in a
  prompt.
- Irreversible-and-unstaged is a finding at `fatal` impact regardless of how confident
  anyone is that it will go fine. That is the asymmetry: confidence does not shrink blast
  radius.

## Stage 4 — Dispatch the advisor (isolated)

Now dispatch `fog-advisor` for the worst-plausible-case pass.

**Give it the design. Do not give it your reasoning about the design, the findings from
stages 1–3, or the author's justification.** An advisor who reads the justification grades
the justification. The independence is the entire value of the dispatch — the same
argument that keeps reporters isolated from each other in the review family. If you brief
it on what you already found, its agreement stops being evidence.

What to pass:

- The design itself (file contents, paths, or a factual description with no advocacy).
- The scope: which parts are in play.
- Nothing else.

The advisor runs four passes — empty-input, p99, reversibility, determinism — and returns
claims with the `FA` prefix. Its reversibility and empty-input passes deliberately overlap
stages 2 and 3. **That overlap is the check, not waste.** Where it independently finds
what you found, confidence goes up. Where it finds something you missed, you missed it.
Where you found something it did not, say so rather than quietly dropping yours.

If the dispatch fails or returns nothing, that is `dispatch failure` — an error, not a
clean advisor pass. Say so in the output and do not report a verdict as though four passes
ran.

## Stage 5 — Concentrate the complexity (inline)

**Which probabilistic steps could be deterministic?**

Attack the strongest form of the design: assume every model call works as intended, then
ask whether it needed to be a model call at all.

- A step a database query, regex, schema validation, or character count could answer
  should not be a model call. Deterministic components are faster, cheaper, testable, and
  cannot be confidently wrong.
- Chained probabilistic steps compound: four chained 95% steps is 81%, and the failure is
  silent because each step emits plausible output.
- The shape to push toward is a narrow probabilistic core with deterministic components on
  both sides — `classifier → retrieval → rerank → LLM`, with the model reasoning over
  evidence rather than supplying it.

The governing rule, and the one to check last: **never let the generative component
silently become the source of truth.** Truth belongs in the deterministic systems. If the
design has a path where the model's output is stored, cited, or acted on as fact without
an intervening check, that is the finding — and it usually outranks everything else in
this pass.

## Stage 6 — Merge and rank

Combine your inline findings with the advisor's. Dedupe by **mechanism**, not by wording —
two findings describing the same collapse site from different angles are one finding with
two witnesses, and the corroboration is worth recording.

Rank by `decision_impact` first, `confidence` second. That order is deliberate: a
`speculative` finding at `fatal` impact outranks a `certain` finding at `cosmetic`, because
expected cost is probability × consequence and the consequence term has the larger range.
The cell to look at hardest is speculative × fatal — low confidence, high blast radius,
and therefore the highest-value thing to spend a cheap check on.

Then answer the last question, which nothing above answers:

**How would this system learn it was wrong — and would anything change if it did?**

A system with no path from wrongness to correction is not uncertain, it is fixed. If there
is no eval, no feedback signal, no alert, no review that could revise a decision, say so
plainly as a standalone finding. It is usually the most important one and the least likely
to be raised by any of the earlier stages, all of which assume something is watching.

## Output

Ranked claims per `claim-schema.md`. Ids are `FOG-001`, `FOG-002`, … for findings you
made inline; the advisor's `FA-NNN` ids are **retained as issued**, not renumbered into
your sequence. A merged finding keeps both ids and names both witnesses — that is how a
reader tells one finding with two independent witnesses from two findings that happen to
rhyme.

Then three required lines:

1. **The fog** — one sentence on what this system does not know about itself.
2. **The one to fix first** — a single named finding.
3. **What this pass could not see** — parts of the design too abstract to attack, code you
   could not read, runtime behaviour you had no visibility into, and whether the advisor
   dispatch succeeded.

The third line is not a disclaimer. A fog pass that reports no blind spots has demonstrated
the exact failure it was run to find.

## Failure modes of this skill

- **Reporting a clean pass on an unreadable target.** Covered above; it is listed twice
  because it is the one that would matter most.
- **Briefing the advisor.** Passing stage 1–3 findings into the dispatch destroys the
  independence and turns corroboration into an echo. Resist the urge to be helpful.
- **Enumerating unknown-unknowns.** Anything you can name is a known-unknown. The
  deliverable for that box is the presence or absence of a detector.
- **Ranking by likelihood.** The whole asymmetric-cost argument collapses if you sort by
  confidence. Impact first, always.
- **Producing fog about the fog.** If every finding is `speculative`, the pass has generated
  uncertainty rather than located it. Ground each claim in a specific file, line, or named
  step, or drop it.
