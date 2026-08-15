---
name: review-defense
description: "Attack a plan before it ships. Dispatches independent adversaries — each given one distinct way the plan could fail — then merges their threats into a ranked list with mitigations and a go/no-go read. Same fan-out shape as the review reporters, aimed at a plan instead of a diff. Callable on any plan, spec, or design. Triggers on: 'war game this', 'how does this fail', 'red team the plan', 'attack this design', 'what breaks', '/review-defense'."
job: derisk
allowed-tools: Read Grep Glob Bash Write Agent
---

You are running a war game: attacking a plan from several independent angles and merging
what survives. This is the review graph's structure applied one layer earlier — nodes are
adversaries, the fan-in is yours, and the verdict is computed rather than felt.

**Read `decide-shared/references/claim-schema.md` before emitting anything.** Threats are
claims and use the same two axes.

**Read `.claude/specs/agent-safety.md §2`** — its adversarial subsection holds the rules
this skill runs against: the adversary as optimizer rather than noise, defenses as
selection pressure, Goodhart on your own metrics, and the bound on when adversarial
framing applies at all. If a finding here contradicts the spec, the spec wins and the
contradiction is itself worth reporting.

Honour that bound. **Name who benefits, what they can observe, and what they can change.**
A threat with none of the three is not a threat — it is ordinary uncertainty, belongs to
`/fog`, and reporting it here manufactures fog instead of locating it.

**Report only. Never edit the plan or the code.** The output is a threat list and a read;
acting on it is a human decision. This skill does not advance `Status:`.

## Input

`$ARGUMENTS` is a plan doc path, spec path, slug, or description. Read the file if one is
named. An empty or unreadable target is an **error, not a clean war game** — say so and
stop. "No threats found" from a broken read is indistinguishable from a robust plan.

Before dispatching, state the plan in **three sentences: what it builds, what it depends
on, what it assumes.** If you cannot, you do not understand it well enough to attack it —
ask, or run `/assumption-audit` first.

---

## Stage 1 — Choose the attack angles

Do **not** dispatch identical attackers. Redundancy finds the same threat N times;
diversity finds N different threats. This is the same reason the review subsystem gives
each `review-*` dimension a different remit — and keeps `wander` separate from `review`
— rather than running one defect scanner N times.

Standard angles — pick 3–5 that actually apply, and say which you dropped and why:

| Angle           | Attacks               | Asks                                                              |
| --------------- | --------------------- | ----------------------------------------------------------------- |
| **Dependency**  | What we don't control | What if the vendor/API/service/team is late, wrong, or gone?      |
| **Scale**       | Volume assumptions    | What breaks at 10×? What is O(n²) that looked O(n)?               |
| **Adversarial** | Hostile input         | What does a malicious or merely careless user do?                 |
| **Operational** | Run-time reality      | 3am failure — who is paged, what do they see, can they roll back? |
| **Sequencing**  | Plan order            | What if step 3 finishes but step 4 cannot start? Partial-state?   |
| **Human**       | The team              | What if the one person who understands this leaves mid-build?     |

Add a bespoke angle when the plan invites one. A plan touching money, PII, or irreversible
external effects gets an angle aimed at exactly that, always.

## Stage 2 — Dispatch, isolated

Dispatch one subagent per angle via the Agent tool, **concurrently, in a single message**.
Each gets the plan and _its own angle only_.

**Attackers must not see each other's output.** Corroboration only means something if it
is independent — two attackers reading each other produce agreement, and agreement is not
evidence. This is `review-shared`'s reporter-independence rule; it holds here for the same
reason.

Each attacker's brief:

```
You are attacking a plan from ONE angle: <angle>. Do not attack from any other.

Plan: <the plan text or path>

Return 2-5 concrete threats. For each:
  - The failure, as a sequence: what happens, then what, then what breaks
  - What in the plan permits it (quote or file:line)
  - Whether the plan already mitigates it (say so plainly if it does)
  - confidence + decision_impact per the claim schema

A threat is a *mechanism*, not a category. "It might not scale" is not a threat.
"The nightly job holds a table lock for the duration; at 10x rows that exceeds the
90s statement timeout and the job dies half-applied" is a threat.

If the plan genuinely defends well against your angle, say so and return fewer
threats. Do not manufacture threats to fill a quota — a padded list buries the
real ones. Name what you could not evaluate.
```

If a dispatch fails, that is a **result, not a silence**. Record it and carry it into the
verdict — see the ladder below.

## Stage 3 — Merge

You are the fan-in. Merge; do not attack — an orchestrator that adds its own threats has
graded its own work. If you notice something the attackers missed, dispatch another
attacker for it rather than adding it yourself.

1. **Dedupe by mechanism, not wording.** Two angles describing the same failure is
   corroboration: keep one entry, note both sources, raise `confidence`.
2. **Keep genuine disagreement visible.** If one attacker says the plan mitigates a threat
   and another says it does not, report both. Do not average them into a middle position
   that neither attacker holds.
3. **Drop the already-mitigated,** unless the mitigation rests on an assumption
   `/assumption-audit` would flag — in which case keep it, marked as conditional.
4. **Rank by `decision_impact`, then `confidence`.** Never confidence first; that buries
   the speculative/fatal cell that matters most.

## Stage 4 — Mitigations

For each surviving threat, one of four — and name which:

|             | Meaning                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| **Prevent** | Change the plan so it cannot happen                                         |
| **Detect**  | It can happen; we will know fast. Name the signal and who sees it           |
| **Recover** | It will happen; here is the path back. Name the rollback                    |
| **Accept**  | Cost of mitigation exceeds cost of the failure. State that trade explicitly |

`Accept` is a legitimate answer and must be _chosen_, not defaulted into. An unmitigated
threat with no decision attached is the one that surprises everyone later.

Prefer prevention where it is cheap, detection where prevention is expensive, and be
honest that recovery without a named rollback path is not recovery. Per the harness
layer: **rollback is the most commonly missing part.** If no threat's mitigation names a
rollback, say that out loud — it is a finding about the plan.

## Stage 5 — The read

Computed, in order — first match wins. Not judged:

| Condition                                                    | Read                                           |
| ------------------------------------------------------------ | ---------------------------------------------- |
| Any attacker failed to dispatch or returned unusably         | `incomplete` — the plan was not fully attacked |
| Any `fatal` threat with no `prevent` or `recover` mitigation | `redesign`                                     |
| Any `costly` threat unmitigated                              | `proceed-with-changes`                         |
| Otherwise                                                    | `proceed`                                      |

The first row is first for the same reason it is first in the review verdict ladder: **a
war game that could not attack part of the plan has not cleared it.** Attacker silence is
a dispatch result, not a clean bill of health.

Write to `.claude/docs/decisions/YYYY-MM-DD-<slug>-wargame.md` for a file target; return
in chat for a verbal one. Never write into the plan doc.

Close with the single threat you would fix first, and what the war game could not
evaluate — angles dropped, systems with no visibility, external behaviour unknowable from
here.

---

## Failure modes of this skill

- **Threat theatre.** Long lists of plausible-sounding categories with no mechanism.
  If a threat cannot be told as a sequence of events, it is not a threat.
- **Attacking the strawman.** Attacking a simpler plan than the one written, usually by
  skipping the mitigations already in it. Read the whole plan before dispatching.
- **Confidence-first ranking.** Puts the well-understood minor threats on top and buries
  the speculative fatal one. The whole point is the bottom-left cell.
- **Self-attacking.** The orchestrator adding threats during merge. Dispatch instead.
