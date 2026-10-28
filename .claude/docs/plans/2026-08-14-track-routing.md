# Track routing for the prototyping pipeline
Date: 2026-08-14
Status: COMPLETE
Review: passed
Completed: 2026-08-14
From: EXECUTED
Track: agent

## Research

Source: `.claude/docs/specs/track-routing.md` (Status: DRAFT) plus direct codebase
inspection on 2026-08-14. The spec is the research artifact; this section records only
what inspection **added to or corrected in** it.

### Verified against code

| Spec claim | Verdict | Evidence |
|---|---|---|
| `detect_signals` returns independent booleans, "neither" reachable | Confirmed | `review/signals.py:195-199` — three independent keys, no exhaustiveness |
| `active_dimensions` returns a `skipped` map with reasons | Confirmed | `review/signals.py:220-251` |
| Hook parses `Status:` with a tolerant regex and a `has_field` helper | Confirmed | `.claude/hooks/plan_status_validate.sh:30`, `:55-56` |
| `detect-signals` is JSON in / JSON out, exit 0 | Confirmed | `review/cli.py:40-55` — `json.load(sys.stdin)` of a **bare list** |
| `ml-select` refuses to run before profiling | Confirmed | `.claude/skills/ml-select/SKILL.md:37-39` |
| `proto-*` skills never mention the ML skills | Confirmed | grep for `ml-select\|ml-transform\|leakage\|ML` over the three orchestrators returns zero |
| `proto-review` uses a named-dispatch protocol pattern | Confirmed | `.claude/skills/proto-review/SKILL.md:112-145` |

### Corrections to the spec

1. **There are 8 plan docs, not 6.** The spec's Verification table and its "6 existing
   plan docs" argument for hook tolerance both undercount. Every one of the 8 lacks a
   `Track:` line, so the tolerance argument holds *more* strongly, not less.

2. **The CLI input shape differs between subcommands.** `detect-signals` reads a **bare
   JSON list** (`review/cli.py:41`), but the spec's `detect-track` example pipes an
   **object** (`{"doc": ..., "files": [...]}`). These are not "the same shape". The
   object is correct for `detect-track` — it has two optional inputs — but Step 3 must
   state this divergence rather than inherit a false parity claim.

### Baseline (2026-08-14)

`uv run pytest -q` → **348 passed, 2 failed**. Both failures are
`review/tests/test_prefix_map.py` (`test_skill_set_matches_reporter_enum`,
`test_declared_prefixes_match_models_exactly`), caused by the untracked
`.claude/skills/review-performance/` skill on branch `GAL-3-leakage-unrun-not-clean` —
a dimension present in the skills dir but absent from `review/models.py`.

**Pre-existing and out of scope.** Confidence: High (the assertion diff names
`performance`/`PF` as the sole extra item). The green bar for this work is
*348 passed, same 2 failures* — not zero failures.

### Disconfirming evidence

- *Is the router genuinely one router?* Checked: `detect_track` adding to `signals.py`
  keeps one definition of "ML code" only if it **reuses** `_ML_IMPORT_PATTERNS` rather
  than paraphrasing them in prose patterns. The doc patterns are a second vocabulary in
  the same file — a real risk the spec does not name. Step 1 constrains them to prose
  that has no import equivalent.
- *Does the tie-break survive real docs?* Not yet knowable — it is why the corpus is
  hand-labelled in Step 2 before the protocols are written.

---

## Plan
Date: 2026-08-14
Based on: `## Research` above, and `.claude/docs/specs/track-routing.md`

### Goal

**Programme goal** (spans this increment and its follow-on): make `/ml-transform` and
`/ml-select` reachable by routing rather than by the operator remembering to type them —
an ML work item routes to `plan-ml`, which names both skills as ordered steps.

**This increment's goal**: build and prove the router that the programme goal depends on —
`detect_track`, its CLI surface, and the `Track:` doc format the hook enforces. Success
here is a router that classifies the real corpus correctly and **abstains honestly when it
cannot**. It does not yet unorphan anything; that is the follow-on, and this plan does not
claim credit for it.

Stated plainly because the distinction is easy to lose: shipping Steps 1–4 leaves the ML
skills exactly as orphaned as they are today. The value delivered is a proven, honest
router — not a routed pipeline.

### Open Questions

Resolved in the planning interview, 2026-08-14:

