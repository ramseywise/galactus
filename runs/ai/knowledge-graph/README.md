# knowledge-graph

The OntoSmith method — hash-pinned pack, cheap proposer, pure gates, blind judge, priced
two-threshold route — rebuilt as a galactus run at the triple grain (entity, relation,
entity, verbatim quote). Plan: `.claude/docs/plans/2026-11-07-knowledge-graph-run-from-ontosmith.md`.
Design: [docs/DESIGN.md](docs/DESIGN.md). Provenance: [docs/case-study.md](docs/case-study.md),
[docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).

**State:** no live model call has been made. The pipeline, both judge seats (Claude, Jev),
both stores (SQLite, Neo4j), the Librarian baseline and both evals run end to end with
`--dry-run`. Not yet done: the eval-v1 pack approval, the hand-labelled gold, the hand-written
retrieval questions, and the spend decision ([docs/spend-decision.md](docs/spend-decision.md)).
Source: 5,192 lines of Python under `src/`.

```bash
uv run pytest runs/ai/knowledge-graph/tests -q     # Neo4j tests skip without NEO4J_URI; the count is printed
```

## Running

`kg` is on pytest's pythonpath only (the root pyproject has no build system), so the CLI
needs `PYTHONPATH` set. `../../..` puts the repo root on the path for `experiments.record`.

```bash
cd runs/ai/knowledge-graph
export PYTHONPATH=src:../../..
uv run python -m kg.cli profile eval                        # census + cost estimate
uv run python -m kg.cli build eval --dry-run                # no spend
uv run python -m kg.cli ask "Position Bias"                 # graph lookup (promoted builds, accept tier)
uv run python -m kg.cli ask "position bias" --via-librarian # entry pages from Librarian, then hops
uv run python -m kg.cli verify-gold evals/gold/eval-v1.jsonl
uv run python evals/run.py --dry-run --json                 # judge calibration eval
uv run python evals/run.py --retrieval --dry-run            # retrieval eval, scripted arms
```

Every command that would call a paid model refuses unless `KG_LIVE=1` is set, and that is
set only after the spend checklist. `--judge jev` needs `OPENROUTER_API_KEY`, and
`--store neo4j` needs `NEO4J_URI`. Each one refuses by name when its variable is missing.

Neo4j, locally:

```bash
docker compose -f runs/ai/knowledge-graph/docker-compose.yml up -d
NEO4J_URI=bolt://localhost:7687 uv run pytest runs/ai/knowledge-graph/tests -q
docker compose -f runs/ai/knowledge-graph/docker-compose.yml down
```

## Approving a pack

Nothing builds against an unapproved pack. Review `packs/eval-v1.json`, edit it freely,
then record the approval bound to its hash:

```bash
uv run python -m kg.cli approve eval --by Ramsey
```

Any later edit changes the hash, and the pack is refused until it is approved again.

## Gold and questions (human work)

- **Judge gold:** `uv run python -m kg.cli label eval` appends to `evals/gold/eval-v1.jsonl`,
  checking each label against the gates at entry. The floors are 50 positive, 15 hard
  negative and 5 control rows, across at least 20 pages, with at least 10 rows in `test`.
  `verify-gold` reports the shortfall.
- **Retrieval questions:** `evals/questions.jsonl` holds 79 weak-gold rows generated from
  typed wikilinks. The goal-1 verdict is read only on hand-written rows (`"source": "hand"`;
  the format is in the `evals/run.py` docstring), and at least 20 are needed.

Configuration: see `.env.example`. Nothing is required to load settings; each external
dependency (Anthropic key, OpenRouter key, Neo4j URI, corpus and Librarian paths) refuses
by name when it is missing.
