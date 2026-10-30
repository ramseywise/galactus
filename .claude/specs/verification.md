# Verification — what counts as evidence that a change landed

*Authored 2026-09-03. Unlike its neighbours this ref was not restored: no copy existed in
`~/.claude`, in `~/workspace/guacamayo/.sounding/refs/`, or in any git history on this
machine, while `diskoe/CLAUDE.md:3` had cited it since the first commit. It is written from
the incidents already recorded in `~/workspace/diskoe/CLAUDE.md` (§Schema conventions) and
`~/workspace/guacamayo/.claude/skills/meta-retro/SKILL.md` (Step 0.3) — each rule below is
earned by a defect one of these repos actually shipped, and the citation is the evidence,
not decoration.*

**The one idea.** A change is verified when a command you can re-run *now* shows the new
state. Everything else — the file existing, the task being checked off, a status column
saying so, your own memory of doing it — is a claim.

---

## 1. Re-derive, never re-read

A row whose Status says "done" is a claim, not evidence. A row verified from its own status
column is unverified. Prose decays the same way: guacamayo's retro loop twice read "metric
met" from ledger text while the live command showed zero matches, undetected across two
windows. **Run the command. Paste the command and its output.** A number without a
re-runnable command is not evidence.

## 2. The artifact existing is not the artifact working

- A migration file in the tree is not a migration that ran. Three separate times a
  migration was marked DONE while its column did not exist — most expensively
  `202608310001`, which merged to main unpushed and took down every
  `/api/recommendations` call in production because `EVENT_COLUMNS` selected a column that
  was not there.
- A plan doc, an issue closed COMPLETED, a green checkbox: all claims. Verify the artifact,
  not the state.

## 3. A check that cannot fail is not a check

- **Silently skipping is failing.** A drift check that no-ops when it has no credentials
  reports green on an unchecked history — that is precisely how the outage above got past a
  green gate. Fail; require an explicit env var to acknowledge a deliberate skip.
- **A check must be able to see all forms of its violation.** A grep for `font-size="13"`
  cannot see `style="font-size:13px"`; ten inline overrides accumulated undetected while the
  check reported clean. When you write a check, first write the violation two ways and
  confirm it catches both.
- **A check must say *why* it failed.** A bare `catch` that prints "check network/auth"
  cannot distinguish a real drift from an expired login, so the recorded cause was an
  unapplied migration when the actual blocker was `supabase login` — and acting on that
  diagnosis would have pushed into "column already exists". A check that cannot name its
  own failure points at the wrong repair, which is the same defect class as one that
  silently passes.

## 4. Verify in a way that cannot be intercepted

An undeclared trigger once made a passing probe meaningless. Ask what sits between your
probe and the thing you believe you are testing — a default, a cache, a fallback, a
middleware, a mock. Then probe past it. Never verify against production data with a
destructive probe.

## 5. Guards match on names, not intent

`create unique index if not exists` against a same-named *non-unique* index skips silently
and enforces nothing — recorded as applied while the invariant was never in force. Where a
change must alter an existing object, drop-then-create is the only honest form.

## 6. Green does not mean covered

`tsc`, lint and 524 tests were all green while a code review found seven real defects,
because every API route handler and the I/O layer had no tests. A green gate says the pure
functions are correct; it says nothing about the shell around them. Before trusting a suite,
ask which layer it actually exercises.

## 7. Fail before you fix

A test that has never failed has not been shown to test anything. Watch the new test fail
against the unfixed code, then fix. Same for a check, a hook, or a lint rule.

## 8. State the corpus and the denominator

"19k antipatterns" means nothing without total calls — always report `n / total (pct%)`.
Say the bounds of what you measured before the number, and say when the raw data behind a
window is already gone. Count the right unit: per-command and per-occurrence-within-command
differ by an order of magnitude, and that gap is the first thing to check when a magnitude
looks implausible.

## 9. Claims have an expiry

A build-state row saying `BUILT` is only as good as its last verification date. Re-verify
against the tree and restate the date, or mark the row unverified. Never copy a stale row
forward.
