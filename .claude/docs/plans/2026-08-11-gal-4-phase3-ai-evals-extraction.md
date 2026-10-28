# GAL-4 Phase 3 — Generalize the AI eval harness (`ai/evals/` extraction)
Date: 2026-08-11
Status: COMPLETE
From: EXECUTED
Review: passed
Completed: 2026-08-15

<!-- 2026-08-15: walked REFINED -> COMPLETE in one sitting, with `GALACTUS_BACKFILL=1` set for
     the duration. The four edges are reconciliation, not traversal — the work they describe
     happened over days in a different repo, and the ledger says so rather than claiming four
     same-minute transitions.

     This plan was written in galactus and executed in `ai-project-template`, per the prefix
     rule: prefix names the repo being changed, not the repo holding the issue. The state
     machine has no token for "executed elsewhere", so COMPLETE is the honest terminal state
     and this note is where the elsewhere is recorded.

     `Review: passed` rests on the merge, not on a `/proto-review` run in this repo. Shipped
     on AIT `main` as `{{ py_project_root }}/{{ eval_root }}/generation/` (the harness plus
     `registry_projection.py`), alongside Phase 1's `experiments/` and unit tests under
     `tests/unit/experiments/` — commits `11ee5ea..6581042`, closing
     ramseywise/ai-project-template#68. Both directories verified present on that repo's main
     before this walk. -->

## Research

### Summary
The existing template eval tree (`{{ eval_root }}/`, ~40 files) **does not duplicate**
what Phase 3 needs — it is a *grading* suite (score recorded rows against golden
answers, with LLM judges) and Phase 3 needs a *generation-under-contract* harness
(drive a producer, measure repair convergence and fallback). They share the words
"eval", "metrics", "reports" and almost nothing structural: the existing tree has no
producer loop, no repair concept, no first-pass-vs-final distinction, and crucially
**no dry-run adapter** — its judges degrade to `None` (skipped) where the galactus
harness degrades to a *scripted deterministic provider* that still exercises the clean,
repair, and fallback paths. That single difference is the whole reason
`evals/run.py --dry-run` returns real numbers with no key and the template's
`eval-grade` returns "n/a". Phase 3 should therefore **extend** `{{ eval_root }}/`
with new sibling sub-packages rather than create a second parallel `ai/evals/` root.
The regression baseline was captured successfully and is recorded verbatim below.

### Scope
**Investigated:** the full 531-line `ai-marketing-comms/evals/run.py` and every
galactus module it imports (`generate.py`, `models.py`, `llm/port.py`,
`layout/contract.py`, `layout/validator.py`); the entire
`ai-project-template/template/_scaffold/{{ py_project_root }}/{{ eval_root }}/` tree
(graders/, metrics/, pipelines/, reports/, models.py, targets.yaml); the
`ml/workflows/classification.py` shape that Phase 3 is the analogue of;
`copier.yaml`'s root-variable block (lines 306–390, 1112–1130); the template's test
harness (`make test_render`); and the GAL-4 Phase 1 plan's Step 6 eval adapter seam.

**Explicitly out of scope:** Phases 1, 2, 4 of issue #4; W&B; any change to
`ai-marketing-comms` *behavior*; the retrieval/interaction grading pipelines
themselves; building a second AI poc (the second consumer is proven by a test
fixture, not by scaffolding a real poc).

### Findings

**F1 — `{{ eval_root }}/` and Phase 3's harness are different eval *kinds*. They
extend, not duplicate. (High — this is the load-bearing finding.)**

The existing suite has two pipelines, both of which grade **already-produced
artifacts**:

| | Existing `{{ eval_root }}/` | Phase 3 harness (`evals/run.py`) |
|---|---|---|
| Input | recorded rows — `data/evals/interactions_sample.jsonl`, `data/raw_corpus/golden_qa.jsonl` | `cases.jsonl` — *briefs*, not outputs |
| Who produces the output? | the system, earlier, out of band | the harness itself, during the run |
| Loop | none — one grade per row | generate → validate → repair × N → fallback |
| Unit of measurement | per-row correctness vs a golden answer | per-case *process* facts (first-pass validity, repair count, fallback used) |
| Failure model | judge unavailable → metric `None`, skipped (`graders/judges/base.py:48-63`) | scripted adapter → full metrics, no key needed |
| Entry points | `evals.pipelines.run` (retrieval), `evals.pipelines.grade` (interactions) | `evals/run.py --dry-run` |
| Gate | `targets.yaml` thresholds, `--gate` (`pipelines/run.py:127-146`) | exit 1 iff `contract_valid_rate != 100.0` (`run.py:527`) |

The existing tree's own `models.py:1-7` docstring already distinguishes two eval kinds
("retrieval golden-QA" vs "interaction evals") and namespaces them separately. Phase 3's
harness is a **third** kind by the same logic — generation-under-contract — and belongs
as a third sibling under the same root, not as a competing root. The `graders/`,
`metrics/`, `pipelines/`, `reports/` four-way split is a shape it can join.

**F2 — The template has no dry-run adapter anywhere, and its degradation contract is the
opposite of galactus's. (High)**

`grep` for `dry.run|dry_run|Scripted|scripted|fake|stub` across the whole scaffold
returns only test-local `monkeypatch` fakes
(`tests/unit/agents/test_generate.py.jinja:56`, `:86`, …) and unrelated type-stub
comments in `ml/`. No production-path scripted provider exists. The template's stated
contract is graceful *skipping*: `judges_available()` returns False without a key
(`graders/judges/base.py:25-32`), `grade()` returns `None` on any failure (`:61-63`),
and `_check_targets` prints "n/a (not measured this run — skipped)"
(`pipelines/run.py:137-142`). That is a defensible contract for a judge, and a fatal
one for a harness whose whole claim is "runnable with no key and no spend": a run that
skips everything reports nothing.

`ScriptedEvalLLM` (`run.py:150-243`) is the opposite design and is *deliberately* not a
stub — its docstring says so ("Not a stub returning one canned draft"). It reads the
requested limits out of the template, overshoots on `difficulty == "hard"` cases,
tightens on repair, and never tightens for `stubborn` cases. The `STRESS_PROFILES` table
(`:246-259`) assigns each hard case a *different* breach class so the run exercises
word-count repair, color-reference repair, and budget exhaustion separately. This is
what makes the baseline non-degenerate — and `tests/test_evals.py:420`
(`test_dry_run_spread_is_not_degenerate`) already asserts exactly that property.
**This is the asset with the highest extraction value and the highest extraction risk.**

**F3 — `run.py` splits cleanly at roughly 60/40 case-agnostic to case-specific. (High)**

Line-by-line coupling map:

| Region | Lines | Galactus imports used | Verdict |
|---|---|---|---|
| Grounding (`is_grounded`, `_distinctive_tokens`, `_STOPWORDS`, `_TOKEN_RE`, `MIN_GROUNDING_OVERLAP`) | 47–96, 354–375 | `Fact` — **only for `f.text`** | **Fully generalizable** — needs `Sequence[str]`, not `Fact` |
| `CaseResult` | 284–297 | none | **Fully generalizable** as-is |
| `compute_metrics` / `_rate` | 383–412 | none | **Fully generalizable** as-is |
| `summarize_table` / `format_report` | 420–480 | none (reads `CaseResult` fields) | **Fully generalizable** as-is |
| `main` argparse + exit code | 488–531 | `Settings`, `configure_structlog`, `AnthropicAdapter` | **Shape generalizable**, provider wiring is case-specific |
| `EvalCase` / `load_cases` | 104–142 | `Fact` (typed field) | **Adaptable** — `Fact` is the only tie; duplicate-id check is generic |
| `ScriptedEvalLLM` | 150–243 | `LayoutTemplate` (`.fields`, `.name`, `.kind`, `.max_words`, `.min_words`, `.max_chars`) | **Adaptable** — needs a field-spec protocol |
| `_scripted_llm` / `STRESS_PROFILES` | 246–276 | via `LayoutTemplate` | **Case-specific** (the profile *names* are galactus case ids) but the *mechanism* is generic |
| `run_case` / `run_all` | 299–346 | `load_template_cached`, `generate_collateral`, `is_valid`, `PipelineState` | **Case-specific glue** — this is the seam |