1. **What decision does this drive?** — *Unorphaning the ML skills.* The router is
   infrastructure in service of that; it is not the deliverable. **Programme** success is
   measured at `plan-ml`, not at `detect_track` — which is precisely why this increment,
   post-split, does not claim to have achieved it (see Goal).
2. **How far does this increment go?** — *Router + CLI + hook (Steps 1–4).* Originally
   scoped as router + all three phases; **split at the Step 4/5 seam during refinement
   (2026-08-14)** after the DoR gate found the increment did not fit one session. Steps
   5–8 (protocols, orchestrator rewiring, end-to-end) move to a follow-on plan doc — see
   "Follow-on increment" below. The router must be proven against real docs before any
   phase depends on it, which this plan's own step ordering already argued.
3. **Who writes `Track:`?** — *`/proto-research` is the canonical writer for new docs;
   `/proto-plan` backfills for the 8 legacy docs.* Two writers, explicit division.
4. **How is the spec's "execute-* may be worthless" warning honoured under (2)?** — *An
   evidence gate.* Follow-on Step C's done-when requires naming ≥3 concrete track-specific
   behaviours absent from the orchestrator; failing that, the step's deliverable is a
   written decision **not** to add them. The step can succeed by producing nothing.
5. **How do protocols load?** — *`Read .claude/skills/<protocol>/SKILL.md` at the routing
   step.* Declaring both tracks in `skills:` frontmatter would load both protocols on every
   invocation, which is the cost the router exists to avoid. Resolved against the repo's own
   contract (`decide-shared`, "Skills orchestrate agents — never the reverse"): a track
   protocol needs neither isolation nor parallelism, so it is **reference material, not an
   agent** — the same category as `review-shared`. All three orchestrators already hold
   `Read`, so this adds no tool permission and no frontmatter change.

   **Rejected alternatives**, recorded so they are not re-litigated:
   - *Agent dispatch* (the `proto-review` pattern) — `proto-execute/SKILL.md:8` says
     outright "Do not spawn subagents"; and per `decide-shared`, agenthood requires
     isolation or parallelism, neither of which applies.
   - *`skills:` frontmatter* — loads both tracks unconditionally.
   - *The `Skill` tool* — would require adding `Skill` to `allowed-tools` on all three
     orchestrators, granting the ability to invoke *any* skill in order to read one file.
6. **What is the router's test corpus?** — *The 8 real plan docs, hand-labelled, plus
   synthetic fixtures* for the branches real docs will not reliably supply (tie-break
   both-signals, zero-signal, declared-override).

Open for the reviewer:

7. **Does `Track:` belong in the doc or a sidecar?** Plan assumes the doc, per spec.
   Flagged because it touches the hook, and the hook is the strongest enforcement layer
   in the repo (`CLAUDE.md`: hook > linter > test > instruction).
8. **Should `/proto-review` cross-check `Track:` against diff signals?** Plan assumes
   **no** — spec calls it scope creep and the plan agrees.

### Approach

Extend `review/signals.py` with `detect_track`, a four-level precedence router
(`declared` → `doc` → `files` → `default`) that returns `track`, `source`, `confidence`,
and `reason` — the same audit rule that made `active_dimensions` return its `skipped`
map. Land the router and its honesty properties (Steps 1–2), expose it on the CLI
(Step 3), and gate the doc format with a hook check (Step 4).

The central design commitment: **the router abstains rather than guesses.** At low
confidence it withholds `track` entirely, so the abstention is enforced by the return
shape and a test, not by a sentence in a downstream skill. That is what makes the router
safe for the follow-on to build phases on — a router that quietly defaults is worse than
no router, because its callers cannot tell inference from a coin flip.

Steps are ordered so the router is proven against the real corpus (Step 2) before it is
exposed to any caller (Step 3) or written into the doc format (Step 4).

### Out of Scope

- **The phase work — protocols, orchestrator routing, end-to-end.** Split to the follow-on
  increment (2026-08-14). No file under `.claude/skills/` is created or modified by this
  plan; the only skill-adjacent change is the hook.
- **Execute repair loop** and **eval harness** — spec-deferred, independently valuable.
- **New state-machine edges** (`REFINED → PLANNED`, failure edges) — next increment.
- **Modifying `/ml-select` or `/ml-transform`.** They are invoked, not rewritten.
- **Vendored skills** — `mcp-builder`, `skill-creator`, `docs-check` are upstream copies
  per `CLAUDE.md`'s vendoring exception.
