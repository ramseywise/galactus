# Context Brief

The input every reporter receives. Assembled once by the orchestrator and passed to all
reporters, so that three reporters do not each re-derive the same diff — and, more
importantly, so they all review **the same** diff.

## Why it is assembled once

Reporters run in parallel with separate context windows. If each gathers its own context,
they drift: one reads the working tree, another reads `HEAD`, a third reads the PR diff,
and their findings cannot be merged because they do not describe the same code. The brief
is the shared ground truth.

## Contents

| Field | Source | Notes |
|---|---|---|
| `diff` | `git diff main...HEAD`, or `gh pr diff <n>` | Three-dot: changes on the branch, not changes to main |
| `changed_files` | Derived from the diff | Paths, relative to repo root |
| `changed_symbols` | Function/class names touched | Feeds the caller lookup below |
| `callers` | Grep for each changed symbol | The most common source of missed blast radius |
| `repo_context` | `CLAUDE.md`, `SANYI.md` if present | Conventions the diff must satisfy |
| `plan_doc` | `.claude/docs/plans/*.md` matched by slug or branch | Absent for `bug/` and `spike/` branches |
| `ci_status` | `gh pr checks <n>` | PR mode only |
| `profile` | Inferred: `general` or `agent-system` | See below |

## Review profile

`agent-system` if any changed file imports an LLM or agent framework, or lives under
`agents/`, `*_agent/`, or `prompts/`. Otherwise `general`.

The profile changes what reporters look for, not how hard they look. An `agent-system`
diff gets the prompt/context/harness/loop/graph questions from `.claude/specs/agent-*.md`
applied on top of the general correctness pass.

## Empty-input rule

**A brief with an empty diff is an error, not an empty review.** Fail loudly and stop.

A reporter handed nothing will return no findings, and no findings is indistinguishable
from a clean review — so a broken diff command reads as an approval. Every silent version
of this bug has survived far longer than it should have, because its output looks exactly
like success.
