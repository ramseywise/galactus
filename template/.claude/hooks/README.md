# .claude/hooks/ — session enforcement

Shell hooks wired through `.claude/settings.json`, run automatically by Claude
Code around tool calls. Blocking hooks exit 2 (the agent must fix before
proceeding); advisory hooks exit 0 with a warning. `lib.sh` holds shared
helpers and is sourced by the others — it is not a hook itself.

Hooks with a `.jinja` suffix are Copier templates — they render conditionally
based on project config (e.g. `ts_quality.sh.jinja` only renders when the
project has TypeScript). Plain `.sh` hooks ship unconditionally.

| Hook | Trigger | Behavior |
|---|---|---|
| `secrets_scan.sh` | Pre Write/Edit | Blocks writes containing API keys, tokens, or credentials. |
| `branch_guard.sh.jinja` | Pre Bash (`git commit`) | Blocks commits on non-main branches whose name lacks a ticket reference (see `ticket_prefix` in CLAUDE.md). |
| `risky_git_guard.sh` | Pre Bash (`git`) | Blocks force-push, hard reset, `clean -fd`, interactive rebase, forced branch delete/checkout. |
| `code_quality.sh.jinja` | Post Write/Edit | Enforces baseline Python standards in the source tree. Blocking. |
| `sdk_lint.sh.jinja` | Post Write/Edit | Enforces AI-SDK best practices (Anthropic, Google Gemini) in the source tree. |
| `test_coverage.sh.jinja` | Post Write/Edit | Warns about public functions without tests. Advisory only. |
| `public_api_test_check.sh.jinja` | Post Write/Edit | Checks edited public APIs in the source tree have matching test coverage. |
| `function_complexity_warning.sh.jinja` | Post Write/Edit | Warns when an edited Python function exceeds complexity limits. |
| `docs_hygiene.sh` | Post Write/Edit (markdown) | Flags stale/duplicated doc patterns. |
| `docs_scope_guard.sh` | Pre Bash | Blocks staging/committing `.claude/docs/plans/` and `.claude/docs/reviews/` — those are local scratch, not durable project knowledge. |
| `memory_duplication_guard.sh` | Pre Write/Edit (CLAUDE.md / memory) | Prevents saving facts that duplicate existing CLAUDE.md/memory content. |
| `structure_guard.sh.jinja` | Pre Write/Edit/Bash | Enforces the canonical eval-suite directory layout. Present only for eval-suite/RAG-shaped projects. |
| `ts_quality.sh.jinja` / `ts_typecheck.sh.jinja` | Post Write/Edit (TS files) | TS standards checks / `tsc --noEmit`. Present only when the project has TypeScript. |
| `ts_lint.sh.jinja` | Post Write/Edit (TS files) | Real eslint run over the TS project. Present only when a TS backend is scaffolded. |

Commit-time gates (run tests before `git commit`) are wired inline in
`.claude/settings.json`, not as separate scripts here. Git-level enforcement
for humans without Claude Code lives in `.pre-commit-config.yaml`, reading the
same `[tool.ruff]` config.
