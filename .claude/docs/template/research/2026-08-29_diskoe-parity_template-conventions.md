# Angle: What conventions from diskoe's mature setup should be templated in ai-project-template?

## Findings

### 1. Spec structure — three-doc split (scope / requirements / roadmap)

[Confidence: High — `diskoe/CLAUDE.md:17-23`, `.claude/specs/design-scope.md:1-8`, `.claude/specs/design-requirements.md:1-7`, `.claude/specs/mvp-roadmap.md:1-13`]

Diskoe restructured its single-doc roadmap into three distinct files on 2026-08-26 because the monolith had become "a roadmap + requirements registry + backlog + decision log + risk register in one file" (`CLAUDE.md:18`). The split disciplines are:

- `design-scope.md` — *what problem, what is out of scope?*
- `design-requirements.md` — *what must exist?* Hosts requirement IDs (`PR-*/CR-*/TR-*`), decisions (`D-`/`DA-`), risks (`RK-`), and doc-vs-code contradictions (`DC-`).
- `mvp-roadmap.md` — *why this next + what to build?* Phases, gates, sequenced `B-` items.

AIT currently scaffolds `DESIGN.md.jinja` (a single doc) and `LIFECYCLE.md.jinja` (phase tracking). There is no equivalent three-doc split, no requirement-ID discipline, and no contradiction/risk register convention.

The three-doc split is worth templating as empty stubs only if a copier question (`include_spec_docs`) controls it — the split earns its complexity only for product-shaped repos with real requirements. Pure infra or ML-pipeline repos do not need it.

---

### 2. Makefile targets

[Confidence: High — `diskoe/Makefile:1-88`, `template/_scaffold/Makefile.jinja:1-293`]

**Diskoe's `gate` target** (`type-check lint test build db-drift`) is the key convention AIT lacks. Diskoe explicitly separates `gate` (dev loop, `--fix` allowed) from `ship` (strict gates, no autofix — so the committed diff is the reviewed diff). AIT's Makefile has `ship: lint test pull push quick-pr` but no explicit `gate` alias.

AIT already has: `test`, `lint`, `lint-check`, `typecheck`, `check-imports`, `ship`, `pull`, `push`, `quick-pr`, `eval-heuristic`, `eval-gate`, `eval-grade`, `eval-grade-gate`, `status`, `docker-up/down`.

**Missing from AIT Makefile:**
- `gate` as an explicit compound target (`lint test typecheck build` for TS, or `lint typecheck test` for Python). This is a naming convention, not logic AIT lacks.
- `db-drift` equivalent — diskoe's migration drift check (`Makefile:40-45`) is project-specific (Supabase) but the pattern of a "skips-without-credentials, fails-loudly-when-reachable" drift check belongs in the Supabase scaffold variant.
- `build` as a top-level target in the TS scaffold. AIT has `ts-build`; diskoe's single-workspace layout makes `build` a natural top-level alias.

---

### 3. Eval harness skeleton — registry + vitest config

[Confidence: High — `diskoe/src/evals/registry.ts:1-40`, `diskoe/src/evals/targets.yaml:1-20`, `diskoe/vitest.config.ts:1-17`, `template/_scaffold/{{ ts_project_root }}/vitest.config.ts.jinja:1-17`]

**Diskoe's eval architecture** (`src/evals/`): `registry.ts` (single wiring point — all metrics register here), `targets.yaml` (thresholds, only written after measurement), `graders/heuristic/` + `graders/judges/`, `fixtures/<name>.jsonl`, `pipelines/grade.ts`, `pipelines/report.ts`.

The key invariant from `CLAUDE.md:127-133`: "Every scoring dimension and enrichment attribute needs an eval metric. Heuristic graders for deterministic functions, LLM judges for prose only. `targets.yaml` thresholds come from a *measured* pass rate — unmeasured metrics stay commented and report `UNGATED`."

AIT already scaffolds an eval harness for Python-shaped projects (`eval-heuristic`, `eval-gate`, `targets.yaml` at `{{ eval_root }}/`) but there is no equivalent TS-native eval scaffold. The TS vitest config (`template/_scaffold/{{ ts_project_root }}/vitest.config.ts.jinja`) is a bare runner config — no registry, no grader convention, no `targets.yaml`.

**The `UNGATED` convention** (missing from AIT) is the most portable piece: an ungated metric reports `UNGATED` rather than being silently skipped. This is a code pattern in `grade.ts`, not a file — but the convention belongs in AIT's eval README template.

