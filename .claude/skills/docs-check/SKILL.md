---
name: docs-check
description: "Check if human-consumed docs (README, DESIGN.md) are in sync with the actual codebase structure, and optionally fix them. Use when code changed and docs might be stale, or for a standalone audit. Triggers on: 'docs check', 'are docs up to date', 'check README', 'docs drift', 'docs audit', 'fix docs', 'update README'."
---

# Docs Check

Detect drift between human-consumed docs and actual codebase structure. Three modes:

- **diff mode** (default): check only directories/files touched by recent changes
- **full mode** (`$ARGUMENTS` contains `full`): audit all docs in the repo
- **fix mode** (`$ARGUMENTS` contains `fix`): audit then apply mechanical fixes

## Fix mode — what it touches

Fix mode applies **mechanical, verifiable fixes only** — the same class as `/sanyi review --fix`
(behavior-preserving relocations). Edits land in the working tree, never committed (Ramsey commits).

| Fix type | Example | Applied automatically |
|----------|---------|----------------------|
| **Count update** | "21 skills" → "26 skills" (counted from disk) | Yes |
| **Dead reference removal** | Row referencing deleted `_mcp_ts/` dir | Yes — remove or mark historical |
| **Missing row/section** | New file/dir exists, not in layout table | Yes — add row with path + one-line description |
| **Stale name** | Hook listed without `.jinja` suffix | Yes — update to match actual filename |

**NOT auto-fixed** (flagged in report for human decision):
- Prose rewrites (changing how something is described)
- Section reorganization
- Anything requiring judgment about what to emphasize

## Steps

### 1. Discover docs

```
Glob: **/README.md
Glob: **/DESIGN.md
Glob: **/ARCHITECTURE.md
```

Skip: `node_modules/`, `.venv/`, `vendor/`, `dist/`, `build/`, `.git/`.

### 2. Determine scope

**Diff mode**: `git diff --name-only HEAD~5..HEAD` (or `--cached` + unstaged). Identify which
directories had code changes. Only audit docs in or above those directories.

**Full mode / Fix mode**: audit every doc found in Step 1.

### 3. For each doc in scope

Read the doc. Then check:

#### 3a. Structural references
Extract all path-like references (directory names, file names, module references).
Compare against the actual tree (`ls`, `Glob`). Flag:
- **Dead reference**: doc mentions a path/dir/file that no longer exists
- **Missing coverage**: a top-level or significant directory exists but isn't mentioned in the nearest README
- **Renamed**: a referenced name looks like a prior name of something that exists under a different name

#### 3b. Section accuracy
For sections that describe architecture, project structure, or directory layout:
- Does the described structure match reality?
- Are there new directories/modules not reflected?
- Are described entry points (main files, CLI commands, API endpoints) still valid?

#### 3c. Dependency/tool references
Check if referenced tools, frameworks, or commands still exist:
- Package names in prose vs `package.json` / `pyproject.toml`
- CLI commands described vs what's actually available (`Makefile`, `scripts/`)
- Config file references vs what exists

### 4. Apply fixes (fix mode only)

For each finding classified as mechanically fixable:
1. Read the target file
2. Apply the edit (Edit tool for surgical changes, Write for rewrites)
3. Record what was changed in the report

### 5. Report

```markdown
## Docs Check — [repo] [date]

**Mode**: diff / full / fix
**Docs scanned**: N

### Fixed (fix mode only)
- `path/README.md:L42` — updated count from 21 to 26
- `path/README.md:L228` — removed dead reference to `_mcp_ts/`

### Remaining (needs human decision)
- **[Stale]** `path/README.md:L15` — prose describes old architecture
- **[Gap]** `README.md` — new module not documented

### Summary
N docs checked · X fixed · Y flagged · Z ok
```

### 6. Integration hooks

If invoked by `/workflow-review`, append findings to the review report under a
`### Docs Drift` section (flag mode only — never auto-fix during review).
