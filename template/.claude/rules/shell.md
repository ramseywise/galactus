# Shell (zsh) — gotchas for agent-run commands

The interactive shell is zsh; compound commands die on these in ways that silently skip
later steps:

- No `echo ===X===` section markers — zsh parses leading `=word` as an `=command` path
  expansion and aborts. Use plain words: `echo DONE1`, `echo CHECK2`.
- Guard globs that may not match — zsh nomatch aborts the whole compound command the
  moment the glob expands (even mid-loop). Prefer `find` over bare globs, or
  `ls pattern 2>/dev/null`, or append `(N)` null-glob qualifiers.
- Paths containing literal `{{ }}` (copier templates) must be quoted.
- No `timeout` on macOS by default (it's GNU coreutils, not BSD) — `timeout 60 cmd` dies
  with `command not found`, and in a compound command that kills every step after it. Use
  the Bash tool's own `timeout` parameter instead of wrapping the command.
- After any aborted compound command, re-verify which steps actually ran — never assume
  the prefix completed.
- Prefer `git rm --cached` over `rm` for bulk file operations — untracking preserves
  files locally and in reflog. Always check `git ls-files` before any bulk delete to
  know what's tracked. The `.claude/docs/` deletion proved this: git-ignored files have
  no history to restore from.
- Git hooks run via `/bin/sh`, not zsh — `/opt/homebrew/bin` is NOT on PATH. Git-LFS
  pre-push hooks fail with "git-lfs not found." Fix: global template
  (`~/.git-templates/hooks/pre-push`) prepends Homebrew PATH. If a new repo has the
  error, copy the template hook or run `git init` to pick it up.

## Quota masquerade

Account usage exhaustion surfaces as `error_max_turns` or silent empty results from the
Agent SDK — indistinguishable from agent logic failures at the API level. Before
debugging agent behavior, check quota state. SDK-level `error_max_turns` in a low-turn
session is a quota signal, not a turns signal.
