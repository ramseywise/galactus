# Job verbs

A verb taxonomy for capability skills. Every skill in the frame/decide family declares
exactly one verb as `job:` in its frontmatter.

## Why a taxonomy at all

The workflow skills are named for their **position** (`research` → `plan` → `execute` →
`review`). That works because they genuinely sequence. Naming a capability skill by
position would be a lie — `/assumption-audit` is useful before research and after execute,
and a name implying otherwise would suppress the second use.

So capabilities are named for the **job**, and the verb makes the coverage map greppable
rather than remembered. The value is not the label on any one skill; it is being able to
ask "what covers `size`?" and get an honest answer, including "nothing."

## The seven verbs

| Verb | Question | Fails when |
|---|---|---|
| `frame` | What problem are we actually solving? | The stated problem is a solution in disguise |
| `size` | How big is it — is it worth doing? | Effort and value are both unquantified |
| `decide` | Which option, and at what cost? | Options were generated but never compared |
| `design` | What is the shape of the thing? | The design answers a problem nobody framed |
| `derisk` | How does this fail, and what would we do? | Failure modes are listed but not attacked |
| `report` | How does someone absent understand this? | The reasoning lived only in a transcript |
| `run` | Do the work | — |

## Coverage in this repo

Honest as of the last audit. `frame` and `derisk` were the two half-covered verbs this
family was created to close.

| Verb | Covered by | State |
|---|---|---|
| `frame` | `/design-sprint` (HMW deconstruction), `/assumption-audit`, `/fog` | Covered |
| `size` | — | **Gap.** Nothing quantifies effort or value |
| `decide` | `/design-sprint` generates options | **Half.** Options are never costed or compared |
| `design` | `/design-initiative`, `/design-system`, `/design-prototype` | Covered |
| `derisk` | `/design-initiative` (failure modes), `/war-game` | Covered |
| `report` | — | **Gap.** Nothing packages a decision for someone absent |
| `run` | `/workflow-*` | Covered |

### Three skills share `frame` — why that is not a collision

The verb names what a skill's output changes, not what it looks at. All three change which
problem gets worked on; they find it in different places:

| Skill | Finds | Answers |
|---|---|---|
| `/design-sprint` | The problem behind the stated problem | What are we solving? |
| `/assumption-audit` | The guesses the plan rests on | What would make this wrong? |
| `/fog` | What the system does not know about itself | Where does not-knowing become an answer? |

They are separable by input: a sprint runs before anything exists, an audit runs on a plan,
and `/fog` runs on a design or on code that already ships. Two of them firing on the same
target would be redundant; that has not happened, because their inputs rarely coincide.

The two remaining gaps are recorded rather than filled, for the same reason the design
doc records its own: **an inventory of gaps with stated reasons is more useful than a
claim of completeness.** `size` and `report` are open on purpose — neither had a clearly
transferable method behind it, and inventing one to fill a table cell is how a taxonomy
becomes decoration.

## Choosing the verb for a new skill

Ask what the skill's output *changes*. Not what it looks at — what it changes:

- Changes which problem gets worked on → `frame`
- Changes whether it gets worked on → `size`
- Changes which of several approaches gets built → `decide`
- Changes the shape of what gets built → `design`
- Changes what safeguards exist → `derisk`
- Changes who understands the decision → `report`

If two answers fit, the skill is two skills. Split it before writing it — the split is
cheap now and expensive after the skill has users.