- **`/proto-review` consuming `Track:`** — Open Question 8, deliberately not built.
- **A third `general` track** — spec-rejected; tooling work routes to `agent`.
- **Fixing `test_prefix_map.py`.** Pre-existing failures from `review-performance` on
  this branch. Do not fix, do not fold in.
- **`review/models.py` and the reporter enum** — untouched; `detect_track` is additive.

### Steps

#### Step 1: `detect_track` in `review/signals.py`
Step 1 ✓ DONE — 2026-08-14

**Files**: `review/signals.py` (append after `detect_signals`, ~line 199; new pattern
lists beside `_ML_PATH_PATTERNS` at ~line 79)

**What**: Add the four-level precedence router. Reuse `_ML_IMPORT_PATTERNS` /
`_AGENT_IMPORT_PATTERNS` against fenced code blocks in the doc; add `_ML_DOC_PATTERNS` /
`_AGENT_DOC_PATTERNS` for prose only. Per the Research note, prose patterns must not
paraphrase an import that already has a pattern — that would be a second definition of
"ML code" in the same module.

Precedence: `declared` (a `Track:` line) → `doc` (keyword scan) → `files`
(`detect_signals`) → `default` (`agent`, low confidence). Tie-break at the `doc` and
`files` levels: **both signals true → `ml` wins** (asymmetric cost; `agent-uncertainty.md`
§asymmetric cost). Confidence is `low` when source is `default`, or when a doc scan hits
fewer than two *distinct* patterns.

**Low confidence is structurally unignorable.** When `confidence` is `low`, `track` is
`None` — not `agent`. A caller that reads only `track` gets nothing usable and cannot
silently consume a guess; the fallback track is reported separately as `default_track`,
which a caller must name explicitly to use. This is the abstention rule from
`agent-uncertainty.md` expressed in the return shape rather than in prose, because a rule
that lives only in a SKILL.md sentence is the weakest layer available
(`CLAUDE.md`: hook > linter > test > instruction) and this is the exact failure the
router exists to prevent.

```python
# low confidence: the track is withheld, not defaulted
{"track": None, "source": "default", "confidence": "low",
 "default_track": "agent", "reason": "no doc or file signal"}
```

**Snippet**:
```python
# before — signals.py ends at detect_injection

# after
_TRACKS = ("ml", "agent")

_ML_DOC_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"train[/ ]test split", r"target leakage", r"feature engineering",
    r"class imbalance", r"cross[- ]validation", r"baseline metric",
    r"\bAUC\b", r"\bRMSE\b", r"\btabular\b", r"\bdataframe\b",
)]
_AGENT_DOC_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"tool call", r"system prompt", r"context window", r"agent loop",
    r"\bretrieval\b", r"eval harness", r"\bMCP\b", r"LangGraph", r"\bADK\b",
    r"\bsubagent\b",
)]

_TRACK_RE = re.compile(r"^[ \t]*(?:\*\*)?Track(?:\*\*)?:[ \t]*(.*)$", re.MULTILINE)


def detect_track(doc_text=None, files=None, repo_root="."):
    """Classify a work item as the `ml` or `agent` track."""
    # 1. declared  2. doc  3. files  4. default
```
The `Track:` regex deliberately mirrors the hook's tolerant `Status:` form
(`plan_status_validate.sh:30`) — bold and leading-whitespace variants both occur in the
corpus, and two different notions of "a Track: line" between hook and router is exactly
the drift this step must not introduce.

**Test**: `uv run pytest review/tests/test_signals.py -v`

**Done when**: `detect_track` returns all four keys for every precedence level; `track` is
`None` whenever `confidence` is `low`, with `default_track` carrying the fallback;
`_TRACKS` is the single place a track name is enumerated; no existing function in
`signals.py` is modified.

---

#### Step 2: Router tests — real corpus plus synthetic edges
Step 2 ✓ DONE — 2026-08-14

**Files**: `review/tests/test_signals.py` (append); new fixtures under
`review/tests/fixtures/tracks/`

**What**: Hand-label all **8** docs in `.claude/docs/plans/` (not 6 — see Research
correction 1) and assert `detect_track` agrees. Add synthetic fixtures for the branches
real docs will not reliably supply: both-signals (tie-break → `ml`), zero-signal
(→ `default`, `confidence: low`), and a declared `Track:` line that **contradicts** the
doc's own keywords (→ `declared` wins).

The contradiction fixture is the one that matters: it is the only test proving human
override actually outranks inference rather than merely agreeing with it.

