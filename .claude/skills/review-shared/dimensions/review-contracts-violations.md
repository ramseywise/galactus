# Violations — taxonomy, severities, report template, `--fix` rules

> **Vendored** from Parallax `.claude/skills/sanyi/references/violations.md`.
> Parallax is read-only: fix upstream and re-vendor, never edit this copy in
> place. The 11 codes and their severities are mirrored by `_MERGE_IMPACT` in
> [review/validate.py](../../../../review/validate.py) — that table is what
> mechanically rejects a `BY-1` carried as a nit, so the two must not drift.

The enforcement vocabulary for the `contracts` review dimension. Codes and
severities here are authoritative.

## 1. Taxonomy

| Code | Meaning                                                                                        | Severity |
| ---- | ---------------------------------------------------------------------------------------------- | -------- |
| BY-1 | Direct modification of Buyi-guarded code                                                       | blocker  |
| BY-2 | Semantic downgrade: Buyi invariant made bypassable via flag/config/env                         | blocker  |
| BY-3 | Buyi evidence test deleted or weakened                                                         | blocker  |
| BY-4 | Declared Buyi invariant has prompt-only implementation, no deterministic code path             | blocker  |
| JY-1 | Jianyi budget exceeded (shape, graph, or other complexity carrier)                             | warning  |
| JY-2 | Anomalous single-PR growth within budget (e.g. +3 fields/edges in one PR)                      | warning  |
| JY-3 | Unbounded escape hatch: untyped catch-all (`dict`/`Any`/`**kwargs`) hides growth               | warning  |
| BN-1 | Bianyi value (prompt string / tunable) hardcoded outside its declared layer                    | info     |
| MG-1 | Unrecorded layer migration: a component's natural layer shifted with no `## Migrations` record | notice   |
| UN-1 | Changed file matches no contract entry (unassigned)                                            | notice   |
| UN-2 | Dangling contract: entry `paths` match no existing file                                        | notice   |

**BY-1 — direct modification.** Any edit inside a Buyi entry's `paths` —
including "harmless" refactors. The point is not that the edit is wrong but
that it must clear the highest review bar. Example: reordering the regexes in
a PII masker. Subsumed when BY-2 or BY-3 fires on the same entry — report only
the more specific code.

**BY-2 — semantic downgrade.** The invariant's code survives but becomes
conditional: a new flag, env var, or config key can now switch it off. This is
the most dangerous decay pattern because **every individual line looks
innocent** — a lint pass and a human skim both approve it; only comparing the
diff against the contract reveals that 不易 Buyi was silently demoted to 变易
Bianyi. Canonical example: `ENABLE_SAFETY_CHECK = os.environ.get(...)` wrapped
around a safety constraint "just for staging".

**BY-3 — evidence weakened.** The entry's `evidence` test is deleted, skipped,
or loosened until it no longer guards the contract. An invariant whose guard
test died is one PR away from BY-2. Example: removing
`test_no_bypass_flag`.

**BY-4 — prompt-only invariant.** The First Law of agent SANYI: LLMs are
probabilistic, so a constraint implemented only in a prompt is soft. A
declared invariant must have a deterministic code-layer implementation.
Canonical example: "never promise refunds" existing only as a sentence in a
system prompt — no output filter, no middleware guard. Extremely common, and
checked by no other tool.

**JY-1 — budget exceeded.** A Jianyi component grew past its declared
`budget`. The fix is redesign or explicit justification — never silent budget
inflation. Field/edge count is the _starting_ proxy, not the definition: the
real target is unjustified, unbounded complexity in any of the three carriers
(shape, escape hatches, control flow). Example: a state schema at 13 fields
against "≤ 12 fields", or a graph that adds a third retry cycle.

**JY-2 — anomalous growth.** Within budget, but a single PR adds enough (≥3
fields/params/edges) to deserve a justification even before the ceiling is hit.
Entropy arrives one sprint at a time.

**JY-3 — unbounded escape hatch.** A field count is easy to game: dump
everything into `metadata: dict`, `**kwargs`, or an `Any`, and the budget never
trips while the real complexity explodes. An untyped catch-all introduced or
widened in a Jianyi component is flagged here and treated as _unbounded_ growth,
not "one field". The fix is to type the thing — make the hidden fields visible
so they count. (This is why raw field count alone is a weak metric.)

