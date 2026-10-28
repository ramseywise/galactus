# resolve-capability registry gap

Status: READY
Track: agent
Issue: ramseywise/galactus#39

---

## Bug

`resolve_capability_agent` (`review/phases.py:257-331`) reports `resolved: true` when:

1. The agent file exists at `Path(repo_root) / agent_path`
2. The file has valid YAML front matter
3. The `name:` field matches the filename stem

None of these conditions check whether the session's agent registry has loaded that agent.
The registry loads `.claude/agents/` from the **session root directory**, not from `repo_root`.
When the session is rooted at `~/workspace` and galactus is at `~/workspace/galactus`, the
registry does not see `galactus/.claude/agents/fog-advisor.md`, but the check passes because
it resolves the file path relative to CWD (which is galactus).

Observed symptom: `uv run python -m review.cli resolve-capability fog` exits 0 / `resolved:
true` from within `~/workspace/galactus`, then `fog-advisor` dispatch fails with "Agent type
not found."

The function docstring at `phases.py:261-279` names this exact failure mode — the guard
exists to catch it and instead replicates it.

---

## Root cause (precise)

`resolve_capability_agent` answers: "Is there a well-formed file here?"
The caller needs: "Will a dispatch naming this agent resolve in this session?"

These are the same question only when the session root equals `repo_root`. That is not
guaranteed and is not the common working pattern (working from `~/workspace` is standard).

`--repo-root` defaults to `"."` in the CLI (`cli.py:321`). The skill invocations in
`proto-refine/SKILL.md:162` and `fog/SKILL.md:130` call the command with no `--repo-root`
argument — they rely on CWD being the repo root, which is true when the session is rooted
at galactus but false otherwise.

---

## Fix approach

**Option A — emit the topology in the resolution payload** (chosen)

Add a `repo_root` field to the JSON output of `resolve-capability`, reporting the absolute
path the check was answered against. The caller (skill or human) can then see whether the
check was meaningful.

Additionally, add a `session_root_mismatch` boolean: True when `Path(repo_root).resolve()`
differs from `Path(".").resolve()` at call time (i.e., `repo_root` was explicitly provided
and differs from CWD, or CWD differs from what it would need to be for the registry to load
that directory).

Separately, the skills must pass `--repo-root` explicitly. Since the skills run as Bash
tool calls, the correct value is the galactus repo root, which is knowable at skill
invocation time (it's where `.claude/agents/` lives relative to the work item).

**Why not Option B (probe the registry directly)?**

Claude Code's agent registry is session-level state managed by the host process. There is
no Python API to query it from within a subprocess — `uv run` runs in a child process with
no access to the parent session's loaded registry. The registry membership is not written
to disk in a queryable form. This avenue is closed.

**Why not Option C (attempt a test dispatch)?**

A test dispatch has side effects and cost. It is not suitable as a precondition check.

**Why not Option D (document the constraint only)?**

The constraint already appears in the docstring and was still violated. Documentation-only
fixes are the failure mode this codebase explicitly rejects (`phases.py:15-16`, CLAUDE.md:
"a rule you rely on belongs in a hook, not here"). The guard must emit evidence the caller
can act on.

---

## Files to change

### `review/phases.py`

`resolve_capability_agent` (lines 257-331): add `repo_root_abs` to the return dict,
containing `str(Path(repo_root).resolve())`. This makes the assumed topology visible in the
payload without changing the resolution logic.

No change to the resolution logic itself — it correctly answers the file-existence question.
The fix is making the scope of the answer explicit so a caller that needs the registry
question can see the gap.

### `review/cli.py`

`_cmd_resolve_capability` (lines 170-206): include `repo_root_abs` from the result in the
JSON output. Also add a `cwd` field (`str(Path.cwd())`) so the payload shows both the
resolved repo root and the current working directory — the mismatch between these is the
signal.

### `.claude/skills/proto-refine/SKILL.md`

The Stage 3 gate (lines 159-181): update the instruction to state that if the payload's
`repo_root_abs` does not match the galactus checkout path, the resolution is invalid. Add
the explicit `--repo-root` flag to the command block:

```bash
uv run python -m review.cli --repo-root ~/workspace/galactus resolve-capability fog
```

This makes the check session-topology-independent: it always answers against the galactus
`.claude/agents/` directory, regardless of where the session is rooted.

### `.claude/skills/fog/SKILL.md`

Same change at Stage 4 (lines 128-130): add `--repo-root ~/workspace/galactus` to the
resolve command.

### `review/tests/test_phases.py`

Add two tests in the "capability resolution: the #15 collapse" block (after line 481):

1. `test_resolve_capability_includes_repo_root_in_payload` — asserts the returned dict
   contains `repo_root_abs` as a non-empty string and that it equals
   `str(Path(repo_root).resolve())` when `repo_root` is `tmp_path`.

2. `test_cli_resolve_capability_payload_includes_cwd_and_repo_root` — drives `main()` with
   `--repo-root <tmp_path>` and asserts the JSON output contains both `repo_root_abs` and
   `cwd` as strings.

---

## Test plan

1. Existing tests must all still pass: `uv run pytest review/tests/test_phases.py -v`
2. New test for `repo_root_abs` in returned dict (unit, `tmp_path`)
3. New CLI test for `cwd` + `repo_root_abs` in JSON output
4. Manual smoke: `cd ~/workspace && uv run python -m review.cli --repo-root galactus resolve-capability fog` should exit 0 with `repo_root_abs` pointing at the galactus checkout, confirming the fix works from a parent-rooted session.
5. Negative smoke: `cd /tmp && uv run python -m review.cli resolve-capability fog` should exit 1 (file not found), and the payload's `repo_root_abs` should confirm `/tmp` was checked.

---

## Risks & rollback

**Risk**: `repo_root_abs` in the payload is a new field — any caller parsing the JSON by
exact key set would break. Callers in the skills use the `resolved` bool and `reason`
string only; no caller validates the full key set. Addition is safe.

**Risk**: hardcoding `~/workspace/galactus` in the skill is machine-local. The skills
already assume galactus is the working repo (they call `uv run` which requires a
pyproject.toml). This assumption is not new; making it explicit reduces ambiguity.

**Rollback**: revert the two skill edits and the `phases.py` / `cli.py` additions. The
behaviour reverts to the current state (file-existence check, no topology info). No schema
version or DB migration involved.

---

## Steps

- [ ] Edit `review/phases.py:resolve_capability_agent` — add `repo_root_abs` to all return
      dicts (both success and failure paths).
- [ ] Edit `review/cli.py:_cmd_resolve_capability` — include `repo_root_abs` and `cwd` in
      JSON output.
- [ ] Add two tests to `review/tests/test_phases.py` (unit + CLI surface).
- [ ] Run `uv run pytest review/tests/test_phases.py -v` — all pass.
- [ ] Edit `.claude/skills/proto-refine/SKILL.md` — add `--repo-root ~/workspace/galactus`
      to the resolve command and add a paragraph explaining the topology check.
- [ ] Edit `.claude/skills/fog/SKILL.md` — same change at Stage 4.
- [ ] Manual smoke tests (from `~/workspace` and `/tmp`).
