# Agent Uncertainty — Conventions

**Durable question:** What does this system do when it does not know — and how does it tell the difference between not knowing and being confidently wrong?

*Tooling-agnostic. Organised around decision-making-under-uncertainty (fog of war, minimax, OODA, least commitment); every rule below is stated in engineering terms. The strategic frame names the shape — it is not the argument.*

**This is our convention, not an industry standard.** The quadrant model and the collapse rule are local inventions. The underlying ideas are borrowed from military decision theory, where they are old and well tested; their application to agent design here is ours.

**Scope, and what this spec does not duplicate.** Reliability owns *what happens when a call fails* (`agent-reliability.md`). Safety owns *what a hostile input can reach* (`agent-safety.md`). Eval owns *how we measure whether a change helped* (`agent-eval.md`). This spec owns the layer above all three: **what the system believes, how sure it is, and what it does when the answer is "not sure."** A retry is reliability. Deciding whether the thing is even worth retrying — and what to say when it is not — is here.

---

## 0. The one-sentence version

> **Good engineering is largely the art of making decisions under uncertainty while preserving the ability to recover from being wrong.**

Two clauses, and the second is the one systems skip. Most designs address uncertainty by trying to *reduce* it — more retrieval, more validation, more context. That is the cheap half. The expensive half is designing for the case where reduction failed and you proceeded anyway.

**The governing rule for this repo: never let the generative component silently become the source of truth.** Truth lives in deterministic systems — the database, the test suite, the file on disk, the character count. The model reasons *over* evidence; it does not *become* the evidence. Every rule below is a consequence of that one.

---

## 1. The four quadrants

Classify what a system does and does not know. The value is not the taxonomy — it is that three of the four quadrants have standard engineering responses, and the fourth does not.

| Quadrant | What it is | Response |
|---|---|---|
| **Known knowns** | Documented APIs, observed traffic, the schema | Encode as invariants; assert them |
| **Known unknowns** | "We don't know peak load yet" | Name it, measure it, or bound it explicitly |
| **Unknown knowns** | The information exists here and nobody surfaced it | **Retrieval and discovery — the quadrant with no owner** |
| **Unknown unknowns** | Failures nobody anticipated | Cannot be enumerated; only survived. Design for recovery, not prediction |

**Unknown knowns is the quadrant that bites hardest, because it looks like ignorance and is actually retrieval failure.** The fact was in the repo, the trace, the spec, or an earlier session — and the system acted without it. Three concrete forms in this codebase:

- A convention documented in `.claude/specs/` that the agent did not read before writing code.
- A decision recorded in a prior plan doc, re-litigated because the session did not load it.
- A hook that exists and is not wired — the rule was *known*, and the system did not act on it. This repo shipped exactly that: nine hooks, zero registered. **Documented-but-unwired counts as absent.**

The engineering response is not "know more." It is: **make the known things reachable at the moment of decision, and make unreachability loud.** A spec nobody loads and a spec that does not exist are the same spec.

For unknown unknowns the response is different in kind. You cannot enumerate them, so every mitigation is generic: bounded blast radius, reversibility, observability good enough to reconstruct what happened. **Design for recovery, not for prediction** — the whole point of the quadrant is that prediction has already failed.

---

## 2. Do not collapse "I don't know" into an answer

The central failure of a generative system: it converts absent knowledge into fluent output, and fluency reads as confidence.

**The collapse rule:** a component that cannot distinguish *"no evidence"* from *"evidence says no"* will report both as an answer. Preserve the distinction structurally, not by asking the model to be careful.

Wrong shape, and it is the default shape:

```
retrieve → generate
```

Right shape:

```
retrieve → evaluate evidence → answer OR abstain
```

The middle step is a gate, not a suggestion. `agent-safety.md`'s Layer 3 (retrieval quality gate, skip generation on poor evidence) is this rule's runtime implementation — this spec states *why* it exists.

**This repo's worked instance.** From `review-shared/references/context-brief.md`: a brief with an empty diff is an error, not an empty review — because a reporter handed nothing returns no findings, and no findings is indistinguishable from a clean review. That is the collapse in its purest form: **absence rendering as approval.** The verdict ladder puts `insufficient_context` *first* for exactly this reason, ahead of every severity check.

Generalised: **any pathway where empty input produces the same output as a successful negative result is a collapse site.** Find them by asking, for each component, *"what does this return when it was given nothing?"* — and if the answer matches what it returns on success, that is the bug, regardless of how well it performs on real input.

Three distinctions worth keeping separate, because they license different actions:

| State | Means | Action |
|---|---|---|
| **Confident answer** | Evidence supports it | Proceed |
| **Uncertain answer** | Evidence is thin or conflicting | Proceed, but mark it and preserve the mark downstream |
| **Abstention** | No adequate evidence | Do not answer. Escalate or return the gap |
| **Dispatch failure** | The component did not run | **Never** the same as abstention. It is an error |