**BN-1 — hardcoded changeable.** The reverse failure: a value the contract
says must be tunable without deploy appears as a literal in business logic —
an inline prompt string, a magic threshold. Mechanically fixable (see §4).

**MG-1 — unrecorded layer migration.** A diff (or audit) shows a component's
natural layer has shifted from its contract assignment, with no record in
`## Migrations`. Promotions (Bianyi → Buyi: a battle-tested prompt becomes
a hardened compliance rule) and justified demotions are _good_ — they just must
be logged with a rationale, so the contract evolves on purpose rather than
drifting. Severity is notice precisely because migration is healthy; the one
unhealthy direction — silently making an invariant bypassable — is the more
specific BY-2 blocker, not MG-1.

A common case: a diff that **remediates** a BY-4 (adds the deterministic code
guard a prompt-only invariant was missing) is exactly a Bianyi → Buyi
promotion — report it as MG-1 (record the migration + re-point the entry's
`paths` to where the guard now lives), not as a fresh violation. It is the
cure, not the disease.

**UN-1 — unassigned.** A changed file matches no entry: it has no change
contract, so the layer decision was never made. New components must be
assigned (or parked in Pending) before they calcify.

**UN-2 — dangling contract.** An entry's `paths` match nothing — usually
post-refactor drift. The contract points at a void; re-point or retire it.

## 2. Severity semantics

| Severity    | Meaning                                        | Behavior                                                                                                                 |
| ----------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **blocker** | The change-contract structure is being altered | Report + present decision options: **revert / redesign / amend the contract via architecture review**. Never auto-fixed. |
| **warning** | Entropy contract under pressure                | Report + bookkeeping (update `current` stamps).                                                                          |
| **info**    | Changeable made rigid                          | Report.                                                                                                                  |
| **notice**  | Contract hygiene signal                        | Report only.                                                                                                             |

These map to `merge_impact` through `_MERGE_IMPACT` in `review/validate.py`:
blocker → `blocker`, warning → `important`, info → `suggestion`, notice → `nit`.
A finding whose `merge_impact` disagrees with its `violation_code` is rejected
mechanically — the code fixes the impact, and a reporter does not get to argue
a BY-2 down to a nit.

## 3. Finding shape

The standalone SANYI report template does not apply here. The `contracts`
dimension emits findings in the canonical schema like every other dimension —
`CT-` prefix, `severity.violation_code` set to the code above, and the contract
entry named in `basis`. The orchestrator writes the report.

Put in `claim.observation` what the diff does *in contract terms* ("the PII
masker's invariant is now gated on `DISABLE_MASKING`"), and in
`claim.failure_scenario` what that permits. For blockers, name the decision
options — revert, redesign, or amend the contract via architecture review — in
the recommendation rather than choosing one.

## 4. Never auto-fix

**Why BY-\* and JY-\* are never auto-fixed.** A Buyi "fix" is a human decision —
revert the change, redesign the approach, or amend the contract itself through
architecture review. Auto-fixing a safety constraint is itself a Buyi
violation: **the enforcer must not rewrite the verdict.** A Jianyi fix
requires redesign or a justification, not field deletion — a tool that deletes
schema fields to satisfy a budget is a disaster generator. Only BN-1 has a
mechanical, unique-direction, behavior-preserving fix (move the value to its
declared layer), and even that is out of scope for a review dimension: this
skill is read-only and reports, it does not edit.

Naming caveat worth reporting when you see it: when the covering contract entry
is symbol-scoped (e.g. `backend/config.py#ESCALATION_*`), a relocated constant's
name must match that glob — otherwise the move takes the value out of contract
coverage.

## 5. Scope notes — deferred and rejected

Kept here so they do not silently re-enter.

- **Deferred (needs scripts):** deterministic Flow Budget metrics — counting
  graph fan-out, depth, and cycles. The control-flow _principle_ is live (a graph
  is a Jianyi component; new edges/loops need justification), but reliable
  counting exceeds pure-LLM measurement. Until then, control flow is judged
  qualitatively.
- **Rejected (2026-06-13): Buyi sub-tiers** (critical / important / operational
  Buyi). They are an invariant-inflation vector and fight Buyi scarcity.
  Severity is already encoded by layer; the consequence test (security / legal /
  financial / trust failure) is the admission gate. A "lesser Buyi" is almost
  always a mis-split — the tunable part is Bianyi, the must-hold part is Buyi.