**Diskoe's vitest config** introduces one fix vs AIT's template: the regex alias form (`/^@\//` instead of bare `'@'`) for path resolution (`vitest.config.ts:15`). AIT's jinja template uses the same bare-string form and will have the same resolution bug in projects that rely on `@/` imports.

---

### 4. SANYI.md — change contract

[Confidence: High — `diskoe/SANYI.md:1-40`]

Diskoe has a `SANYI.md` as of 2026-08-29 (same day as this research). It maps to the `review-contracts` dimension's `CT-` findings. The file has three layers (Buyi/Jianyi/Bianyi — invariants/budgets/tunables) with per-entry `paths:`, `contract:`, and `evidence:` fields.

AIT has no `SANYI.md` template. The guacamayo review stack's `contracts` dimension reads `SANYI.md` to enforce contracts — without it, `CT-` findings cannot fire on any scaffolded project.

**What to template:** a minimal `SANYI.md.jinja` with the three-layer structure, one placeholder Buyi entry (secrets gate), one placeholder Jianyi entry (module count), and the "how to read" table. The BY-4 rule ("an invariant that is only declared — no test, hook, or type enforcing it — is BY-4") belongs in the template comment.

---

### 5. `.claude/` structure

[Confidence: High — `diskoe/CLAUDE.md:240-266`, observed via `ls`]

