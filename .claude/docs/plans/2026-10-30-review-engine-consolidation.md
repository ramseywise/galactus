# Review engine — one implementation, guacamayo's

Status: PLANNED
Date: 2026-10-30
Issue: — (none yet)

Decided in the 2026-10-30 audit: keep galactus and guacamayo separate, merge only the
review engine. The largest of the four sibling plans; land it last.

## Research

Direct inspection, 2026-10-30.

| | guacamayo `src/review` | galactus `review/` |
|---|---|---|
| Size | about 3500 lines | about 2100 lines |
| CLI | click, `review-cli` script | argparse, `python -m review.cli` |
| Shared subcommands | validate-finding, detect-signals, resolve-capability, verdict | same four |
| Unique subcommands | validate-report, verify-commits, render-report, fingerprint, trends, run | track/detect-track, derive-phases, metrics |
| Tests | in guacamayo `tests/` | `review/tests/`, 172 tests, in galactus `testpaths` |

- **Schemas are compatible.** Reporter enum values match (`silent_failure`). guacamayo adds
  `wander`, `lint`, `plan_fidelity`, and deprecated `akira_scan`, `akira_wander`, `sanyi`.
- **Dimension text lives in two places,** both with `prefix:` frontmatter:
  galactus `review-shared/dimensions/review-<dim>.md`, guacamayo `skills/review-<dim>/SKILL.md`.
  Both repos already call galactus canonical for dimension vocabulary.
- **Callers.** galactus `proto-refine`, `proto-review`, `proto-execute`, `review-shared`
  call `review.cli`. guacamayo `workflow-review` and `fog` call
  `uv run --project ~/workspace/guacamayo review-cli`.
- **`phases.py` and `transitions.py`** encode galactus's `Status:` machine. They are not
  review logic and stay in galactus.
- **Import-name collision.** Both packages import as top-level `review`. guacamayo ships it
  via `packages = ["src/review", ...]`. galactus is `package = false` and imports its
  `review/` from the repo root. A path dependency on guacamayo would put two `review`
  packages on one `sys.path`.

### Addendum, found at the start of execution (2026-10-30)

The premise above, that guacamayo's engine is a superset, is wrong. Each side is ahead in
different modules, so this is a two-way merge, not a deletion:

| Module | Ahead | Why it matters |
|---|---|---|
| finding validation | galactus `validate.py` (199 lines) vs guacamayo `validation.py` (36) | galactus checks quoted spans against the file and spec citations; guacamayo only schema-validates |
| signals | galactus `signals.py` (471) vs guacamayo (213) | galactus adds `detect_track`, `detect_injection`, and a `skipped` reason map |
| `active_dimensions` contract | — | galactus returns `{active, skipped}`; guacamayo returns `list[str]`. `/proto-review` §11 depends on the skip reasons |
| enums | galactus has `Phase`, `Capability`; guacamayo has `Attribution`, report and trend models | |
| run, attribution, fingerprint, trends, render, static analysis | guacamayo only | |

S2 and S6 as written would delete the quoted-span check and injection detection. Execution
stopped here; nothing in this plan has been changed. Needs re-planning before refine.

## Plan

Based on: direct codebase inspection (Research above).

**S1. Resolve the name collision first.** Rename galactus's remaining package from
`review` to `pipeline` (it will hold only `phases`, `transitions`, `track`). Update its
callers and tests. Land and verify this alone before anything else moves.

**S2. Port galactus-only review behaviour into guacamayo.** `metrics` moves into
guacamayo's CLI, with its tests. Diff the four shared subcommands' behaviour against
galactus's tests; any galactus test that fails against guacamayo's implementation is a
gap to close in guacamayo, not a test to delete.

**S3. Depend, don't shell out.** galactus `pyproject.toml` gains
`guacamayo = { path = "../guacamayo", editable = true }` via `uv add --editable ../guacamayo`.
galactus skills call `uv run review-cli <cmd>`. guacamayo's `workflow-review` and `fog`
lose `--project ~/workspace/guacamayo` when run inside guacamayo.

**S4. Point the driver at galactus dimensions.** guacamayo's `DriverConfig.skills_dir`
gains a way to read dimension files from galactus `review-shared/dimensions/`. guacamayo's
`skills/review-<dim>/SKILL.md` become symlinks or are removed; decide in refine after
diffing the two formats.

**S5. `/proto-review` calls `review-cli run`.** Its manual fan-out becomes one call, with
`plan_fidelity` as a reporter.

**S6. Delete galactus duplicates.** `review/models.py`, `validate.py`, `signals.py`,
`verdict.py`, and their tests once each has a passing counterpart in guacamayo. Remove
`review/tests` from `testpaths` only after the counterpart tests are collected in
guacamayo.

### Verification

- galactus `uv run pytest -q`: no drop in collected tests other than the ported ones; 0 failed.
- guacamayo `uv run pytest -q`: count rises by the ported tests; 0 failed.
- `uv run python -c "import review, pipeline; print(review.__file__)"` in galactus points
  into guacamayo.
- `/proto-review` on a small diff produces a verdict identical in shape to today's.
- `grep -rn "python -m review.cli" galactus/.claude` → none.

### Open Questions

- Q1 (S4): the two dimension-file formats differ. Which wins where they conflict?
- Q2: guacamayo's `wander` and the deprecated reporters. Drop the deprecated three during
  the port, or keep them for reading old findings?
- Q3: galactus CI then needs guacamayo checked out beside it. Check out guacamayo in the
  workflow, or depend on a git URL in CI?
