Status: EXECUTED
Review: pending

# Review — galactus 2026-08-08

`/code-review level:2`. Repo has zero commits; every file is untracked on `main`
and there is no remote, so the changed set is the whole tree (24 source/test
files, 5,416 lines). No `SANYI.md` and no `CLAUDE.md` at the repo root — the
contract step is skipped, not failed.

### Mechanical
- Lint: **FAIL** — 3 × F401 unused imports (all auto-fixable)
- Tests: **PASS** — 259 passed in 2.00s

No Makefile, so this fell back to `uv run ruff check .` + `uv run pytest`.

```
F401  src/galactus/api.py:19    `typing.Any` imported but unused
F401  src/galactus/api.py:22    `pydantic.Field` imported but unused
F401  tests/test_generate.py:22 `galactus.models.LayoutTemplate` imported but unused
```

### Findings (ranked, canonical schema)

- **[important:verified]** `RW-001` `src/galactus/api.py:190` — the `role`
  column is written on upload and filterable in the store, but the generation
  pipeline never uses it; every PDF for a company is ingested as both sides.
  Evidence: `store.get_pdfs` takes `role: str | None = None`
  ([store.py:117](src/galactus/store.py#L117)) and both callers omit it —
  [api.py:144](src/galactus/api.py#L144) and
  [api.py:190](src/galactus/api.py#L190). `run_job` loops over
  `(sender_company_id, state.sender_facts)` and
  `(receiver_company_id, state.receiver_facts)` fetching by company id alone,
  so when one company has uploaded PDFs under both roles, its receiver-role
  PDF lands in `sender_facts` too. The upload endpoint validates `role`
  against `{"sender", "receiver"}` ([api.py:119](src/galactus/api.py#L119))
  and returns it in the 201 body, which tells a client the distinction is
  load-bearing. `test_store_filters_pdfs_by_role`
  ([test_api.py:267](tests/test_api.py#L267)) covers the filter at the store
  level, which is why the gap survives a green suite — no test exercises
  role-mixing through the API. Directly undercuts the stated design intent in
  `_render_facts`: "Sender and receiver facts are kept apart… a flat list
  invites the model to mix them"
  ([generate.py:280-285](src/galactus/generate.py#L280-L285)).
  Merge impact: important

- **[suggestion:verified]** `RW-002` `src/galactus/generate.py:298` —
  `_render_fact` renders a missing page as the literal `pNone` in the grounding
  block sent to the model. Evidence: `Fact.page` is `int | None`
  ([models.py:128](src/galactus/models.py#L128)) and vision-extracted facts can
  carry `None`; the f-string interpolates unconditionally. Cosmetic in the
  prompt, but it is prompt text the model reads as a citation.
  Merge impact: suggestion

- **[suggestion:verified]** `RW-003` `src/galactus/layout/fallback.py:239` —
  `_first_theme_color` calls `next(iter(template.theme_colors))` unguarded;
  a template declaring a `color_ref` field with an empty `theme_colors` dict
  raises `StopIteration` from inside the fallback path. Evidence: no validator
  in `LayoutTemplate` ties `color_ref` fields to a non-empty `theme_colors`.
  The shipped `two_column_brief.json` populates it, so this is unreachable
  today — but the fallback is the "guaranteed to produce a valid draft"
  escape hatch ([generate.py:227-229](src/galactus/generate.py#L227-L229)),
  and an uncaught `StopIteration` there fails the one path that must not fail.
  Merge impact: suggestion

- **[nit:verified]** `RW-004` `src/galactus/generate.py:52-55` — the
  `schema_for` docstring says length limits are emitted as
  "`maxLength`/`minLength`", but only `maxLength` is emitted
  ([generate.py:64-66](src/galactus/generate.py#L64-L66)). No correctness
  impact — `validate()` independently enforces word and char counts — but the
  docstring overstates what the schema constrains.
  Merge impact: nit

- **[nit:verified]** `RW-005` `src/galactus/layout/validator.py:81` — the
  `field` parameter of `_check_text` is unannotated, implicitly `Any`, in a
  package that ships `py.typed`.
  Merge impact: nit

**Dropped during verification** (raised by scan agents, did not survive):
- *"Receiver PDFs are not validated at request time like sender PDFs"* —
  proposed as a blocker. Not a defect: receiver context is optional by design.
  `_render_facts` skips empty sides, and
  [test_api.py:194](tests/test_api.py#L194) asserts 404 for a missing *sender*
  only. Verifying this claim is what surfaced RW-001, which is the real issue
  in the same code path.
- *"Read-modify-write race in `update_job`"* — `update_job` is called only
  from `run_job`, once per job, sequentially per background task. No concurrent
  writer to the same `job_id` exists.
- *"`ScriptedEvalLLM` ignores its `schema` argument"* — intentional in a
  deterministic dry-run fake; the template is the authority there.

### Contract (SANYI)
No `SANYI.md` — skipped.

### Docs
- Machine-consumed: none present (no `CLAUDE.md`, no `.claude/` before this
  report). No proposed diffs.
- Human-consumed: `README.md` is **0 bytes** on a repo with a working API,
  eval harness, and 259 tests. Flagged, not edited (doc-writer boundary).
  [docs/cap-reuse.md](docs/cap-reuse.md) is the only prose in the repo.

### Verdict
**needs-changes** — lint fails on 3 unused imports (`ruff check --fix` clears
all three), and `RW-001` means the sender/receiver separation the prompt
layer is built around does not hold end-to-end. Nothing here threatens the
259 green tests; RW-001 needs either a `role=` argument at
[api.py:190](src/galactus/api.py#L190) or an explicit note that role is
upload metadata only.
