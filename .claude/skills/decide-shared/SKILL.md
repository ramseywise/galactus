---
name: decide-shared
description: "Shared contracts for the frame/decide capability family — the Job verb taxonomy, the claim schema every capability emits, and the rule separating a capability from a pipeline stage. Preloaded by /assumption-audit and /war-game rather than invoked directly. Load it when writing a new capability skill or when deciding whether a new skill is a capability or a phase."
---

# decide-shared

The contracts the frame/decide capability skills write against. This skill holds no
procedure of its own — it exists so that `assumption-audit`, `war-game`, and any later
capability emit claims a human (or an orchestrating skill) can act on without re-reading
each skill's private conventions.

It is the `review-shared` of the decide family. Same role, different family.

| Reference | Load when |
|---|---|
| `references/job-verbs.md` | Adding a skill, or deciding which verb it declares |
| `references/claim-schema.md` | Emitting an assumption, a threat, or a comparison |

## Capability, not phase

The workflow skills are **positional**: `/workflow-research` runs before `/workflow-plan`
because plan reads research's output. That is the true-dependency test, and they pass it.

The capability skills are **situational**: you call `/assumption-audit` when a plan rests
on a guess, whether that is before research or after execute. Nothing sequences them.

The distinction is not stylistic. It decides three things:

| | Phase skill | Capability skill |
|---|---|---|
| Invoked by | Position in the pipeline | The situation |
| Writes to | The plan doc's own section | Its own artifact, or chat |
| Advances `Status:` | Yes | **Never** |

**A capability skill must not touch `Status:`.** The state machine
(`RESEARCH → … → COMPLETE`) tracks pipeline progress. A capability can run at any point in
that machine, including twice at the same state, so writing to `Status:` would make the
field mean two incompatible things.

This is enforced structurally rather than by instruction. `plan_status_validate.sh` scopes
itself to `/.claude/docs/plans/*.md` (line 10); capability artifacts land in
`.claude/docs/decisions/`, which is a different tree. A capability writing its own artifact
therefore *cannot* trip the state machine — not because it is told not to, but because it
is not writing where the state machine lives.

The residue is honest: the rule "don't write into the plan doc" is still an instruction,
and per the enforcement ladder that makes it the weakest thing in this file. A
`PreToolUse:Write` guard rejecting plan-doc writes from a capability skill would close it,
if it ever matters enough.

## Skills orchestrate agents — never the reverse

The section above sorts *skills* from *phases*. This one sorts **skills from agents**, which
is the question that comes up the moment a skill wants more than one perspective.

The direction is fixed, and every dispatch in this repo already runs it: `/workflow-review`
dispatches three reporters, `/fog` dispatches `fog-advisor`, `/war-game` dispatches one
attacker per angle. **No agent invokes a skill.** Agents may *preload* a shared contract
(`skills: [review-shared]`) as reference material, which is loading, not calling.

That asymmetry is load-bearing, not stylistic:

| | Skill | Agent |
|---|---|---|
| Context | Stateful — reads `$ARGUMENTS`, merges, ranks | Isolated — one lens, no sibling awareness |
| Sees | Everything, including other lenses' output | Only its own brief |
| Returns | A ranked artifact a human acts on | Claims, to be merged by its caller |
| Decides | What the user sees | Nothing |

Reverse it and the isolation collapses. Corroboration is evidence only when the corroborating
parties could not see each other; an agent that could call a skill could reach a sibling's
output, and agreement would stop meaning anything (`review-shared`'s reporter-independence
rule, one layer up).

### When a lens earns agenthood

A new perspective is **a section in a skill** by default. It becomes an agent only when it
needs one of two things — and the burden of proof is on the agent:

1. **Isolation** — the lens must be denied something the caller knows. `fog-advisor` is the
   worked example: withholding the author's justification requires a separate context, because
   a lens that has read the rationale grades the rationale.
2. **Parallelism** — N instances of the same shape run concurrently over different inputs
   (`plan-research-scout`, `/war-game`'s per-angle attackers).

Neither of those is "it feels like a distinct role." **A job title is not a lens.** Splitting
PM / designer / EM into three agents buys nothing, because they are not adversarial to each
other — they grade different axes, so their agreement was never evidence. Three lenses
converging on one verdict is one agent's job, or one skill's section.

Two failure modes this rule exists to prevent, in opposite directions:

- **The committee.** Five advisors dispatched on every design, producing five claim lists and
  a merge burden. Each lens sees too little to rank what it found, and the output is fog —
  findings everywhere, nothing prioritized. This is the overloaded verifier's mirror image:
  *under*-loaded reviewers.
- **The duplicate lens.** Building an agent for a perspective an existing skill already
  dispatches inline. Before adding one, grep what is already dispatched — `/war-game`'s angle
  table covers adversarial, scale, dependency, operational, sequencing, and human. A
  standing agent duplicating one of those violates that skill's own
  *"do not dispatch identical attackers."*

The check, in one line: **name what this agent is denied, or what it runs N of. If neither
answers, it is a section.**

## The Job verb

Every capability declares exactly one verb in its frontmatter as `job:`. The full
taxonomy with definitions is in `references/job-verbs.md`; the short form:

| Verb | The question it answers |
|---|---|
| `frame` | What problem are we actually solving? |
| `size` | How big is it — is it worth doing? |
| `decide` | Which option, and at what cost? |
| `design` | What is the shape of the thing? |
| `derisk` | How does this fail, and what would we do? |
| `report` | How does someone who was not here understand this? |
| `run` | Do the work |

One verb, not two. A skill that wants two verbs is two skills — that is precisely the
overloaded-verifier failure the review graph exists to fix, applied one layer up. A skill
covering both `frame` and `decide` will do both adequately and neither well.

`job:` is not a Claude Code frontmatter key; the runtime ignores it. It is a convention
for humans and for skills that read sibling skills. Keeping it in frontmatter rather than
prose means it can be grepped:

```bash
grep -h '^job:' .claude/skills/*/SKILL.md | sort | uniq -c
```

## What these skills are not

**No domain content.** This family ports a *taxonomy* and an *adversarial method*, not
consulting vocabulary. Market sizing, profit pools, board-readiness and competitor
war-rooms are domain content for a different domain; importing them here would be
cargo-culting the words. If a proposed capability skill has "market", "profit", or
"board" in its name, it does not belong in this repo.

The transferable claim is narrow and worth stating plainly: **we generate options and
build well; we do not quantify or defend.** These skills attack the second half.

## Output contract

Every capability skill in this family:

1. Emits claims matching `references/claim-schema.md`, including the two orthogonal axes
   (`confidence` and `decision_impact`) — collapsing them loses the same information the
   review family loses when it collapses evidence and merge impact.
2. **Reports; never edits code.** Same rule as the review reporters. A capability that
   fixes what it found is a capability that graded its own work.
3. Names its own blind spot before finishing. A skill that returns "no problems found"
   without saying what it could not see is indistinguishable from a skill that failed to
   run — the empty-review failure mode from `review-shared/references/context-brief.md`,
   which is the reason that rule exists there too.
4. Writes to `.claude/docs/decisions/YYYY-MM-DD-<slug>.md` when it produces a durable
   artifact, or returns in chat when it does not. It does not write to the plan doc.
