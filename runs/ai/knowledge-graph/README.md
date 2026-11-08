# knowledge-graph

The OntoSmith method — hash-pinned pack, cheap proposer, pure gates, blind judge, priced
two-threshold route — rebuilt as a galactus run at the triple grain (entity, relation,
entity, verbatim quote). Plan: `.claude/docs/plans/2026-11-07-knowledge-graph-run-from-ontosmith.md`.

**State:** Phase A built (pack, profile, gates, store, proposer, judge, route, build, CLI,
gold labelling, evals). Dry runs only: no live model call has been made, and the eval-v1
pack is not yet approved.

```bash
uv run pytest runs/ai/knowledge-graph/tests -q
```

## Running

`kg` is on pytest's pythonpath only (the root pyproject has no build system), so the CLI
needs `PYTHONPATH` set. `../../..` puts the repo root on the path for `experiments.record`.

```bash
cd runs/ai/knowledge-graph
PYTHONPATH=src:../../.. uv run python -m kg.cli profile eval            # census + cost estimate
PYTHONPATH=src:../../.. uv run python -m kg.cli build eval --dry-run    # no spend
uv run python evals/run.py --dry-run --json                             # evals, no spend
```

A live build needs an approved pack and `ANTHROPIC_API_KEY`; the live eval judge
(`--judge claude`) additionally needs `KG_LIVE=1`.

## Approving a pack

Nothing builds against an unapproved pack. Review `packs/eval-v1.json`, edit it freely,
then record the approval bound to its hash:

```bash
cd runs/ai/knowledge-graph
PYTHONPATH=src:../../.. uv run python -m kg.cli approve eval --by Ramsey
```

Any later edit changes the hash, and the pack is refused until it is approved again.

Configuration: see `.env.example`. Nothing is required to load settings; each external
dependency (Anthropic key, OpenRouter key, Neo4j URI, corpus and Librarian paths) refuses
by name when it is missing.
