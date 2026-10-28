"""Seeded sampling of interaction records for experiments.

Subsample for local dev or to control judge cost; always seeded so runs are
reproducible, and the pipeline prints the sample size + seed it used.

    python -m evals.pipelines.sampling --input all.jsonl --output sample.jsonl --n 50
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

DEFAULT_SEED = 42


def sample_records(
    records: list[dict[str, Any]],
    n: int,
    seed: int = DEFAULT_SEED,
    stratify_by: str | None = None,
) -> list[dict[str, Any]]:
    """Take a seeded sample of ``n`` records, optionally stratified by a field.

    Stratified sampling round-robins across the field's value buckets so rare
    categories (e.g. escalation cases) keep representation in small samples.
    """
    if n >= len(records):
        return list(records)
    rng = random.Random(seed)
    if stratify_by is None:
        return rng.sample(records, n)

    buckets: dict[Any, list[dict[str, Any]]] = {}
    for record in records:
        buckets.setdefault(record.get(stratify_by), []).append(record)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    sampled: list[dict[str, Any]] = []
    bucket_order = sorted(buckets, key=str)
    index = 0
    while len(sampled) < n:
        bucket = buckets[bucket_order[index % len(bucket_order)]]
        if bucket:
            sampled.append(bucket.pop())
        elif all(not b for b in buckets.values()):
            break
        index += 1
    return sampled


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m evals.pipelines.sampling")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--stratify-by", default=None, help="Record field to stratify on.")
    args = parser.parse_args(argv)

    lines = args.input.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    sampled = sample_records(records, args.n, seed=args.seed, stratify_by=args.stratify_by)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in sampled),
        encoding="utf-8",
    )
    print(f"Sampled {len(sampled)}/{len(records)} record(s) (seed={args.seed}) -> {args.output}")


if __name__ == "__main__":
    main()