Add a regression assertion that `detect_signals` output is byte-identical for a fixed
file list before and after Step 1 — the spec's load-bearing row.

**Snippet**:
```python
def test_declared_overrides_contradicting_doc_keywords():
    doc = "Track: agent\n\nWe discuss train/test split and target leakage at length."
    got = detect_track(doc_text=doc)
    assert got["track"] == "agent"      # declared wins over ml-leaning prose
    assert got["source"] == "declared"

def test_both_signals_tie_breaks_to_ml():
    doc = "A system prompt drives the agent loop over a dataframe with class imbalance."
    assert detect_track(doc_text=doc)["track"] == "ml"

def test_no_signal_is_low_confidence_not_a_guess():
    got = detect_track(doc_text="Rename a variable in the build script.")
    assert got["source"] == "default"
    assert got["confidence"] == "low"

def test_low_confidence_withholds_the_track():
    """The abstention rule, enforced by shape rather than by instruction."""
    got = detect_track(doc_text="Rename a variable in the build script.")
    assert got["track"] is None          # a caller reading `track` cannot consume a guess
    assert got["default_track"] == "agent"

def test_no_result_ever_carries_a_track_at_low_confidence():
    """Sweep every fixture: low confidence and a non-None track must be unreachable."""
    for doc in _ALL_TRACK_FIXTURES:
        got = detect_track(doc_text=doc)
        assert not (got["confidence"] == "low" and got["track"] is not None)
```

**Test**: `uv run pytest review/tests/test_signals.py -v`

**Done when**: all 8 real docs classified with their hand label recorded in the test as a
comment naming the evidence; both tie-break directions covered; the low-confidence
abstention sweep green; `detect_signals` regression assertion green.

**Note on the corpus**: `.claude/docs/plans/` now holds **9** files — the 8 legacy docs
plus this plan doc itself. Label the 8; exclude this one by name rather than globbing the
directory, or the corpus silently grows every time a plan is written.

---

#### Step 3: `detect-track` CLI subcommand
Step 3 ✓ DONE — 2026-08-14

**Files**: `review/cli.py` (new `_cmd_detect_track` after `_cmd_detect_signals` ~line 55;
parser registration ~line 162); module docstring table at `:8-10`

**What**: Add the subcommand. **Input is a JSON object, not a bare list** — unlike
`detect-signals`, which reads a bare list (`cli.py:41`). Research correction 2: the spec
calls these "the same shape" and they are not. Same *contract* (JSON in, JSON out,
exit 0), different *payload*. Document the divergence in the docstring so the next reader
does not "fix" the inconsistency.

**Snippet**:
```python
# before — cli.py docstring
#     detect-signals    < ["path", ...]     active + skipped + injection hits

# after
#     detect-signals    < ["path", ...]     active + skipped + injection hits
#     detect-track      < {"doc": str, "files": [...]}   track + source + confidence

def _cmd_detect_track(args: argparse.Namespace) -> int:
    payload = json.load(sys.stdin)          # object, not a bare list
    result = detect_track(
        doc_text=payload.get("doc"),
        files=payload.get("files"),
        repo_root=args.repo_root,
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0
```

**Test**:
```bash
echo '{"doc":"target leakage and train/test split"}' | uv run python -m review.cli detect-track
```

**Done when**: emits all four keys, exits 0; a non-object payload fails with a clear
message rather than an `AttributeError` traceback; `detect-signals` output unchanged.

---

#### Step 4: `Track:` validation in the hook
Step 4 ✓ DONE — 2026-08-14

**Files**: `.claude/hooks/plan_status_validate.sh` (inside the existing `python3`
heredoc, after the `Status:` issue block ~line 52); `.claude/hooks/tests/test_plan_status_validate.sh`

**What**: Add a `Track:` check in the **same heredoc** — one hook, additional block, per
spec. Enum `{ml, agent}`, exactly one token, no suffix; same shape as the `Status:` check.

**Validate the value; never require the line.** All 8 existing docs lack it; blocking on
absence makes every one of them instantly unwritable. Absence is valid, and later phases
backfill.