The last row is the one systems get wrong. An abstention is a *result*; a failure is an *absence of result*. Merging them means a broken component reads as a cautious one.

**Uncertainty must survive the handoff.** A confidence marker that a downstream step drops has not preserved uncertainty — it has laundered it. If step A abstains and step B treats the empty response as "nothing to report," the system is confidently wrong at the boundary. Uncertainty is only preserved if it is *typed* — a field the next component must handle, not prose it may ignore.

---

## 3. Asymmetric cost — optimise for consequences, not probabilities

> Expected value = probability × consequence.

A 99.9% accurate component is excellent or unacceptable depending entirely on the 0.1%. Accuracy alone is not a specification; it becomes one only when paired with the cost of the failure.

| System | Wrong output costs | Implied requirement |
|---|---|---|
| Recommendation | Annoyance | Accuracy is enough |
| Marketing copy over a character limit | A broken layout, caught by code | Deterministic check, not a better model |
| Financial transaction | Money moved wrongly | Confirmation, idempotency, audit trail |
| Irreversible external action | Cannot be undone | Human approval before execution |

**Same model accuracy, different architectures.** This is why "the model is 99% accurate" is never a sufficient answer to "is this design sound."

**Rank by blast radius, not by confidence.** This repo already implements the rule in `akira dao`: mechanical fixes auto-apply behind a passing test suite; anything behavioural is surfaced to a human *regardless of how certain the model is*. Confidence is the wrong sort key, and it fails in a specific direction — **a confident wrong behavioural change is worse than an uncertain one, because it is the one that gets applied.**

The same inversion appears in `decide-shared/references/claim-schema.md`: rank by `decision_impact` first, `confidence` second. Ranking by confidence buries the speculative-but-fatal claim, which is the one worth the most.

**Worst-plausible-case, not average-case.** Ask the p99 question, not the mean:

- Not "what is the average latency" → "what happens at p99, and what does the caller do while it waits?"
- Not "what happens if retrieval works" → "what happens if retrieval returns confident garbage?"
- Not "what if the model is correct" → "what does the system do when it is confidently wrong?"

The last is the load-bearing one for any LLM component. **Guardrails go around the happy path, not inside it** — a check the model performs on itself is the generator grading its own output, which `agent-eval.md` rules out for the same reason.

---

## 4. Least commitment — preserve the ability to be wrong

> Do not make irreversible decisions before you have enough information.

Where a decision can be staged, stage it. The pattern is identical across domains:

| Instead of | Stage it |
|---|---|
| Permanent delete | Soft delete → retention window → purge |
| Deploy everywhere | Canary → observe → expand |
| Commit to one model | Abstraction boundary → evaluate → switch |
| Agent executes | Propose → validate → approve → execute |
| Rewrite in place | Branch → review → merge |

The last two are this repo's standing structure, and they are least-commitment rules rather than politeness: **agents never push, work is always on a branch, review is read-only by default.** A human sees the diff before it becomes permanent — not because the model is untrusted in general, but because that is the cheapest available point of reversal.

**Reversibility is a property of the harness, not a promise in a prompt.** "The agent will be careful" is not a rollback. Name the mechanism: the branch, the retention window, the revert-on-test-failure in `dao`, the flag that turns it off.

**Rollback is the most commonly missing harness part** (`agent-architecture.md`, harness section). When a design has no answer to "how do we undo this," it does not have a safety gap to be patched later — it has an architecture that assumes correctness. Those are different problems, and only the first one is fixable by adding a check.

**The cost of optionality is real.** Staging a decision costs latency, code, and sometimes a worse outcome than committing early would have produced. Least commitment says *defer irreversible decisions*, not *defer all decisions* — an agent that never commits to anything is its own failure mode. The test: **is this decision cheap to reverse?** If yes, make it and move on. Deliberation over a reversible choice is waste.

---

## 5. Concentrate complexity where it buys something

Do not spend intelligence everywhere. Ask where intelligence is actually needed, and use the cheapest component that satisfies the requirement.

```
LLM → LLM → LLM → LLM          every step probabilistic, errors compound
classifier → retrieval → rerank → LLM    each step the cheapest that works
```

**Every LLM call must justify itself against the deterministic alternative.** If a database query, a regex, a schema validation, or a character count answers the question, that wins — it is faster, cheaper, testable, and it cannot be confidently wrong.

This is `galactus`'s own thesis, stated in `CLAUDE.md`: *counting characters is a job for code; the model's job is content.* The ml6 case study is the worked example — the layout contract is a pure function, so it is decidable, so the loop cannot terminate invalid. **The model's cooperation is an optimisation, not a dependency.**

The corollary matters as much: probabilistic steps compose badly. Four chained 95% steps is 81%, and the failure is silent because each step produces plausible output. **Chain deterministic steps; isolate probabilistic ones.**

