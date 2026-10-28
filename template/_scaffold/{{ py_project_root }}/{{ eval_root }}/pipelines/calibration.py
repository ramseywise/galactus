"""Heuristic-vs-judge calibration over a graded interactions file.

For each metric where both grader types scored the same interaction, computes
agreement rate and Cohen's kappa — how well the free heuristic flags track the
LLM judge. Low kappa means the heuristic (or the judge prompt) needs retuning;
high kappa means heuristic-only CI runs are trustworthy proxies.

    python -m evals.pipelines.calibration            # reads the default graded file
    python -m evals.pipelines.calibration --input reports/output/interactions_graded.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_GRADED_PATH = (
    Path(__file__).resolve().parent.parent / "reports" / "output" / "interactions_graded.jsonl"
)
CALIBRATION_OUTPUT = (
    Path(__file__).resolve().parent.parent / "reports" / "output" / "calibration.json"
)


def cohens_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa for two binary raters; None when there are no pairs."""
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(1 for a, b in pairs if a == b) / n
    p_a = sum(1 for a, _ in pairs if a) / n
    p_b = sum(1 for _, b in pairs if b) / n
    expected = p_a * p_b + (1 - p_a) * (1 - p_b)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1 - expected)


def calibrate(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Per-metric agreement stats from graded rows ({"interaction": ..., "grades": [...]})."""
    pairs_by_metric: dict[str, list[tuple[bool, bool]]] = {}
    for row in rows:
        by_metric: dict[str, dict[str, bool]] = {}
        for grade in row.get("grades", []):
            by_metric.setdefault(grade["metric"], {})[grade["grader"]] = bool(grade["is_correct"])
        for metric, graders in by_metric.items():
            if "heuristic" in graders and "judge" in graders:
                pairs_by_metric.setdefault(metric, []).append(
                    (graders["heuristic"], graders["judge"])
                )

    stats: dict[str, dict[str, float]] = {}
    for metric, pairs in sorted(pairs_by_metric.items()):
        kappa = cohens_kappa(pairs)
        stats[metric] = {
            "n": float(len(pairs)),
            "agreement": sum(1 for a, b in pairs if a == b) / len(pairs),
            "kappa": kappa if kappa is not None else 0.0,
        }
    return stats


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m evals.pipelines.calibration")
    parser.add_argument("--input", type=Path, default=DEFAULT_GRADED_PATH)
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(
            f"error: no graded file at '{args.input}'.\n"
            "Run `python -m evals.pipelines.grade run` (or `make eval-grade`) first — "
            "with ANTHROPIC_API_KEY set, so judge results exist to calibrate against.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    lines = args.input.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    stats = calibrate(rows)

    if not stats:
        print("No interactions carry both heuristic and judge grades — nothing to calibrate.")
        print("(Judges require ANTHROPIC_API_KEY; re-run grading with it set.)")
        return

    header = f"{'metric':<12} {'n':>4} {'agreement':>10} {'kappa':>7}"
    print(header)
    print("-" * len(header))
    for metric, s in stats.items():
        print(f"{metric:<12} {int(s['n']):>4} {s['agreement']:>10.3f} {s['kappa']:>7.3f}")

    CALIBRATION_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_OUTPUT.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"\nWrote calibration stats to {CALIBRATION_OUTPUT}")


if __name__ == "__main__":
    main()
