"""Runs INSIDE Librarian's own venv: `uv run --project $LIBRARIAN_ROOT python -I <this file>`.

galactus never imports Librarian; this script is the only place `librarian` is imported, and
only because it executes in Librarian's interpreter. It must not be imported by `kg` or by
pytest collection (its name starts with `_` and no test imports it).

Prints one JSON object: rows (7-tuples as lists), degraded, and `retrieval_ms`, the
in-process time of the search call alone so latency excludes `uv run` startup (fog FA-009).
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--domain", default="")
    ap.add_argument("--expand", action="store_true")
    args = ap.parse_args(argv)

    from librarian.retrieval.ranking import search_rows

    t0 = time.perf_counter()
    rows, degraded = search_rows(
        args.query, domain=args.domain, limit=args.limit, tool="kg_baseline", expand=args.expand
    )
    ms = (time.perf_counter() - t0) * 1000
    json.dump(
        {"rows": [list(r) for r in rows], "degraded": list(degraded), "retrieval_ms": ms},
        sys.stdout,
        default=str,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