**Snippet**:
```python
# after the existing Status suffix check
track_re = re.compile(r"^[ \t]*(?:\*\*)?Track(?:\*\*)?:[ \t]*(.*)$")
TRACKS = {"ml", "agent"}

track_value = None
for line in lines:
    m = track_re.match(line)
    if m:
        track_value = m.group(1).strip()
        break

if track_value is not None:          # absent is valid — legacy docs predate the line
    t = track_value.split()[0] if track_value.split() else ""
    if t not in TRACKS:
        issues.append(f"  '{t}' is not a valid track; expected one of: {', '.join(sorted(TRACKS))}")
    elif track_value[len(t):].strip():
        issues.append("  Track: must be exactly one token (ml | agent)")
```

**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh`

**Done when**: a doc with `Track: ml` exits 0; `Track: nonsense` exits 2 with a reason; a
doc with **no** `Track:` line exits 0; all pre-existing hook tests still pass.

Note: the hook's Python block exits **10**; the shell wrapper translates that to the
documented `exit 2` (`plan_status_validate.sh:69`, `:77`). Add the `Track:` block to the
same heredoc and the translation is inherited — do not add a second exit path.

---

#### Step 5: Verify this increment, end to end
Step 5 ✓ DONE — 2026-08-14

**Files**: none modified — verification only

**What**: Prove the router works and that nothing regressed. This increment's claim is
*a correct, honest router* — not a routed pipeline — so verification stops at the CLI
boundary.

**Snippet**:
```bash
uv run pytest -q                     # expect: 348 passed, 2 failed (test_prefix_map only)
bash .claude/hooks/tests/test_plan_status_validate.sh

# high-confidence ML doc -> ml
echo '{"doc":"target leakage, train/test split, baseline metric"}' \
  | uv run python -m review.cli detect-track

# no signal -> abstains: track is null, default_track carries the fallback
echo '{"doc":"Rename a variable in the build script."}' \
  | uv run python -m review.cli detect-track