The genuinely case-specific core is small: `run_case` needs (a) something that turns a
case into a contract, (b) something that runs a producer against it, (c) something that
validates. Those are three callables. Everything upstream and downstream of them is
already generic Python with no galactus types.

**F4 — The four metrics generalize only because `generate_collateral` mutates state.
(High — the subtle dependency.)**

`contract_pass_rate` is measured on the *first* generation, before repair. It is not
reconstructable from the final result — `models.py:150-159` says so explicitly: "a run
with `repair_attempts == 0` could equally be a clean first pass or a run given no repair
budget." `run_case` reads `state.first_pass_valid` and `state.repair_attempts` off the
mutated `PipelineState` (`run.py:329-330`), and `used_fallback` off the return tuple
(`:312`).

Consequence for extraction: the extracted harness cannot just call
`producer(case) -> output`. The producer contract must **return the process facts**, not
just the artifact. The natural extraction is a small result type —
`(output, first_pass_valid, repair_attempts, used_fallback)` — which is precisely a
generalized `PipelineState` projection. Any extraction that types the producer as
`Callable[[Case], Output]` silently loses two of the four metrics.

**F5 — Issue #4's "`ai/evals/`" does not name a real directory; `ai_source_root` renders
to `src`. (High)**

`copier.yaml:378-381`: `ai_source_root` default is `src` (never asked, `when: false`);
`ml_source_root` is `ml` (`:383-386`); `eval_root` is `evals` (`:1115-1118`). So the ML
analogue lives at `ml/workflows/` and a literal reading of "`ai/evals/`" would render as
`src/evals/` — a *third* eval location, inside the AI source root, alongside the existing
sibling `evals/`. copier.yaml:322-326 is explicit that this is wrong by design: evals are
"a SIBLING of both source roots, not nested: evals import ACROSS roots … a consumer of
every root rather than a member of one." Issue #4's phrasing is shorthand for "the AI
analogue of `ml/workflows/`", not a path specification.

There is also a guard: `eval_allowed_dirs` (`copier.yaml:1119-1122`) is
`graders metrics pipelines reports utils`, enforced by `enable_structure_guard`
(`:1127-1130`) for `project_type in ['eval_suite', 'rag']`. **A new top-level directory
under `{{ eval_root }}/` with a name outside that list will trip the structure guard on
guarded project types.** Any placement decision must either use an allowed dir name or
extend `eval_allowed_dirs`.

**F6 — `ml/workflows/classification.py` is the right shape to copy, and it is now
committed. (High)**

The prompt flagged it as uncommitted on `AIT-67-ml-workflows-classification`. Re-verified
2026-08-11: `git -C ~/workspace/ai-project-template status --porcelain` is **empty** and
`git log --oneline -1` is `0f8b2cf feat: implement classification workflow and reporting
structure` on that branch. Phase 1's F8 blocker ("wait for #67 to land") is **discharged
for Phase 3** — the branch is committed, though not yet merged to main.

