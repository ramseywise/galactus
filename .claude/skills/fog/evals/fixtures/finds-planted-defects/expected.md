# Expected — /fog on the `digest` spec

The fixture is a **plan-stage spec** (`input/SPEC.md`) for a weekly research-digest
service. It is deliberately competent: several uncertainty questions are answered
*correctly*, and four are answered badly. A good fog run separates them.

This case grades **precision as hard as recall.** A run that reports all four planted
defects but also flags the three negative controls has demonstrated the failure mode the
skill's own "Failure modes" section names — producing fog rather than locating it.

---

## The four planted defects

### D1 — Collapse site: `fetch_new_papers` swallows a category failure (§2.1)

`except Exception: continue` means a category that is **down** contributes zero papers,
and zero papers from a down category is byte-identical to zero papers from a quiet week.
The `continue` is justified in the spec's own prose ("one flaky category should not sink
the whole digest") — that justification is the tell, not an exoneration. The caller
believes it received a complete week; it received seven-eighths of one, and nothing in
the return type says which.

Maps to fog **Stage 2** (collapse sites) and the spec's four-row table: this is row 4,
*ran, answered from nothing*, being reported as row 1.

A strong run also notes this interacts with D4: the zero-send pager cannot fire here,
because the other seven categories still produce sends.

### D2 — Collapse site: `match_topics` empty → skip, indistinguishable from failure (§2.2)

A subscriber who matches nothing gets no email. A subscriber whose model call **errored,
returned malformed output, or matched nothing because D1 starved the input** also gets no
email. Three states, one observable outcome, and the outcome is silence — the hardest
failure to notice because nobody receives a complaint about an email they didn't know to
expect.

Maps to **Stage 2**. Strong runs name the fix shape: distinguish `matched_none` from
`match_failed` as typed states, the way §2.4 already does for `Summary`.

### D3 — Irreversible, unstaged: the topic-taxonomy migration drops the source column (§3)

`topics_freetext` is dropped **in the same release** as the backfill that reads it. Once
dropped, there is no way to re-derive `topic_ids` if the encoding is wrong — the input to
the migration no longer exists. "It ran in 40 seconds on a prod copy with no errors"
establishes that it *completes*, not that it is *correct*; a mis-encoding completes
cleanly too.

