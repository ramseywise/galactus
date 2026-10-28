# User Test Protocol: Discovery Pipeline

**Purpose:** Validate that DSSG volunteers can walk from "I have an idea" to a
completed Project Profile using `/project-discovery`, and that the profile feeds
cleanly into `/scope-poc`.

**Participants:** 2-3 DSSG volunteers who have NOT used the template before.
Ideally: 1 with engineering background, 1 without, 1 with a real nonprofit project idea.

**Facilitator:** Someone familiar with the skill pipeline (ideally not the author).

**Duration:** 30 minutes per participant (20 min active, 10 min debrief).

---

## Setup

1. Fresh workspace with only the template skills available (no pre-existing DESIGN.md or profile)
2. Claude Code session with `/project-discovery` accessible
3. Friction log template open (see below)
4. Screen recording if participant consents

## Scenarios

### Scripted scenarios (participants 1-2)

Give each participant one of these prompts and ask them to run `/project-discovery`:

**Scenario 1 (Information Retrieval):**
> "You're working with a community health clinic. Their case managers spend hours
> looking up which benefit programs each client qualifies for — Medicaid, SNAP, housing
> assistance, childcare vouchers. The rules are in a 300-page policy manual that
> changes quarterly. New case managers take months to get good at this."

**Scenario 2 (Workflow Automation):**
> "You're helping a youth mentoring program. They pair 50 mentors with 50 mentees.
> After each weekly meeting, mentors are supposed to log notes and the coordinator
> is supposed to check that everyone actually met. Right now it's all manual — a
> spreadsheet that's always out of date, follow-up emails that don't get sent."

### Real scenario (participant 3)

Ask: "Do you have a real nonprofit you're working with or thinking about helping?
Tell me about their biggest pain point."

Use their actual situation. This is the most valuable test — a scripted scenario
can't surface confusion that only arises from real-world ambiguity.

---

## Observation Guide

During the session, the facilitator notes:

### What to watch for

| Signal | What it means | Severity |
|--------|--------------|----------|
| Participant says "what do you mean?" | Jargon or unclear prompt | Medium |
| Participant says "I don't know" to a question | Question assumes expertise they don't have | High |
| Participant gives a long, unfocused answer | Question is too broad; needs narrowing | Low |
| Participant picks the wrong archetype | Archetype descriptions aren't clear enough | High |
| Participant hesitates at "must-demonstrate" | Needs more prompting / examples | Medium |
| Participant's final profile has blank sections | Skill didn't elicit the information | High |
| Participant says "this is what I thought" at confirm | Working as intended | N/A (positive) |
| Profile's copier hints don't match their intent | Mapping logic is wrong | High |

### When to intervene

- **Do intervene** if the participant is stuck for > 60 seconds (note what they're stuck on, then help)
- **Do intervene** if they're about to answer a question with clearly wrong information (note the confusion, then correct)
- **Don't intervene** if they're thinking or reading — silence is fine
- **Don't intervene** if they pick a "wrong" answer — that's a test finding, not a mistake

---

## Success Criteria

### Must-pass (any failure = fix before shipping)

1. Participant produces a valid Project Profile (all sections non-empty) without asking
   "what does that mean?" more than **twice** across the entire session
2. The profile's archetype matches the facilitator's independent assessment of the
   scenario (facilitator writes their expected archetype BEFORE the session)
3. Profile → `/scope-poc` handoff works: scope-poc finds the profile and correctly
   pre-fills at least 3 of the 5 mapped fields
4. Total time from "tell me about the nonprofit" to confirmed profile: **< 20 minutes**

### Should-pass (fix if failing, but don't block)

5. Participant doesn't need to read the reference cards themselves (the skill presents
   the relevant information conversationally)
6. Copier hints in the profile are all valid (no made-up parameters or values)
7. Participant says the profile "sounds right" on first presentation (no major corrections)

### Nice-to-have

8. Participant volunteers positive feedback ("this is helpful", "I didn't know that was an option")
9. Participant's real scenario (if used) produces a profile that the facilitator agrees is reasonable

---

## Friction Log Template

One entry per friction point observed:

```markdown
## Friction Log — [participant name/number] — [date]

### Entry [N]
- **Step:** [which step of /project-discovery was active]
- **What happened:** [participant's action or statement, verbatim if possible]
- **What they expected:** [what they seemed to be trying to do]
- **Severity:** [blocks-progress | confusing | cosmetic]
- **Suggested fix:** [how the skill/card should change]

### Entry [N+1]
...
```

Severity definitions:
- **blocks-progress:** Participant cannot continue without facilitator help
- **confusing:** Participant is uncertain but continues (may produce wrong output)
- **cosmetic:** Participant notices something odd but it doesn't affect outcome

---

## Post-Test Debrief Questions

Ask each participant after completing the session:

1. "What was the hardest question to answer? Why?"
2. "Did the archetype options make sense? Would you have described your project differently?"
3. "Looking at the final profile — does it capture what you were trying to say?"
4. "What would have helped you get to this point faster?"
5. "Would you use this again for your next project? Why or why not?"

Record answers verbatim. These are the design insights that automated testing can't surface.

---

## Post-Test Action Items

After all participants complete:

1. **Sort friction entries by severity** (blocks-progress first)
2. **Group by skill step** (which step has the most friction?)
3. **Identify patterns** (did multiple participants struggle with the same thing?)
4. **Assign fixes:** Each blocks-progress item gets a fix committed before the next test round
5. **Re-test:** Run `/design-dryrun` after fixes to confirm no regression

### Fix priority

| Severity | Action | Timeline |
|----------|--------|----------|
| blocks-progress | Fix immediately, re-test | Before next volunteer session |
| confusing | Fix in next sprint | Within 1 week |
| cosmetic | Add to backlog | When convenient |

---

## Reporting

Summarize findings in `.claude/docs/test-protocols/discovery-pipeline-results.md`:

```markdown
# Discovery Pipeline Test Results — [date]

## Participants
- P1: [background], [scenario used]
- P2: [background], [scenario used]
- P3: [background], [scenario used]

## Summary
- Success criteria met: [X/9]
- Total friction entries: [N] (blocks: [n], confusing: [n], cosmetic: [n])
- Average time to profile: [N minutes]

## Top findings
1. [Most impactful finding + fix]
2. [Second finding + fix]
3. [Third finding + fix]

## Fixes applied
- [fix 1: file + change]
- [fix 2: file + change]

## Open questions for next round
- [question that surfaced but wasn't resolved]
```