---

## 6. Close the loop — Observe, Orient, Decide, Act

A system that observes but never adapts is running three quarters of a loop.

| Stage | Question | Here |
|---|---|---|
| **Observe** | What actually happened? | Hooks, test results, traces, review findings |
| **Orient** | What does it mean? | Finding merge, evidence state, verdict ladder |
| **Decide** | What do we do? | Merge read, triage tiering |
| **Act** | Do it | Fixes applied, plan changed |

**The stage that closes the loop is the edge from Act back to Observe** — and it is the one this repo does not have. Findings are emitted, acted on, and the run ends. Nothing about the *next* review is different because of what this one found. A rule that fires false positives every week keeps firing; a reporter that never finds anything keeps being dispatched.

Stated honestly: **this repo runs at capability level 2** (every phase gated on a checkable signal) and does not implement level 4 (the loop improves its own criterion). `agent-eval.md` names the prerequisite — an eval set good enough to hill-climb against. Without one, a self-improving loop optimises a proxy and drifts, which is worse than not adapting at all.

So the convention is deliberately conservative:

- **Levels 1–3 automate work; level 4 automates improvement.** Do not build level 4 without an eval set. An adaptive system with no ground truth adapts toward whatever it can measure.
- **Where the loop cannot close automatically, close it manually and say so.** A finding that recurs across three reviews is a signal about the *rule*, not the code. Today a human notices that; nothing in the harness does.
- **Faster feedback beats a better initial strategy.** Prefer the design that learns it was wrong in an hour over the one that is more likely to be right and takes a week to find out. This is why `dao` runs tests after *each* fix rather than at the end — the loop is tightened deliberately, so a bad hunk is attributed to itself rather than to the batch.

**A known gap stated is worth more than a gap silently carried.** The Act→Observe edge is absent by choice, and the choice is revisitable the moment `agent-eval.md`'s eval set exists.

---

## 7. Applying this spec

This spec states rules a built system obeys. **Interrogating a design against them is a separate job with a separate artifact** — `/fog` runs the questions; this file holds the answers they are graded against.

That split is deliberate and worth naming, because the first draft of this spec got it wrong. A section of questions inside a convention ref fires only when a human remembers to read the ref before designing — the weakest layer on the enforcement ladder. Moving them into a callable skill does not make them deterministic, but it makes them *invokable*, which is one rung up.

| You want to | Use |
|---|---|
| Know the rule | This spec |
| Interrogate a design for how it handles not-knowing | `/fog` |
| Attack a plan for how it fails | `/war-game` |
| Find the load-bearing guesses | `/assumption-audit` |

The three skills lean on this spec and on `decide-shared`; none of them restates it.

### Where these rules are enforced

This spec cuts across the layer refs, which means its rules are *stated* here and *obeyed* there. A rule with no enforcing section is documentation. The map, so a reader arriving from a layer ref can find the rule and a reader here can find the teeth:

| Rule here | Enforced in |
|---|---|
| Abstain rather than collapse (§2) | `agent-eval.md §9` — graders must be able to abstain; `agent-observability.md §8` — abstentions are recorded events |
| Asymmetric cost (§3) | `agent-safety.md §5` — confirm gates sit where consequence concentrates |
| Least commitment (§4) | `agent-architecture.md` — checkpointing and staged rollout; `agent-reliability.md §3-4` — idempotency and resumability |
| Concentrate complexity (§5) | `agent-architecture.md` — deterministic components around a narrow probabilistic core |
| Close the loop (§6) | `agent-observability.md §8` — would a trace show the system being wrong? |
| Unknown-unknowns are survived, not enumerated (§1) | `agent-reliability.md §1` — coupling and interactive complexity, the two variables you can actually lower |

Adversarial not-knowing is deliberately **not** here. When another actor observes your defense and adapts, the failure distribution is chosen rather than sampled, and the rules differ — that lives in `agent-safety.md §2`. The test for which spec applies: if you can name who benefits, what they observe, and what they can change, it is adversarial; otherwise it is ordinary uncertainty and belongs here.

---

## Sources

- Local synthesis (2026-08-08). No single upstream source; the strategic vocabulary is standard military-decision-theory material (Boyd's OODA loop, minimax, fog of war, the Rumsfeld quadrant) applied to agent design.
- `agent-safety.md` §1 Layer 3 (retrieval quality gate) — the runtime form of §2's abstention rule.
- `agent-eval.md` — the eval-set prerequisite that blocks level-4 adaptation in §6.
- `agent-architecture.md` — harness parts; rollback as the commonly missing one.
- `review-shared/references/context-brief.md` — the empty-diff-is-an-error rule, §2's worked instance.
- `decide-shared/references/claim-schema.md` — impact-major/confidence-minor ranking, §3.
- `akira/references/dao.md` — blast-radius triage, §3; per-fix test loop, §6.