**Diskoe's `.claude/` tree:**
- `specs/` — product contracts, subdivided: `pipeline/`, `frontend/`, `agents/`, `graph/`, `infra/`
- `docs/research/` — dated, `Status:`-stamped audits (not contracts)
- `docs/plans/` — per-work-item plan docs
- `docs/` — open-questions, onboarding, feasibility, telemetry, notion mirror
- `agents/` — agent harness files (not present in diskoe's `.claude/` by convention — diskoe has no `agents/` directory there; agent code lives in `src/agents/`)

**AIT's `.claude/` (template level):** the scaffold does not emit a `.claude/` at all except via the companion/dev-companion flag. The `.claude/` that exists in the AIT repo itself is for AIT's own workflow, not scaffolded into output projects.

**Key gap:** AIT scaffolds no `CLAUDE.md`-adjacent spec discipline — no `specs/` directory stub, no `docs/research/` convention. New projects start with just `DESIGN.md` and no separation between "what was decided" (spec) and "what was audited" (research). Diskoe's pattern of `Status:`-stamped dated research docs under `docs/research/` vs. contracts under `specs/` is directly adoptable.

---

### 6. CI gates — eval step in CI

[Confidence: High — `diskoe/.github/workflows/ci.yml:1-53`, `template/_scaffold/.github/workflows/ci.yml.jinja:1-51`]

**Diskoe's CI** runs: `npm ci` → `lint` → `type-check` → `test` → `build` → `npm run eval:grade -- --gate`. The eval gate step passes a blank `GOOGLE_GENERATIVE_AI_API_KEY` so judge metrics degrade gracefully (heuristic-only run exits 0). This is the "CI-safe eval gate" pattern.

**AIT's CI template** (`ci.yml.jinja`) uses the reusable Python workflow for lint+test. The optional `eval-report` job runs informational (no `--gate`) on PRs. There is no hardening-gate step that blocks merge on a threshold miss — the CD template (`cd.yml.jinja`) was where gate enforcement was planned, but is not confirmed present.

**What diskoe adds:** the `--gate` flag in CI + the "blank API key = graceful heuristic-only" env pattern. The dependabot auto-merge job (gated on `needs: ci`) is also a reusable pattern for the AIT TS template.

---

### 7. Admin auth pattern

[Confidence: Medium — `diskoe/CLAUDE.md:64-65`]

Diskoe's admin auth is basic HTTP auth on `/admin/*` and `/api/admin/*` routes (`middleware.ts`), with a 503 when creds are unset. This is the "fail closed when env missing" pattern for admin surfaces. AIT has no admin scaffold. This is project-specific enough that it belongs in a future `include_admin_surface` copier flag, not as a default — noted here for completeness.

---

### 8. Schema conventions

[Confidence: Medium — `diskoe/CLAUDE.md:141-173`]

Diskoe codified six schema cluster names (`source`/`content`/`enrichment`/`interaction`/`product`/`account`) in `CLAUDE.md:148-154`. The "product vs interaction" test (`would deleting the row change what a user sees tomorrow?`) and the "every new column names its reader" rule are domain-specific but the meta-pattern belongs in a naming reference. AIT has `~/.claude/refs/naming.md` but no DB-cluster convention. This is out of scope for AIT to template (too Supabase/product-specific).

---

## Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `diskoe/.claude/specs/` three-doc split | ADAPT | Empty Jinja stubs (`design-scope.md.jinja`, `design-requirements.md.jinja`, `mvp-roadmap.md.jinja`) gated on a `include_spec_docs` copier question | Full diskoe spec docs are project-specific; the structure (three questions, ID discipline, contradiction register) is the template-worthy part |
| `diskoe/Makefile` `gate` target | ADAPT | Add `gate: lint typecheck test build` to `Makefile.jinja` alongside existing `ship` | AIT already has all constituent targets; the composite alias is one line |
| `diskoe/Makefile` `db-drift` target | SKIP | The "skip-without-creds, fail-loudly-when-reachable" pattern is salvageable as a comment/template comment in the Supabase scaffold's Makefile section | Target is Supabase-specific; AIT's scaffold has a `supabase/` directory but `db-drift` requires a custom migration checker that is diskoe-specific code |
| `diskoe/src/evals/` registry + targets convention | ADAPT | The `UNGATED` convention + `targets.yaml` comment rule belong in AIT's eval README template; the TS eval scaffold (registry/graders/fixtures) should mirror the Python scaffold structure | AIT has the Python eval scaffold; the TS side has no registry or targets.yaml — add `{{ ts_project_root }}/{{ ts_source_root }}/evals/registry.ts.jinja` and a `targets.yaml.jinja` |
| `diskoe/vitest.config.ts` regex alias fix | REUSE | Lift the regex alias form (`/^@\//`) into `template/_scaffold/{{ ts_project_root }}/vitest.config.ts.jinja` directly — it fixes a latent bug in the current template | AIT's template has the buggy bare-string form; this is a one-line fix |
| `diskoe/SANYI.md` | ADAPT | `SANYI.md.jinja` with the three-layer structure, placeholder Buyi (secrets gate) and Jianyi (module budget) entries, and the BY-4 comment | Full diskoe SANYI.md is project-specific; the skeleton + the "how to read" table is universal |
| `diskoe/.github/workflows/ci.yml` eval gate step | ADAPT | Add `npm run eval:grade -- --gate` step (with blank API-key env) to the TS CI template; add dependabot auto-merge job | AIT's Python ci.yml.jinja already has an informational eval job; the `--gate` flag and the graceful-degrade env pattern are missing from the TS variant |
| `diskoe/eslint.config.mjs` flat config | ADAPT | Copy the `ignores` block pattern (generated/vendored trees explicitly listed) and the `@next/eslint-plugin-next` over `eslint-config-next` rationale comment; gate on `ts_agent_framework == "vercel_ai_sdk" or nextjs` | Diskoe's full ESLint config is Next.js-specific; the ignores pattern and the rationale for avoiding `eslint-config-next` apply to any ESLint 9 flat-config TS project |
| `diskoe/.claude/docs/research/` convention | ADAPT | Add a comment in AIT's `CLAUDE.md.jinja` establishing the `docs/research/` (dated, `Status:`-stamped, never a contract) vs `specs/` (decisions, enforced) split | Diskoe's research docs are project-specific content; the directory-purpose discipline is the template-worthy norm |

## Open questions

1. **`include_spec_docs` copier question scope**: should the three-doc split be its own question, or folded into `project_type` (i.e., only product-shaped projects get spec stubs)? The answer changes whether AIT adds a new question or a conditional branch.

2. **TS eval scaffold completeness**: diskoe's `grade.ts` and `report.ts` pipeline scripts are non-trivial (~100+ lines each). Does AIT want minimal stubs (registry + targets.yaml + one fixture example) or full pipeline scaffolding? The Python eval harness went full; the TS side has been left thin.

3. **SANYI.md gating**: should `SANYI.md.jinja` be unconditional (every project gets it) or gated on a `include_change_contract` flag? Diskoe drafted its SANYI.md at project maturity, not genesis — templating it at genesis risks it being blank/ignored.

4. **Vitest regex alias fix**: this is a latent bug in the current AIT TS template (bare `'@'` alias does not rewrite trailing path segments). Should be fixed independently of any diskoe-parity work — confirm whether any existing rendered projects hit this.

5. **`gate` vs `ship` naming**: diskoe's Makefile comment (`ship` was written against a `Makefile.common` include that does not exist — `diskoe/Makefile:52-57`) reveals that AIT's shared `Makefile.common` include pattern is not present in diskoe at all. The `gate` target proposal is additive; does the parent session want to reconcile the `Makefile.common` include pattern as part of this work?