The shape worth copying: one `run_*()` entry point taking a frame plus keyword config and
returning a single result dataclass (`RunResult`, `classification.py:90-153`) that
carries not only metrics but *decisions* — `skipped: dict[str, str]` ("Model name → why
it did not run. Carried so a missing model in the report is a recorded decision rather
than a silent omission.", `:102-104`) and an assertable invariant
(`assert_no_transform_outside_pipeline`, `:138-153`). The AI analogue: an eval run result
that carries `errors` *and their reasons* — which `run.py` already half-does via
`CaseResult.error` (`:296`).

One anti-pattern to **not** copy: `ModelRun.headline` (`:84-87`) hardcodes PR-AUC as a
property, which Phase 1's F2 identified as the thing the registry must route around. The
extracted AI harness must declare its headline metric as data, not as a property.

**F7 — The regression baseline runs clean, read-only, with no network. (High)**

`cd ~/workspace/galactus && uv run python ai-marketing-comms/evals/run.py --dry-run --json`
— exit code **0**, no network, no `ANTHROPIC_API_KEY`. Structlog JSON spans go to stderr;
the metrics JSON is the last object on stdout. Verbatim:

```json
{
  "cases": 12,
  "contract_pass_rate": 58.3,
  "repair_convergence": 0.36,
  "fallback_rate": 8.3,
  "grounding_rate": 91.7,
  "contract_valid_rate": 100.0,
  "errors": 0,
  "total_llm_calls": 19
}
```

Corroborating facts from the same run, useful as secondary assertions: 12 cases in
`cases.jsonl`; 5 cases emit repair spans (`overlong-headline-pressure`,
`verbose-column-pressure`, `color-reference-pressure`, `quote-and-cta-pressure` at 1
attempt each; `no-facts-at-all` at 3 attempts then fallback); violation counts per repair
are 2, 4, 1, 4, and 12/12/12 respectively. **This is the regression contract.** All eight
numbers must be byte-identical post-extraction.

**F8 — `tests/test_evals.py` is a 428-line, 33-test safety net that mostly survives
extraction. (High)**

Named tests include `test_dry_run_exits_zero_without_a_credential` (`:390`),
`test_dry_run_json_output_is_parseable` (`:405`), `test_dry_run_spread_is_not_degenerate`
(`:420`), `test_contract_pass_rate_is_first_pass_not_final` (`:219`),
`test_stress_fields_breach_only_the_named_fields` (`:322`), and
`test_a_dead_provider_scores_as_an_error_rather_than_ending_the_run` (`:289`). These
already encode the properties the extraction must preserve — in particular `:390` and
`:420` are the no-key and non-degeneracy guarantees the prompt calls first-class. The
extraction does **not** need to invent a test suite; it needs to keep this one green
while the implementation moves underneath it. That is the cheapest possible regression
gate and it is already written.

**F9 — Phase 1's Step 6 eval adapter is the seam that must be revisited — and the plan's
answer is "don't". (Medium-High)**

Phase 1's Step 6 (plan doc lines 468–477) deliberately types the eval adapter as taking
"a plain `dict[str, float]` metric map … plus an explicit `headline_metric`", with the
stated rationale "Takes a dict, not an `EvalResult` type, so Phase 3's extraction is not a
dependency." Phase 3 *does* introduce a real result type (`CaseResult` /
`compute_metrics`'s dict). The decoupling still holds in the right direction — Phase 1
does not import Phase 3 — but the temptation at execute time will be to "upgrade" the
adapter to take the new type. That would re-couple the registry to the AI harness and
undo Phase 1's explicit design. The correct treatment: Phase 3 supplies a **one-line
projection** (`metrics_dict()` on its result type) that feeds Phase 1's existing dict
adapter unchanged, and Phase 1's `runs/adapters/evaluation.py` signature does not move.
`compute_metrics` already returns exactly that dict shape (`run.py:395-408`) with one
wrinkle: `repair_convergence` can be `None` (`:398-402`) and `cases`/`errors`/
`total_llm_calls` are `int`, so a `dict[str, float]` claim needs a documented coercion or
a filtered projection. **That is the concrete Phase-1 coupling to address.**

**F10 — `EvalCase`'s only galactus tie is `Fact`, and `is_grounded` only reads
`.text`. (High)**

`Fact` (`models.py:119-134`) carries `text`, `source_span`, `page`, `confidence`,
`origin`. `is_grounded` (`:364`) uses `" ".join(f.text for f in facts)` — nothing else.
`EvalCase` splits facts into `sender_facts`/`receiver_facts` (`:111-112`), which is a
marketing-collateral concept (partnership attribution, per `generate.py:286-301`), then
immediately re-concatenates them for grounding (`run.py:332`). So the generic harness
needs `grounding_texts: list[str]`; the sender/receiver split is case-specific
enrichment that stays in `ai-marketing-comms`.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `evals/run.py` `compute_metrics` + `_rate` (`:383-412`) | **REUSE** | — | Zero galactus imports; operates only on `CaseResult` fields. Moves verbatim. |
| `evals/run.py` `CaseResult` (`:284-297`) | **REUSE** | — | Zero imports. `error: str \| None` already encodes the "recorded decision" pattern `RunResult.skipped` uses on the ML side (F6). |
| `evals/run.py` `summarize_table` + `format_report` (`:420-480`) | **REUSE** | — | Pure rendering over `CaseResult`. `summarize_table`'s docstring already flags it as previously copied from `cap-genai.md` — third home, still no dependency. |
| `evals/run.py` grounding (`is_grounded`, `_distinctive_tokens`, `_STOPWORDS`, `_TOKEN_RE`) | **ADAPT** | — | One-line change: accept `Sequence[str]` instead of `list[Fact]` (F10). The stopword list and the `MIN_GROUNDING_OVERLAP=2` rationale transfer untouched. |
| `evals/run.py` `ScriptedEvalLLM` (`:150-243`) | **ADAPT** | — | The highest-value asset (F2). Its `_value_for` reads `field.kind/max_words/min_words/max_chars` off `LayoutTemplate`; extraction needs a field-spec Protocol so the mechanism survives without the type. |
| `evals/run.py` `STRESS_PROFILES` + `_scripted_llm` (`:246-276`) | **ADAPT** | — | Mechanism (per-case breach profiles → non-degenerate spread) is generic; the *contents* are galactus case ids and stay in the poc. Extract as an injected mapping, not a constant. |
| `evals/run.py` `EvalCase` + `load_cases` (`:104-142`) | **ADAPT** | — | Duplicate-id validation and blank-line skipping are generic; `sender_facts`/`receiver_facts` are not (F10). Generic base + case-specific subclass. |
| `evals/run.py` `main` / argparse / exit code (`:488-531`) | **ADAPT** | — | `--dry-run/--json/--cases` flags and the "exit 1 iff contract_valid_rate != 100" rule generalize; `Settings`, `configure_structlog`, `AnthropicAdapter` wiring is case-specific and stays. |
| `evals/run.py` `run_case` / `run_all` (`:299-346`) | **ADAPT** | — | The seam. Needs three injected callables (contract-for-case, produce, validate) plus the F4 process-facts return. Sequential-not-gathered rationale (`:343-345`) transfers verbatim. |
| `galactus.generate.generate_collateral` | **SKIP** | The *shape* — `(artifact, used_fallback)` + mutated state carrying `first_pass_valid`/`repair_attempts` — is the producer contract the extracted harness must require (F4) | The function itself is marketing-collateral specific (prompt prose about page layout, sender/receiver facts, theme colors). Do not move it; specify its contract as a Protocol. |
| `galactus.layout.validator.is_valid` / `validate` | **SKIP** | The `Violation` *shape* — `field`, `constraint`, `repair_hint`, `actual`, `limit` — is a generic repair-loop currency worth mirroring in the extracted contract | Word/char/hex-color/placeholder checks are layout-specific. The harness only needs `validate(output, contract) -> bool` at the seam. |
| `galactus.models.PipelineState` | **SKIP** | `first_pass_valid`'s docstring rationale (`models.py:150-159`) — it is the argument for F4 and should be quoted in the extracted producer Protocol | Pydantic model with `job_id`/`sender_facts`/`receiver_facts`/`draft` — collateral-shaped throughout. |
| `galactus.models.Fact` | **SKIP** | `.text` only (F10) — the extracted grounding takes `Sequence[str]` | `source_span`/`page`/`origin` encode a PDF-extraction provenance model the generic harness has no use for. |
| `galactus.llm.port.LLM` Protocol (`port.py:34-56`) | **REUSE** | — | Already provider-agnostic, already a `runtime_checkable` Protocol, one method. Its own docstring notes it was designed so fakes need no import. Copy the Protocol into the template verbatim; it is 20 lines and importing it would recreate the welding. |
| Template `{{ eval_root }}/graders/` | **SKIP** | The `graders/heuristic` vs `graders/judges` *split* is a good precedent for "free deterministic check paired with paid LLM check" — the same pairing the dry-run/live split expresses | Retrieval + interaction graders score existing rows against golden answers. No producer, no repair, no contract (F1). |
| Template `{{ eval_root }}/metrics/` | **SKIP** | `metrics/_shared.py`'s existence proves the tree already expects a shared-helper module — the new metrics can live as a sibling file here rather than a new directory | `hit_rate`, `mean_reciprocal_rank`, escalation/friction/intent/language are all row-grading metrics. None of the four Phase 3 metrics has an analogue. |
| Template `{{ eval_root }}/pipelines/` | **ADAPT** | — | `run.py.jinja` and `grade.py.jinja` establish the CLI-entrypoint-per-eval-kind convention (`python -m evals.pipelines.<kind>`) plus the `targets.yaml` gate. The Phase 3 harness should be a third entrypoint here, inheriting that convention. |
| Template `{{ eval_root }}/reports/` | **SKIP** | The `builder.py`/`renderer.py` split (build a report object, then render it) is the right factoring — `format_report` currently does both in one function | Reports are Pydantic-model-shaped over `GraderResult`. The Phase 3 report is a markdown table over `CaseResult`. |
| Template `{{ eval_root }}/models.py` | **SKIP** | Its docstring's precedent of *explicitly namespacing distinct eval kinds within one root* (`models.py:1-7`) is the argument for F1's "extend, don't duplicate" verdict | `EvalInteraction`/`GraderResult`/`MetricSummary` are interaction-grading types with no producer or repair concept. |
| Template `{{ eval_root }}/targets.yaml.jinja` + `_check_targets` | **ADAPT** | — | A declarative metric-threshold gate is exactly what a generalized harness wants instead of the hardcoded `contract_valid_rate == 100.0` (`run.py:527`). But the existing gate is `actual >= target` only; `fallback_rate` and `repair_convergence` are *lower-is-better*, so direction must be added. |
| Template `graders/judges/base.py` degradation contract | **SKIP** | The `judges_available()` capability-probe *function shape* is reusable for deciding live-vs-dry — but its `return None` consequence must be inverted | Degrading to "skipped" is the exact opposite of the dry-run guarantee (F2). Adopting this contract would be the failure mode the prompt names. |
| `ml/workflows/classification.py` (`RunResult`, `skipped`, assertable invariant) | **ADAPT** | — | The structural template for Phase 3 (F6): one entry point, one result object, decisions recorded not omitted. Do not copy `ModelRun.headline`'s hardcoded PR-AUC property (F6, Phase-1 F2). |
| Phase 1 `runs/adapters/evaluation.py` (dict + `headline_metric`) | **REUSE** | — | Explicitly designed not to depend on Phase 3 (F9). Phase 3 feeds it via a projection method; the adapter signature must not change. |
| `ai-marketing-comms/tests/test_evals.py` (428 lines, 33 tests) | **REUSE** | — | Already asserts the no-key guarantee (`:390`), non-degeneracy (`:420`), and first-pass-not-final semantics (`:219`). Keep green throughout; it is the regression gate (F8). |
| `evals/cases.jsonl` (12 cases) | **SKIP** | The *difficulty* field and the id↔stress-profile correspondence are the mechanism worth generalizing | Marketing-collateral briefs with sender/receiver facts and `template_id`s. Stays in the poc as the case study's data. |

### Assumptions
- **Assumption:** Phase 3's deliverable belongs under the existing `{{ eval_root }}/`,
  not a new `src/evals/` — **Evidence:** copier.yaml:322-326 ("a SIBLING of both source
  roots … a consumer of every root"), F1's kind-not-duplicate analysis, `models.py:1-7`'s
  precedent of namespacing kinds within one root — **If wrong:** a second eval root
  exists, `make eval-*` targets fragment, and the structure guard's `eval_allowed_dirs`
  no longer describes where evals live — **Confidence:** High
- **Assumption:** Preserving the eight baseline numbers exactly is achievable because the
  scripted adapter is fully deterministic — **Evidence:** `ScriptedEvalLLM` has no
  randomness; `LOREM` indexing is `i % len(LOREM)` (`:234`); `run_all` is sequential by
  design (`:343-345`); the captured baseline is reproducible — **If wrong:** the
  extraction changed adapter behavior, which is precisely the failure the phase must not
  ship — **Confidence:** High
- **Assumption:** A field-spec Protocol (name/kind/max_words/min_words/max_chars) is
  sufficient to decouple `ScriptedEvalLLM` from `LayoutTemplate` — **Evidence:**
  `_value_for` (`:220-243`) touches exactly those five attributes and nothing else —
  **Confidence:** High
- **Assumption:** `ai-marketing-comms` can import from the template's extracted module —
  **Evidence:** none found. galactus is a standalone repo with its own `pyproject.toml`;
  the template scaffolds *new* projects. **This is the largest unverified assumption** —
  **If wrong:** the case study proves generality by *mirroring* the extracted code rather
  than importing it, which weakens the "second poc composes" claim to "second poc copies"
  — **Confidence:** Low. See Key Unknowns and Open Question 2.
- **Assumption:** `repair_convergence`'s `None` and the three `int` metrics can be
  projected into Phase 1's `dict[str, float]` without loss — **Evidence:**
  `compute_metrics:395-408`; `None` means "no case converged", which Phase 1's
  `NotApplicable` sentinel exists to express — **If wrong:** Phase 1's Step 6 signature
  needs the revisit F9 argues against — **Confidence:** Medium

### Disconfirming Evidence

**Against F1 (extend, don't duplicate):** Steel-manned the duplication case. If the
existing tree already had a producer-driving pipeline, Phase 3 would be a refactor, not
an addition. Checked `pipelines/run.py` and `pipelines/grade.py` end to end: `run.py`
calls `search_fn(question)` then optionally `try_generate_fn` (`:298-306`) — that *is* a
producer call. But it is best-effort *enrichment* that returns `None` without a key
(`:162-180`), and no result of it is validated against a contract or repaired. The
closest thing to overlap is real and bounded: **the `targets.yaml` gate genuinely
duplicates** what Phase 3's exit code does, and that is called out as an ADAPT row rather
than ignored. **Looked; found one real partial overlap, no structural duplication.**

**Against F2 (no dry-run adapter exists):** Searched the entire scaffold for
`dry.run|dry_run|Scripted|scripted|fake|stub`. Hits were test-local monkeypatch fakes and
type-stub comments only. Also checked whether `graders/custom/` or `pipelines/sampling.py`
might host one — they do not. **Looked, found nothing contradicting.**

**Against F5 (`ai/evals/` is not a literal path):** Considered that issue #4 might
genuinely intend a new root, since it also names `ai/workflows/`. But the sibling-root
rationale in copier.yaml predates the issue and is stated as a design conclusion, and
`ml/workflows/` — the stated analogue — is inside `ml_source_root`, i.e. `ml/workflows/`
maps to `src/workflows/` on the AI side, *not* `src/evals/`. So the analogue supports a
`workflows/` package under `ai_source_root` and an *evals* addition under `eval_root` —
two different destinations for the two halves. **Looked; the finding survives but split
the destination in two, which is why Open Question 1 exists.**

**Against F7 (baseline is trustworthy):** A baseline captured once could be
environment-dependent. Checked the sources of nondeterminism: no `random`/`np.random` in
`run.py`; `ScriptedEvalLLM.LOREM` indexing is deterministic; `load_cases` preserves file
order; `run_all` is sequential. The one environment coupling is
`Settings.load().log_level` (`:507`), which affects only the stderr spans, not the
metrics JSON. **Looked, found the baseline safe to treat as a contract, with the caveat
that assertions must read stdout only.**

**Against F9 (don't revisit Phase 1's adapter):** Steel-manned the upgrade. A typed
`EvalResult` in the adapter signature would give type safety and remove the coercion
question. But it would make `runs/` import from `evals/`, and Phase 1's Out of Scope
already names "The AI-side adapter's extraction from `galactus.*` — that is Phase 3"
(plan:288-290). Upgrading it would reverse a decision made deliberately one phase
earlier. **Looked, found the decoupling worth defending — the cost is a documented
projection, which is cheaper than the coupling.**

**Against F8 (the test suite transfers):** Read the test function names but not all 428
lines. Tests importing `Fact`, `LayoutTemplate`, or the `template` fixture (`:245`,
`:322`, `:337`) will not transfer to a template-side test unchanged. So the suite is the
gate for *the poc side*; the template side needs its own tests. **Looked, found a real
limit — reflected in the plan's two-sided test strategy.**

### Key Unknowns
- **Whether `ai-marketing-comms` can actually import the extracted module.** Not
  determined. galactus has no dependency on `ai-project-template`, and the template is a
  copier template, not a published package. This decides whether Phase 3's done-condition
  ("a second AI poc runs the harness without importing anything from `galactus.*`") is
  provable by import or only by scaffolding. **This is the single biggest unknown and
  Step 1 of the plan exists to answer it before anything moves.**
- **Whether the structure guard fires.** `eval_allowed_dirs` is
  `graders metrics pipelines reports utils` and `enable_structure_guard` is on for
  `eval_suite`/`rag` project types. Whether a new sibling directory trips it was not
  executed — only read from `copier.yaml:1119-1130`. Not found: the guard's
  implementation.
- **Where `ai/workflows/` should live, or whether it is needed at all.** Issue #4 says
  "+ `ai/workflows/` if composition needs it". The research suggests it *is* needed — the
  generate→validate→repair→fallback loop is the AI analogue of `run_classification` — but
  extracting that loop is a materially larger job than extracting the harness, and the
  four metrics do not require it (they require only that a producer *report* the process
  facts, F4).
- **The `targets.yaml` direction problem.** Two of the four metrics are lower-is-better.
  `_check_targets` only implements `actual >= target` (`pipelines/run.py:141`). Whether
  to extend it or bypass it is undecided.
- **Whether `cases.jsonl` should stay JSONL.** The template's own eval data lives at
  `data/evals/*.jsonl` and `data/raw_corpus/golden_qa.jsonl`, so the format is
  consistent; the *location* convention (`data/` vs alongside the harness) differs from
  galactus's.

### Recommendation
Extend the existing `{{ eval_root }}/` tree rather than creating a parallel `ai/evals/`
root — the two eval kinds are complementary, not competing, and the template already has
a precedent for namespacing kinds within one root. The extraction should be organized
around the observation that only three things in `run.py` are genuinely case-specific:
turning a case into a contract, running a producer, and validating output. Everything
else — the four metrics, the reporting, the grounding heuristic, the case loader's
validation, and most of the scripted adapter's *mechanism* — is generic Python already.
The single property that must survive is the dry-run adapter's *non-degenerate spread*:
an extraction that produces a scripted provider which passes every case has technically
preserved `--dry-run` and actually destroyed it, and `test_dry_run_spread_is_not_degenerate`
is the existing test that catches this. Capture the eight-number baseline first, keep
`ai-marketing-comms/tests/test_evals.py` green throughout, and resist the temptation to
upgrade Phase 1's dict-shaped eval adapter — that decoupling was bought deliberately and
a projection method is the cheaper way to honor it.

---

## Plan
Date: 2026-08-11
Based on: `## Research` above

### Goal
**Inferred, not elicited** (this planning session could not interview): make the AI-side
eval harness composable, so that when the next AI poc is prototyped the decision "do we
write an eval harness or reuse one?" has already been answered — the same decision
`ml/workflows/` settled on the ML side — while `ai-marketing-comms` continues to produce
byte-identical numbers as the case study that proves the harness works.

### Open Questions

**All nine resolved 2026-08-11 at `/workflow-refine`.** Item 2 was confirmed by Ramsey
directly; items 3 and 7 were resolved by verification against the template; the rest on
recorded evidence. No item remains UNCONFIRMED.

1. **RESOLVED (evidence) — Destination is
   `template/_scaffold/{{ py_project_root }}/{{ eval_root }}/generation/`** (new sibling of
   `graders/`, `metrics/`, `pipelines/`, `reports/`) plus one CLI entrypoint at
   `{{ eval_root }}/pipelines/generation.py`. **Not** a new `src/evals/` root. Basis: F1/F5
   plus the naming caveat — `ai_source_root` renders to `src`, so the issue's literal
   `ai/evals/` would become `src/evals/`, a *third* eval location contradicting
   copier.yaml:322-326's "sibling of both source roots, not nested" rule. The issue's
   wording names an intent, not a path.

2. **RESOLVED (Ramsey, 2026-08-11) — `ai-marketing-comms` does not import the
   extraction.** The case study keeps its own `evals/run.py`, refactored to sit on the same
   seam (same three injected callables, same result types by structure). Generality is
   proven by a **second consumer built as a test fixture inside the template**, per Phase
   3's done-condition. Confirmed over the import alternative, which would open a packaging
   question this plan does not answer — galactus has no dependency on the template, and the
   template is a copier template rather than a package. Step 1 still verifies whether a real
   import is possible and **records the answer either way**, since that finding has value
   independent of the decision.

3. **RESOLVED (verified 2026-08-11) — `generation` must be added to `eval_allowed_dirs`.**
   The guard is live, not nominal: `template/.claude/hooks/structure_guard.sh.jinja:9`
   reads `ALLOWED_EVALS_DIRS="{{ eval_allowed_dirs }}"` and enforces it, and
   `template/CLAUDE.md.jinja:56` states the rule to the scaffolded project ("Never add
   top-level directories to `{{ eval_root }}/` beyond: {{ eval_allowed_dirs }}"). Current
   value (copier.yaml:1120-1122): `graders metrics pipelines reports utils`. The fallback
   of flattening into `metrics/` and `pipelines/` is therefore **not** needed.

4. **RESOLVED (evidence) — `ai/workflows/` is out of scope.** This phase extracts the
   *harness* and specifies the producer as a Protocol rather than shipping a generic
   generate→repair→fallback loop (F4). Basis: including it adds 3–4 steps and a second
   review boundary, roughly doubling the phase, and the Protocol is what the done-condition
   actually requires.

5. **RESOLVED (evidence) — Phase 1's adapter signature does not change.** Phase 3 supplies
   a projection feeding Phase 1's `dict[str, float]` + explicit `headline_metric` (F9).
   Non-float values (`cases`, `errors`, `total_llm_calls` are `int`) coerce to float;
   a null `repair_convergence` maps to Phase 1's `NotApplicable` sentinel — **never to
   `0.0`, which would read as "converged instantly"**, the exact brier/getattr failure
   Phase 1's F7 cites. Direction preserved: the registry gains no import from the eval
   harness.

6. **RESOLVED (evidence) — Headline metric is `contract_pass_rate`**, matching Phase 1's
   own worked example. Noted because Phase 1's `RunRecord.__post_init__` validates that the
   declared headline exists in the metrics map — so this must stay in sync with the
   projection in item 5.

7. **RESOLVED (verified 2026-08-11) — Do not wire into `targets.yaml` this phase.** The
   extracted harness keeps its own exit rule (`contract_valid_rate != 100.0` → exit 1).
   Two independent bases: `_check_targets` implements `actual >= target` only, while
   `fallback_rate` and `repair_convergence` are lower-is-better; **and** a search of
   galactus found no `targets.yaml` and no `_check_targets` outside plan docs — the gate
   exists only in the template, so wiring into it would couple the case study to
   scaffolding it does not have. Follow-up: extend `_check_targets` with per-metric
   direction.

8. **RESOLVED — Branch/issue: `AIT-` prefix, one issue and one branch per repo.** Code
   lands in `ai-project-template` (so the prefix follows the changed repo per `agile.md`),
   while the plan doc stays in galactus per the four-docs-together convention. Phase 3
   shares the `ai-project-template` branch and issue with Phase 1 (Ramsey, 2026-08-11:
   one issue and one branch per repo, not per phase). This is the same prefix defect that
   refine corrected in Phase 1 — caught independently here at planning time.

9. **RESOLVED (evidence) — Phase 3 branches from `main` and does not depend on `AIT-67`.**
   It touches no `ml/` file. `AIT-67-ml-workflows-classification` is committed (`0f8b2cf`)
   but unmerged (F6); since Phase 1 shares this branch and *does* compose against #67, the
   shared branch takes Phase 1's constraint — see Phase 1's merge-order risk row. Phase 3's
   own work adds no further dependency.

### Approach
Extract in the direction that keeps the case study frozen: **capture the baseline, build
the generic modules alongside the existing code, prove them with a second synthetic
consumer, and only then refactor `ai-marketing-comms/evals/run.py` to sit on the new
seam** — verifying the eight-number baseline after every step that could move it. The
generic core is three injected callables (`contract_for(case)`, `produce(case, contract)`,
`validate(output, contract)`) plus a producer result carrying the four *process facts*
(F4) that the metrics cannot be reconstructed without. The scripted adapter is extracted
against a five-attribute field-spec Protocol rather than `LayoutTemplate`, and its
per-case stress profiles become an injected mapping rather than a module constant, so the
non-degenerate spread property is configurable rather than hardcoded to galactus case ids.
**Key tradeoff:** specifying the producer as a Protocol instead of shipping a generic
generate→repair→fallback loop means the second poc still writes its own producer — it
gets the harness, the metrics, the reporting, and the dry-run machinery for free, but not
the generation loop. That is the honest boundary of what the four metrics actually
require, and it keeps this phase to seven steps instead of twelve.

### Out of Scope
- **`ai/workflows/` — a generic generate→validate→repair→fallback loop** (Open Question
  4). This phase specifies the producer contract; it does not implement a generic
  producer.
- **Any behavior change in `ai-marketing-comms`.** Refactoring to the new seam is
  permitted; changing what the numbers are is not. The eight-number baseline (F7) is the
  contract.
- **Scaffolding a real second AI poc** (`ai/agentic-workflow`, `ai/chat-assistant-rag`,
  `ai/voice-assistant` are all empty per issue #4). The second consumer is a test fixture.
  A real poc is Phase 4's business.
- **W&B, and the run registry itself** (Phase 1). Phase 3 supplies a projection into
  Phase 1's existing adapter; it does not build or modify the registry.
- **Changing Phase 1's `runs/adapters/evaluation.py` signature** (F9, Open Question 5).
- **Rewriting the existing `{{ eval_root }}/` graders, metrics, pipelines, or reports.**
  Additive only. `evals.pipelines.run` and `evals.pipelines.grade` must keep working.
- **`targets.yaml` gate integration** (Open Question 7).
- **Extracting `galactus.layout.validator`, `galactus.generate`, or `galactus.models`.**
  All SKIP per the asset verdicts — their *shapes* inform Protocols; their code stays.
- **Packaging/distribution of the template as an importable library** (Open Question 2's
  reversal).
- **`ml/` — any file under `ml_source_root`.** Phase 3 reads `ml/workflows/` as a shape
  reference and modifies nothing there.

### Steps

Seven steps, two review boundaries. Steps 1–3 are template-side and touch no galactus
file. Step 4 proves generality. Steps 5–6 touch the case study and are gated on the
baseline. Step 7 wires Phase 1.

---

#### Step 1: Capture the regression baseline and answer the import question
**Files**: new `template/_scaffold/{{ py_project_root }}/tests/unit/evals/BASELINE.md`
is **not** created — the baseline lives in this plan doc (F7) and in a test constant
added in Step 5. This step writes **no production code**; it produces two recorded
answers.
**What**: (a) Re-run and re-record the baseline immediately before any file moves, to
confirm the F7 numbers still hold on the executing machine. (b) Determine empirically
whether `ai-marketing-comms` can import from `ai-project-template` — check
`galactus/pyproject.toml` for any path/git dependency on the template, and check whether
the template is installable at all. Record the answer in this doc's Open Question 2 as
resolved-with-evidence. This is the step that decides whether the rest of the plan's
Step 6 is "refactor to import" or "refactor to mirror".
**Snippet**:
```bash
# baseline — stdout only; stderr carries structlog spans that vary by log_level
cd ~/workspace/galactus && \
  uv run python ai-marketing-comms/evals/run.py --dry-run --json 2>/dev/null
# expect exactly the eight numbers in F7

# import feasibility
grep -n "ai-project-template\|ai_project_template" ~/workspace/galactus/pyproject.toml
```
**Test**: `cd ~/workspace/galactus && uv run python ai-marketing-comms/evals/run.py --dry-run --json 2>/dev/null`
**Done when**: the eight numbers match F7 exactly (`cases` 12, `contract_pass_rate` 58.3,
`repair_convergence` 0.36, `fallback_rate` 8.3, `grounding_rate` 91.7,
`contract_valid_rate` 100.0, `errors` 0, `total_llm_calls` 19); exit code is 0; and Open
Question 2 carries a dated resolution with the grep output as evidence. If the numbers
differ from F7, **stop and report** — the baseline moved before the extraction began and
that is itself the finding.

---

#### Step 2: The case-agnostic core — result types, metrics, reporting
**Files**: new `template/_scaffold/{{ py_project_root }}/{{ eval_root }}/generation/__init__.py`,
new `.../generation/results.py`, new `.../generation/metrics.py`,
new `.../generation/report.py`
(directory subject to Open Question 1/3)
**What**: Move the four REUSE assets verbatim — `CaseResult` (`run.py:284-297`),
`compute_metrics` + `_rate` (`:383-412`), `summarize_table` + `format_report`
(`:420-480`) — plus the grounding functions ADAPTed to take `Sequence[str]` instead of
`list[Fact]` (F10). Zero imports from `galactus.*` and zero imports from `ml.*` or
`agents.*`. Preserve every docstring rationale verbatim: the denominators-with-rates
argument (`:386-388`), the `MIN_GROUNDING_OVERLAP` "blunt proxy, and named as one"
paragraph (`:48-54`), and the "a case with no facts is never grounded" reasoning
(`:357-360`) — those are the claims that make the metrics defensible.
**Snippet**:
```python
# before (galactus/evals/run.py:354)
def is_grounded(draft: dict[str, str], facts: list[Fact]) -> bool:
    if not facts:
        return False
    fact_tokens = _distinctive_tokens(" ".join(f.text for f in facts))

# after (template .../generation/metrics.py)
def is_grounded(output: dict[str, str], grounding_texts: Sequence[str]) -> bool:
    """Whether an output's content traces back to the supplied source texts.

    A case with no grounding texts is never grounded — that is the honest
    reading, not a vacuous pass. Reporting 100% grounding on a run that
    included an ungrounded case would be the exact overclaim these metrics
    exist to prevent.
    """
    if not grounding_texts:
        return False
    fact_tokens = _distinctive_tokens(" ".join(grounding_texts))
```
**Test**: `cd ~/workspace/ai-project-template && make test_render PYTEST_ARGS="tests/unit/evals/test_generation_metrics.py -v"`
**Done when**: `compute_metrics` over a hand-built list of `CaseResult` reproduces the
four rates and their denominators; `repair_convergence` is `None` when nothing converged
and excludes both fallback and errored cases; `is_grounded` returns False for empty
grounding texts and requires ≥2 distinctive shared tokens; stopwords do not count; and
`grep -rn "galactus\|from ml\.\|from agents\." <generation dir>` returns nothing.

---

#### Step 3: The dry-run seam — field-spec Protocol, scripted adapter, stress profiles
**Files**: new `.../generation/ports.py`, new `.../generation/scripted.py`
**What**: **The first-class requirement.** Copy the `LLM` Protocol from
`galactus/llm/port.py:34-56` verbatim (REUSE — 20 lines, and its own docstring explains
it was designed so fakes need no import). Add a `FieldSpec` Protocol carrying exactly the
five attributes `_value_for` touches: `name`, `kind`, `max_words`, `min_words`,
`max_chars` (F3). Extract `ScriptedEvalLLM` against `FieldSpec` instead of
`LayoutTemplate`, preserving the overshoot/tighten/stubborn logic *exactly* — including
`LOREM`'s `i % len(LOREM)` indexing, the `ceiling + 6` overshoot, the `max(floor,
ceiling - 1)` aim, and the whole-word truncation on the non-overshooting path
(`:220-243`). `STRESS_PROFILES` becomes an **injected mapping** parameter rather than a
module constant, because its keys are galactus case ids; the *mechanism* (per-case breach
class → non-degenerate spread) is what ships.
**Snippet**:
```python
# before (galactus/evals/run.py:262, module-level constant)
STRESS_PROFILES: dict[str, dict[str, Any]] = {"overlong-headline-pressure": {...}, ...}

def _scripted_llm(case: EvalCase, template: LayoutTemplate) -> ScriptedEvalLLM:
    profile = STRESS_PROFILES.get(case.case_id, {})

# after (template .../generation/scripted.py — mechanism, not contents)
def scripted_provider_for(
    case: GenerationCase,
    fields: Sequence[FieldSpec],
    stress_profiles: Mapping[str, StressProfile],
) -> ScriptedProvider:
    """Give each case a scripted provider matched to its difficulty.

    Difficulty drives behaviour so the dry-run metrics have a real spread:
    easy and medium cases pass first time, hard cases need repair, and the
    stubborn case exhausts the budget. Without a per-case profile every hard
    case would breach every field identically and the run would report the
    same violations N times over — a spread that says nothing.
    """
    profile = stress_profiles.get(case.case_id, StressProfile())
```
**Test**: `make test_render PYTEST_ARGS="tests/unit/evals/test_generation_scripted.py -v"`
**Done when**: the scripted provider overshoots only on `difficulty == "hard"`; a
`stress_fields` profile breaches only the named fields and leaves the others compliant; a
`bad_color` profile emits a hex literal where a named color is required; a `stubborn`
profile never tightens across repeated calls while a non-stubborn one tightens on call 2;
`calls` increments per call; and the module imports nothing from `galactus.*`.

> **REVIEW BOUNDARY 1** — the case-agnostic core and the dry-run seam are complete and
> independently tested. Nothing in `ai-marketing-comms` has been touched; the Step 1
> baseline is by construction unchanged. Verify that before proceeding.

---

#### Step 4: The runner seam + a second consumer that is not galactus
**Files**: new `.../generation/runner.py`,
new `.../generation/cases.py`,
new `template/_scaffold/{{ py_project_root }}/tests/unit/evals/test_generation_second_consumer.py`
**What**: Extract `run_case`/`run_all` (`run.py:299-346`) against three injected
callables — `contract_for(case)`, `produce(case, contract, provider)`,
`validate(output, contract) -> bool` — with the producer required to return the **process
facts** (`first_pass_valid`, `repair_attempts`, `used_fallback`) alongside the output
(F4). Preserve the sequential-not-gathered rationale (`:343-345`) and the
one-dead-case-must-not-end-the-run exception handling (`:313-324`) verbatim. Extract the
generic half of `EvalCase`/`load_cases` (`:104-142`): JSONL loading, blank-line skipping,
duplicate-`case_id` rejection, `difficulty` default — without `sender_facts`/
`receiver_facts`/`template_id` (F10). Then write the **second consumer**: a minimal
non-marketing domain in the test file (e.g. a fixed-width log-line formatter with a
two-field contract) that composes the harness and produces a report — proving Phase 3's
done-condition without scaffolding a real poc.
**Snippet**:
```python
# after (.../generation/runner.py) — the seam, in one signature
async def run_case(
    case: GenerationCase,
    *,
    contract_for: Callable[[GenerationCase], Contract],
    produce: Callable[..., Awaitable[ProducerOutcome]],
    validate: Callable[[dict[str, str], Contract], bool],
    provider: LLM | None = None,
) -> CaseResult:
    """Run one case end to end and score it.

    `produce` returns process facts, not just an artifact. Contract pass rate
    is measured on the FIRST generation, before repair, and is not
    reconstructable afterwards: a run with repair_attempts == 0 could equally
    be a clean first pass or a run given no repair budget.
    """
```
**Test**: `make test_render PYTEST_ARGS="tests/unit/evals/test_generation_second_consumer.py -v"`
**Done when**: the second consumer runs the harness end to end with a scripted provider
and no API key, producing all four metrics with a non-degenerate spread (at least one
first-pass pass, at least one repair, at least one fallback); its module imports nothing
from `galactus.*`; a deliberately dead producer scores as `error` without ending the run;
`run_all` preserves case order; and `load_cases` rejects a duplicate `case_id` and skips
blank lines.

---

#### Step 5: Pin the baseline as an executable assertion in the case study
**Files**: edit `ai-marketing-comms/tests/test_evals.py` (append one test near the
existing dry-run tests at `:390-428`)
**What**: Before any refactor of `run.py`, add a test that asserts the exact eight-number
baseline from F7/Step 1 by invoking `main(["--dry-run", "--json"])` and parsing stdout.
The existing suite covers *properties* (exit zero without a credential `:390`, parseable
JSON `:405`, non-degenerate spread `:420`); none of them pins the *values*. This test is
the tripwire for Step 6 — it must be written and passing **before** `run.py` changes, or
the regression check is retroactive and worthless.
**Snippet**:
```python
# after (ai-marketing-comms/tests/test_evals.py, appended)
EXTRACTION_BASELINE = {
    "cases": 12,
    "contract_pass_rate": 58.3,
    "repair_convergence": 0.36,
    "fallback_rate": 8.3,
    "grounding_rate": 91.7,
    "contract_valid_rate": 100.0,
    "errors": 0,
    "total_llm_calls": 19,
}


def test_dry_run_metrics_are_unchanged_by_the_harness_extraction(capsys, monkeypatch):
    """The GAL-4 Phase 3 regression contract, captured 2026-08-11.

    The extraction is behaviour-preserving or it is a failed phase. These are
    not aspirational targets — they are what this case file produced against
    the scripted adapter before a single file moved.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["--dry-run", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == EXTRACTION_BASELINE
```
**Test**: `cd ~/workspace/galactus && uv run pytest ai-marketing-comms/tests/test_evals.py -q`
**Done when**: the new test passes against the **unmodified** `run.py`, and the full
`test_evals.py` suite (33 existing tests + 1) is green. If it fails here, the baseline in
F7 is wrong and Step 6 must not start.

---

#### Step 6: Refactor the case study onto the extracted seam
**Files**: edit `ai-marketing-comms/evals/run.py` (all regions per F3's coupling map)
**What**: Rewrite `run.py` so its case-agnostic regions are *structurally identical* to
the extracted modules (or literally imported, if Step 1 resolved Open Question 2 in
favour of importability), leaving only the case-specific parts: `Fact`-typed
`sender_facts`/`receiver_facts`, `template_id` → `load_template_cached`,
`generate_collateral` as the producer, `is_valid` as the validator, the galactus
`STRESS_PROFILES` contents, and the `Settings`/`configure_structlog`/`AnthropicAdapter`
live-path wiring. **The `--dry-run` flag, its no-key guarantee, and the exit-code rule
must be untouched in observable behavior.** Adapt `generate_collateral`'s call site to
return the process facts explicitly rather than reading them off the mutated
`PipelineState` at the seam — `PipelineState` mutation stays inside the case study, but
the harness boundary receives them as a value.
**Snippet**:
```python
# before (run.py:326-335)
return CaseResult(
    case_id=case.case_id,
    first_pass_valid=bool(state.first_pass_valid),
    repair_attempts=state.repair_attempts,
    used_fallback=used_fallback,
    grounded=is_grounded(draft, case.sender_facts + case.receiver_facts),
    ...
)

# after — the case study supplies a producer; the harness scores it
async def _produce(case, template, provider):
    state = PipelineState(job_id=f"eval-{case.case_id}", prompt=case.prompt, ...)
    draft, used_fallback = await generate_collateral(state, template, provider, model=model)
    return ProducerOutcome(
        output=draft,
        first_pass_valid=bool(state.first_pass_valid),
        repair_attempts=state.repair_attempts,
        used_fallback=used_fallback,
        grounding_texts=[f.text for f in case.sender_facts + case.receiver_facts],
    )
```
**Test**: `cd ~/workspace/galactus && uv run pytest ai-marketing-comms/tests/test_evals.py -q && uv run python ai-marketing-comms/evals/run.py --dry-run --json 2>/dev/null`
**Done when**: **all 34 tests in `test_evals.py` pass, including Step 5's value-pinning
test**; the CLI still prints the identical eight numbers with `ANTHROPIC_API_KEY` unset;
the human-readable (non-`--json`) report still names all four metrics with their
parentheticals; exit code is still 0; and `uv run pytest ai-marketing-comms/tests -q`
(the full suite, not just evals) is green — `test_generate.py` and `test_api.py` must not
have been disturbed.

> **REVIEW BOUNDARY 2** — the case study is refactored and provably unregressed. This is
> the phase's critical constraint discharged. Do not proceed to Step 7 until the eight
> numbers are confirmed identical.

---

#### Step 7: The Phase 1 projection — feed the registry without coupling it
**Files**: new `.../generation/registry_projection.py` (or a method on the metrics
module), new `template/_scaffold/{{ py_project_root }}/tests/unit/evals/test_generation_registry_projection.py`
**What**: Add a projection from the harness's metric dict into the shape Phase 1's
`runs/adapters/evaluation.py` already accepts — plain `dict[str, float]` plus an explicit
`headline_metric` (F9, Open Question 5/6). Handle the two shape mismatches
`compute_metrics` produces: `cases`/`errors`/`total_llm_calls` are `int` (coerce to
`float`), and `repair_convergence` may be `None` (map to Phase 1's `NotApplicable`
sentinel with the reason "no case converged", never to `0.0` — the `brier`/`getattr` bug
Phase 1's F7 cites is exactly this failure mode). **Phase 1's adapter signature does not
change.** Direction of dependency: the projection knows the registry's shape; the
registry knows nothing about evals.
**Snippet**:
```python
# after (.../generation/registry_projection.py)
NON_FLOAT_KEYS = ("cases", "errors", "total_llm_calls")

def to_run_record_metrics(metrics: Mapping[str, Any]) -> tuple[dict[str, float], str]:
    """Project harness metrics into the Phase 1 registry's dict + headline shape.

    Phase 1's eval adapter deliberately takes a plain dict rather than a typed
    eval result, so that Phase 1 could not be blocked on this extraction. That
    decoupling is preserved here: this function knows the registry's shape;
    the registry knows nothing about this harness.

    repair_convergence is None when no case converged. It maps to the registry's
    NotApplicable sentinel with a reason — never to 0.0, which would read as
    'converged instantly' and is the brier/getattr failure Phase 1 exists to
    prevent.
    """
```
**Test**: `make test_render PYTEST_ARGS="tests/unit/evals/test_generation_registry_projection.py -v"`
**Done when**: a projected metric map contains only `float` values plus explicitly
sentinel-marked inapplicables; `headline_metric` defaults to `contract_pass_rate` and is
always a key present in the projected map; `repair_convergence=None` projects to a
sentinel carrying a reason, **not** to `0.0` or a dropped key; and
`grep -rn "from runs\|import runs" <generation dir>` returns nothing — the projection
describes the registry's shape without importing it, so Phase 3 does not depend on Phase 1
having landed.

### Test Plan

**Two-sided, because the code lives in two repos (F8).**

- **Template side** (`~/workspace/ai-project-template`): every step runs
  `make test_render PYTEST_ARGS="tests/unit/evals/<file> -v"` — template sources cannot be
  tested in place; `make test_render` renders to a temp dir with `copier copy --defaults`
  and runs pytest inside it (Makefile:86-105). Note the default render passes
  `-d include_ml=true -d primary_chat_agent=lg_agent`; the new tests must not require an
  ML or agent-specific answer.
- **Full template suite** after Step 4 and Step 7:
  `make test_render PYTEST_ARGS="tests/unit/evals/ -v"` — includes the pre-existing
  `test_interaction_evals.py.jinja`, proving the additive extension did not disturb the
  grading suite (F1's "extend, don't duplicate" claim, verified rather than asserted).
- **Path/config validation**: `make lint` (validate_paths + copier config + ruff over
  `scripts/`) and `make lint-render`. If Open Question 3 resolves toward a new directory,
  `eval_allowed_dirs` must be updated in the same commit or the structure guard fires on
  `eval_suite`/`rag` renders. Watch for a new `ORPHAN_DIR` warning — a scaffold directory
  no copier task reaches is reported as orphaned (Phase 1's Test Plan established the
  clean baseline: 0 errors, 2 warnings, 2 info).
- **Case-study side** (`~/workspace/galactus`): `uv run pytest ai-marketing-comms/tests -q`
  — the whole suite, not just `test_evals.py`, since Step 6 touches a file
  `test_generate.py` and `test_api.py` share types with.
- **The regression gate is the CLI, not only the tests.** After Step 6, run
  `uv run python ai-marketing-comms/evals/run.py --dry-run --json 2>/dev/null` with
  `ANTHROPIC_API_KEY` unset and diff against F7's eight numbers. A test that imports
  `main()` in-process can pass while the CLI entry point is broken.
- **No-network verification**: the dry-run path must be exercised with the key unset
  (`monkeypatch.delenv`, as Step 5's snippet does and `test_evals.py:390` already does).
  A test that happens to run on a machine with a key set proves nothing about the
  guarantee.
- **Ordering is load-bearing**: Step 5 (pin the baseline) must be green **before** Step 6
  (refactor) begins. A regression test written after the refactor pins whatever the
  refactor produced.

### Risks & Rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| **The extraction preserves `--dry-run` but destroys its spread** — a scripted provider that passes every case still "runs with no key" and reports a meaningless 100% (F2) | **Medium-High — the phase's signature failure mode** | Step 3's done-when tests each behavior arm separately (overshoot only on hard, breach only named fields, stubborn never tightens). Step 4's second consumer must show a non-degenerate spread. `test_evals.py:420` guards the case-study side, and Step 5's value pin makes any drift a numeric diff rather than a judgement call. |
| **`ai-marketing-comms` cannot import the template** (Assumption 4, Low confidence), so "composition" degrades to "duplication" | High | Step 1 answers this *before* anything moves. If it resolves negative, the extraction still ships and the case study mirrors the seam structurally — Phase 3's done-condition ("a second AI poc runs the harness without importing `galactus.*`") is satisfied by Step 4's second consumer regardless. |
| **The eight numbers move during Step 6** | Medium | Step 5's pin catches it immediately and Review Boundary 2 blocks progress. Rollback is `git checkout ai-marketing-comms/evals/run.py` — the template-side modules are additive and unaffected. |
| **Structure guard / `eval_allowed_dirs` rejects the new directory** (F5, Open Question 3) | Medium | Detected by `make lint` before merge. Fallback: place modules as flat files under existing allowed dirs (`metrics/`, `pipelines/`), which costs legibility and nothing else. |
| **Scope creep into `ai/workflows/`** — the generic repair loop is the tempting next thing and doubles the phase (Open Question 4) | Medium | Named in Out of Scope. The producer is a Protocol, not an implementation. If a reviewer wants the loop, it becomes its own issue. |
| **Phase 1's eval adapter gets "upgraded" during Step 7**, re-coupling registry to harness (F9) | Medium | Step 7's done-when asserts `grep` finds no `runs` import in the generation package, and states the signature does not change. Reviewers should treat any diff to `runs/adapters/evaluation.py` as out of scope for this phase. |
| **Docstring rationale is lost in the move** — the metrics' defensibility lives in prose (`MIN_GROUNDING_OVERLAP` "a blunt proxy, and named as one", "a case with no facts is never grounded") | Medium | Steps 2–4 name docstring preservation explicitly. This is not cosmetic: the metrics' whole value is that they are honest about what they do not measure. |
| **`repair_convergence: None` projects to `0.0`** in Step 7, reading as "converged instantly" | Low | Step 7's done-when tests it directly; the Phase 1 `NotApplicable` sentinel exists for precisely this and is cited in the snippet. |

**Rollback**: Steps 2–4 and 7 add new files under the template's eval tree and modify no
existing module (the only possible exception is one line in `copier.yaml`'s
`eval_allowed_dirs`, per Open Question 3) — reverting is deleting the directory. Step 5
appends one test. Step 6 is the only destructive edit, confined to
`ai-marketing-comms/evals/run.py`, and is guarded on both sides by the Step 5 pin and the
Review Boundary 2 CLI check. No `ml/` file, no `agents/` file, and no existing
`{{ eval_root }}/` module is modified by any step.