Maps to fog **Stage 3** (reversibility). Per the skill: irreversible-and-unstaged is
`fatal` **regardless of confidence** — a run that downgrades this because the rehearsal
succeeded has made exactly the error Stage 3 warns about ("confidence does not shrink
blast radius").

The staging that fixes it is nameable and a strong run names one: keep the column for a
retention window, or backfill-and-verify in one release and drop in the next.

Note the trap: §5 offers `DIGEST_ENABLED` as "our rollback." It is a rollback **for the
send path only** and does nothing for a dropped column. A run that reads §5 as covering
§3 has been taken in by the spec.

### D4 — Missing detector: no mechanism would notice a quality regression (§4, §6)

§4 checks summary quality **once, before launch** (28/30, two reviewers). §6 monitors
duration, send failures, and zero-send runs — all liveness signals. Nothing observes
whether the summaries are still accurate in week 30. If `summarize` degrades — model
change, prompt drift, abstracts getting longer and silently truncated — every alert stays
green and 1,800 people receive confident, wrong two-sentence summaries.

Maps to fog **Stage 1** (name the *absence of the detector*, not the surprise) and to
**Stage 6**'s closing question: *how would this system learn it was wrong, and would
anything change if it did?* The answer here is that it would not learn, and nothing
would. A strong run raises this as its own standalone finding, per Stage 6's instruction.

Also in scope for D4, and worth credit if raised: §4's launch check is the only quality
gate for a **chain** of three model calls (§2.2 match → §2.3 rank → §2.4 summarize), and
it only grades the last one. `match_topics` and `rank_by_relevance` have no accuracy
check at any point, before or after launch.

---

## The three negative controls — flagging these is a precision failure

These are places the spec **handles uncertainty correctly.** They are written to look
like the defect classes above so a pattern-matching run trips on them.

### N1 — `summarize` abstention is typed and preserved (§2.4)

`Summary = Ok(text) | Unavailable(reason)`, and `render_email` must handle both arms; the
paper still renders with title and link. This is `agent-uncertainty.md` §2's rule
implemented correctly — the abstention is a *typed field the next component must handle*,
not prose it may ignore. **Do not report this as a collapse site.** Reporting it means the
run matched on the word "unavailable" rather than on the mechanism.

### N2 — `send` idempotency is real and named (§2.6)

The `(subscriber_id, week)` row is written **before** the SendGrid call and is
unique-constrained in Postgres. That is a named mechanism in the harness, not a promise in
a prompt — it satisfies Stage 3's "name the branch, the flag, the retention window" test.
**Do not report double-send risk here.** (Reporting the *inverse* — that a pre-write plus
a failed send yields a paper marked sent that nobody received — is a legitimate, more
sophisticated finding and should be credited if raised, but it is not the same claim as
"there is no idempotency.")

### N3 — the 900-character cap is deterministic (§2.5)

Counted in code, in a Jinja template, with truncation. This is the repo's own thesis
applied correctly (`CLAUDE.md`: *counting characters is a job for code*). **Do not report
this under Stage 5** as a probabilistic step that should be deterministic — it already is
one. A run that flags it has inverted the stage.

---

## What a good run does

1. Fills all four quadrants in Stage 1, including unknown-knowns. The spec never consults
   `agent-uncertainty.md`, whose §2 collapse rule D1/D2 violate directly and whose §4
   least-commitment rule D3 violates — that is an unknown-known (the repo holds the rule;
   the design did not reach it), and naming it is the highest-yield Stage 1 output.
2. Reports D1–D4, each grounded in a specific section of `SPEC.md`. Per the skill's own
   failure modes, an ungrounded claim should have been dropped.
3. Ranks **D3 at `fatal`** and does not downgrade it for the successful rehearsal.
   Impact-major, confidence-minor throughout (`claim-schema.md`).
4. Leaves N1, N2, N3 unflagged — or, at most, mentions them explicitly as *handled*, which
   the advisor's brief permits ("if a pass produces nothing because the design genuinely
   handles it, say so explicitly").
5. Dispatches `fog-advisor` with the spec and **no** stage 1–3 findings, then merges by
   mechanism — D1/D2/D3 are exactly the overlap the skill says the advisor's empty-input
   and reversibility passes should independently reproduce. Corroboration on those is the
   check working; both ids (`FOG-NNN` + `FA-NNN`) are retained on a merged finding.
6. Emits the three required closing lines, and the third — **what this pass could not
   see** — is substantive. There is real blind material here: no code exists yet (the spec
   is PLANNED), so every claim about `_page_all`, the SendGrid client, and the migration
   script is about described behavior and not observed behavior. A run that reports no
   blind spots on a spec for unwritten code has demonstrated the failure the line exists
   to catch.

## What a BAD run looks like (grade down)

- **Flagging N1, N2, or N3.** The precision failure. A skill that flags everything is as
  useless as one that flags nothing.
- **Downgrading D3** below `fatal` because §3 says the rehearsal passed, or because §5
  mentions a flag (that flag does not cover the migration).
- **Enumerating unknown-unknowns** — naming specific surprises rather than reporting the
  absence of a detector (D4's correct shape).
- **Briefing the advisor** with the inline findings, then reporting its agreement as
  independent corroboration.
- **Reporting a clean pass, or an all-`speculative` finding set.** Every claim here is
  groundable in a numbered section; a pass that cannot ground them has generated fog
  rather than located it.
- **Omitting or trivializing the blind-spots line** ("none identified" on a spec whose
  code does not exist).
