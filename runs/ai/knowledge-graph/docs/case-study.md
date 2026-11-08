# Case study: OntoSmith's method, rebuilt at the triple grain

OntoSmith (MIT, Dongbum Lee; see `THIRD_PARTY.md`) builds knowledge graphs from documents
under a contract: a pack defines the types, a cheap model proposes, deterministic checks
filter, a stronger model judges, and a priced rule decides what is kept. This run rebuilds
that method inside galactus. It is written from OntoSmith's whitepaper and documents, not its
code, and the grain is one triple with its verbatim quote.

## Why the triple grain

Librarian, the wiki this runs over, already has 6,821 author-typed page-level edges
(`[[Target]] — extends`) and expands retrieval along two of them. A page-level graph is
already there. What it lacks is the sentence-level fact with a quote you can check, so that
is what this run builds.

## Taken from OntoSmith

| Element | OntoSmith | Here |
|---|---|---|
| Pack | `pack.json` per domain, versioned | `packs/eval-v1.json`, Pydantic contract, sha256 over canonical JSON, approval bound to the hash (`kg/contract/`) |
| Proposer / judge split | cheap proposer, stronger blind judge | Haiku proposer; Sonnet judge behind a `JudgeSeat` protocol. The judge prompt carries no proposer reasoning |
| Gates before the judge | deterministic filters | four pure functions: quote verbatim, entities attested in the quote, schema conformance, dedupe (`kg/gates/`) |
| Profile before spend | corpus census and cost estimate | `kg profile`; a build is refused before any call when the domain is empty or the estimate exceeds the ceiling |
| Priced routing | thresholds on judge score | two thresholds, accept / review / reject, from route prices (below) |
| Conformance record | per-build record of what passed | `kg/conformance.py`, written as an `experiments.record` RunRecord |
| Adjudication protocol | `docs/ADJUDICATION.md` | the protocol is the model for gold labelling (`evals/gold/README.md`); not yet encoded beyond the entry-time gates in `kg/label.py`, and its domain-specific seam rulings were not taken |

## Not taken

- The serving app and UI. This is method, not product; `ask` is a CLI.
- OWL import. The pack is hand-written.
- The benchmark harness (DocRED, BioRED, CUAD). The run's own gold is the benchmark.
- The configure wizard, dialects and packaging. `config.py` reads env vars.
- Any code. No OntoSmith source file is copied into this run.

## Changed, with the reason

- **Thresholds are priced, not only searched.** OntoSmith picks the operating point under a
  precision floor. The course's Chow derivation prices each route (wrong accept 10, wrong
  reject 3, review 1, with an imperfect reviewer) and the thresholds fall out of the prices.
  Both points are reported: `floor_point` keeps OntoSmith's rule beside the priced one.
- **Judge quality is TPR, TNR and κ against human labels**, never agreement between seats. Two
  scorers with the same blind spot can agree with each other and not with people. Hence the
  optional second-family seat (Jev, via OpenRouter) and the hand-labelled gold.
- **A store behind a protocol.** SQLite is the default; Neo4j sits behind the same
  `GraphStore` protocol, with result parity tested and pre-registered (`preregistration.md`).
  At this size, recursive SQL is expected to match it.
- **"Not run" is not "nothing found."** Every model failure becomes `not_run` with a reason, and
  a rate with no denominator is `NotApplicable`, never 0.0.

## What it shows so far

Nothing about quality yet. Phase A and the Phase B seams run end to end in dry-run mode.
Quality numbers wait on the gold (B1) and the spend decision (`spend-decision.md`).