```

**Done when**: the ML doc returns `{"track": "ml", ...}`; the zero-signal doc returns
`track: null` with `confidence: "low"` and `default_track: "agent"`; `detect-signals`
output is unchanged for a fixed file list; test failures are **exactly** the 2
pre-existing `test_prefix_map.py` ones — no more, no fewer.

---

### Test Plan

| Claim | Instrument | Step |
|---|---|---|
| Router classifies real docs correctly | Hand-labelled tests over the 8 legacy plan docs | 2 |
| Both tie-break directions covered | Synthetic both-signals + declared-contradiction fixtures | 2 |
| Router is honest about thin evidence | Zero-signal doc → `confidence: low`, not a guess | 2 |
| **Abstention cannot be ignored** | `track is None` at low confidence; sweep over all fixtures | 2 |
| Human override outranks inference | Declared `Track:` contradicting doc keywords | 2 |
| CLI contract holds | `detect-track` JSON round-trip, exit 0 | 3 |
| Hook accepts valid, rejects invalid | `test_plan_status_validate.sh` additions | 4 |
| Legacy docs stay writable | Write to a `Track:`-less doc exits 0 | 4 |
| No regression | `detect-signals` byte-identical; 348 passed / same 2 failed | 2, 5 |

The abstention row is this increment's load-bearing claim: it is what makes the router
safe to build phases on, and it is enforced by shape and test rather than by prose. The
regression row protects `detect_signals`, which `/proto-review` depends on daily.

**Not tested here**: ML reachability. That claim belongs to the follow-on (Step D) and
this increment does not assert it — see the Goal section.

### Risks & Rollback

| Risk | Mitigation |
|---|---|
| `detect_track` perturbs `detect_signals` | Additive only; explicit byte-identical regression assertion (Step 2) |
| Doc patterns become a second definition of "ML code" | Prose patterns constrained to phrases with no import equivalent (Step 1); imports reuse existing lists |
| Hook change makes the 8 legacy docs unwritable | Hook validates value, never requires line; explicit absence test (Step 4) |
| A caller consumes a low-confidence guess | `track` is `None` at low confidence; fallback only via the explicitly-named `default_track` (Step 1), with a fixture-wide sweep asserting the invariant (Step 2) |
| Tooling work misroutes to `agent` | Accepted per spec; `_TRACKS` is the only edit site if revisited |
| Router ships but is never adopted | Real risk of the split: Steps 1–4 deliver no user-visible change. Mitigated by the follow-on being planned, not merely intended — and by this plan refusing to claim the unorphaning as done |
| *(follow-on)* Protocol modules restate their orchestrators | Evidence gate on Steps B/C; permitted to produce nothing |
| *(follow-on)* Both protocols load per invocation | `Read` of exactly one protocol path; no `skills:` frontmatter declaration |

**Rollback**: Steps 1–3 are additive to `signals.py` / `cli.py` — revert the commits, and
`detect_signals` is untouched by construction. Step 4 is one block in one heredoc; removing
it restores the prior hook exactly. Any `Track:` lines already written remain harmless
after a full revert — they become ordinary prose in a doc the hook no longer inspects, and
nothing reads them, so there is no data migration in either direction.

### Open Questions

Resolved items are recorded at the top of this plan (dated 2026-08-14). Outstanding for
the reviewer: **Q7** (`Track:` in doc vs sidecar — touches the hook) and **Q8**
(`/proto-review` cross-checking `Track:` against diff signals — assumed out of scope).

Resolved during refinement, 2026-08-14:

9. **How do orchestrators load a protocol?** — `Read .claude/skills/<protocol>/SKILL.md`.
   Full reasoning and the three rejected alternatives are recorded under Q5 above. This
   was the blocking gap: the pre-split plan cited `proto-review` as precedent, but
   `proto-review` *dispatches agents* (`allowed-tools: … Agent`) rather than loading
   skills, so the cited mechanism did not exist in any orchestrator.

10. **Can `plan-ml` invoke the ML skills?** — **No.** Both are
    `disable-model-invocation: true`, so only the operator can invoke them. "Unorphaning"
    therefore means *named as ordered steps in the emitted plan*, and the follow-on's
    verification greps the plan doc rather than observing a call.

Deferred to the follow-on: whether `execute-ml` / `execute-agent` earn their existence
(Step C's evidence gate).


## Follow-on increment (not in scope here)

Split out during refinement, 2026-08-14, because Steps 1–4 and the phase work do not fit
one session and the phase work depends on the router being proven first. The design below
is preserved verbatim from the pre-split plan so it is not re-derived; it becomes its own
plan doc, gated separately.

**Prerequisite**: this plan complete, with the router green against the real corpus.

**Loading mechanism, resolved** (Open Question 5): orchestrators load a protocol with
`Read .claude/skills/<protocol>/SKILL.md` at the routing step. No frontmatter change, no
`Agent`, no `Skill` tool — all three orchestrators already hold `Read`.

**Known constraint to design around**: `/ml-transform` and `/ml-select` are both
`disable-model-invocation: true` (`ml-transform/SKILL.md:10`, `ml-select/SKILL.md:11`).
A skill therefore **cannot invoke them** — only the operator can. `plan-ml` unorphans them
by *naming them as ordered steps in the emitted plan*, which is a documentation edge, not
a call edge. The follow-on's done-when must assert on emitted plan text, not on execution.

---

#### Follow-on Step A: `plan-ml` and `plan-agent` protocols

**Files**: new `.claude/skills/plan-ml/SKILL.md`, `.claude/skills/plan-agent/SKILL.md`

**What**: The goal step. `plan-ml` names `/ml-transform` **then** `/ml-select` as ordered
plan steps — turning `ml-select`'s prose precondition (`ml-select/SKILL.md:37-39`,
"Refuses to select before the data has been profiled") into a routed edge. It also covers
target definition, split strategy, leakage-by-construction, and baseline metric, and
references `/ml-transform`'s outputs (`.claude/docs/column-plan.md`, the `ColumnPlan`)
from the plan doc's `## Plan` so `/proto-execute` and `/proto-review` can find them.

`plan-agent` covers the five layers, loop termination, tool contracts, and eval hooks.

Neither ML skill is modified.

**Snippet**:
```markdown
<!-- plan-ml/SKILL.md -->
## Ordered steps this protocol requires
1. `/ml-transform <frame>` — profile first; emits the ColumnPlan.
2. `/ml-select` — refuses to run before (1). Emits `.claude/docs/ml-config.md`.
Reference both outputs from `## Plan` so execute and review can resolve them.
```

**Test**: `grep -n "ml-transform" .claude/skills/plan-ml/SKILL.md` precedes
`grep -n "ml-select"`

**Done when**: both files exist; `plan-ml` names the two skills in the correct order; no
track-independent content (goal elicitation, doc I/O, `Status:` transitions) is duplicated
from the orchestrator.

---

#### Follow-on Step B: `proto-plan` and `proto-research` become orchestrators

**Files**: `.claude/skills/proto-plan/SKILL.md`, `.claude/skills/proto-research/SKILL.md`;
new `.claude/skills/research-ml/SKILL.md`, `.claude/skills/research-agent/SKILL.md`

**What**: Add a routing block to both orchestrators: read the `Track:` line, else call
`detect_track`, then **load exactly one** protocol by exact name — no `skills:` frontmatter
declaration (Open Question 5; declaring both loads both).

`confidence: low` → **ask the operator, do not proceed.** The router's abstention rule is
enforced at the phase, which is the only place it can be.

Writer division (Open Question 3): `/proto-research` writes `Track:` for new docs;
`/proto-plan` backfills when the line is absent.

Research protocols: `research-ml` (data availability, provenance, target feasibility,
prior baselines), `research-agent` (framework survey, tool inventory, prior-art loops,
context budget). Same evidence gate as Step C applies — if a protocol only restates the
orchestrator, record that and do not create it.

**Snippet**:
```markdown
## Track routing
1. Read `Track:` from the plan doc. If absent, run:
   `echo '{"doc": "<doc text>"}' | uv run python -m review.cli detect-track`
2. If `track` is `null` (low confidence) → **ask the operator.** Do not read
   `default_track` and proceed; the router withheld the track on purpose.
3. Write the resolved `Track:` line next to `Status:`.
4. Load exactly one protocol: `Read .claude/skills/plan-<track>/SKILL.md`.
```

**Integration point** (FA-007): this block is an edit to a named location in each
orchestrator, not free-floating prose. Insert it in `proto-plan/SKILL.md` immediately
before the step that reads `## Research` (`:59`), and at the head of `proto-research`'s
existing `## Routing` section — the track must resolve before either skill does
track-dependent work. **`/proto-plan` is the only backfiller**; `/proto-research` writes
`Track:` for new docs only. Two writers with one rule each, so no phase can race another.

**Test**: `bash .claude/hooks/tests/test_plan_status_validate.sh` (backfilled line
validates) plus the end-to-end grep in Step D.

**Done when**: both orchestrators route by exact name; neither declares protocols in
frontmatter; low-confidence asks rather than assumes; `Track:` backfill writes a
hook-valid line.

---

#### Follow-on Step C: `proto-execute` — evidence-gated

**Files**: `.claude/skills/proto-execute/SKILL.md`; possibly new
`.claude/skills/execute-ml/SKILL.md`, `.claude/skills/execute-agent/SKILL.md`

**What**: Add the same routing block to `proto-execute`. Then apply the evidence gate
(Open Question 4): the spec's candidate content is fit-order discipline, split-before-
transform, and metric-recorded-per-step for `-ml`; contract-first and harness-before-prompt
for `-agent`.

**Enumerate each candidate behaviour and check it against the orchestrator's existing
text.** If fewer than 3 survive as genuinely track-specific for a track, **do not create
that file** — write the decision and its reasoning into this plan doc's Open Questions
instead. A protocol that restates its orchestrator is worse than no protocol.

This step succeeds by producing nothing, if that is what the evidence says.

**Test**: `uv run pytest -q` (no regression) — this step is prose-only either way.

**Done when**: `proto-execute` routes; **and** either both protocol files exist with ≥3
verified track-specific behaviours each, or a dated written decision records why they
were not created.

---

#### Follow-on Step D: End-to-end verification of the programme goal

**Files**: none modified — verification only

**What**: Prove the actual goal, not its infrastructure. Take a real ML-track plan doc,
run it through `/proto-plan`, and confirm the chain end to end: `Track:` resolves to `ml`
→ `plan-ml` is read → the emitted plan names `/ml-transform` before `/ml-select`.

**The instrument is the emitted plan doc, not an observation.** Because both ML skills are
`disable-model-invocation: true`, "reachable" means *named as ordered steps in the written
plan* — which is a grep, not a judgement call:

```bash
DOC=.claude/docs/plans/<the-ml-doc>.md
grep -n "ml-transform" "$DOC"        # must appear
grep -n "ml-select"    "$DOC"        # must appear
# and in order:
test "$(grep -n 'ml-transform' "$DOC" | head -1 | cut -d: -f1)" \
  -lt "$(grep -n 'ml-select' "$DOC" | head -1 | cut -d: -f1)"   && echo ORDER_OK
```

**Done when**: `ORDER_OK` prints for a real ML-track doc that went through `/proto-plan`;
`Track: ml` is present and hook-valid; test failures are **exactly** the 2 pre-existing
`test_prefix_map.py` ones.

---
