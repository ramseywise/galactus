"""The proving run — the only module that touches the real CSVs.

Plan: `.claude/docs/plans/2026-08-14-gal-17-customer-segmentation.md`.

WHAT THIS RUN IS
    Part 3 of the Trade Republic challenge: segment ~29,000 customers by trading
    behaviour. Its value to this repo is as an `ml`-track exemplar — profile before
    framing, baseline named before it is computed, leakage shown red before it is cleared.

    **A refusing run is a successful run.** If the leakage guard reports any FAIL, this
    exits 0, writes the report, and declines to name a winning k. Following
    `runs/ml/fraud/src/run.py`: a guard that can be talked past is not a guard.

DATA HANDLING
    `csv/` is covered by the repo-wide `*.csv` ignore and `docs/` is ignored explicitly —
    the generated report carries centroid profiles over real customers, and aggregates
    derived from real records are still real records. This script prints aggregates only:
    never a customer id, never a row.

PROVENANCE
    `segments.json` is stamped with a run id, the feature set, input file hashes, and the
    four leakage verdicts. Both artifacts are written to fixed paths and overwritten in
    place, so without the stamp there would be no way to tell whether a given report
    predates a fix.

RUNNING IT
    uv run --group ml python "runs/ml/customer segmentation/src/run.py"
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cluster import best, sweep
from features import FEATURE_COLUMNS, VALUATION_DATE, build_customer_features
from load import load_instruments, load_prices, load_trades
from prepare import check_leakage, prepare_matrix

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "csv"
DOCS = ROOT / "docs"


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _build_synthetic_features(n_customers: int = 500, seed: int = 0) -> pd.DataFrame:
    """A synthetic feature frame for dry-run testing. Matches the real column contract."""
    import numpy as np

    rng = np.random.default_rng(seed)
    data = {}
    for col in FEATURE_COLUMNS:
        data[col] = rng.standard_normal(n_customers).astype(float)
    # Make the skewed columns positive so log1p works
    from prepare import LOG_COLUMNS

    for col in LOG_COLUMNS:
        data[col] = np.abs(data[col]) + 0.1
    return pd.DataFrame(data)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="use synthetic features instead of real CSVs; never writes to runs/_index/",
    )
    args = parser.parse_args()

    DOCS.mkdir(exist_ok=True)
    started = datetime.now(UTC)
    run_id = started.strftime("%Y%m%dT%H%M%SZ")

    print(f"run {run_id}")

    if args.dry_run:
        from cluster import RANDOM_STATE

        features = _build_synthetic_features(seed=RANDOM_STATE)
        print(f"  dry-run: synthetic {len(features)} customers x {len(FEATURE_COLUMNS)} features")
    else:
        print("loading")
        trades, report = load_trades(CSV / "trades.csv")
        instruments = load_instruments(CSV / "instruments.csv")
        prices = load_prices(CSV / "prices.csv")
        print(
            f"  trades {report.rows_in:,} -> {report.rows_out:,} "
            f"({report.dropped_unparseable_time} unparseable timestamp dropped)"
        )
        print(
            f"  instruments {len(instruments):,} | prices {len(prices):,} "
            f"({prices['date'].nunique()} distinct dates, {int(prices['date'].isna().sum())} NaT)"
        )

        print("building features")
        features = build_customer_features(trades, instruments, prices)
        print(f"  {len(features):,} customers x {len(FEATURE_COLUMNS)} features")

    # The guard runs, and is printed, BEFORE any score exists. A leakage check written
    # after a good number is a check under pressure to pass.
    print("\nleakage check (before any score)")
    findings = check_leakage(features, expected_rows=len(features))
    for finding in findings:
        print(f"  {finding}")
    # Leakage rules (a, b, c) are data integrity — a FAIL means the matrix is
    # contaminated and no score from it can be trusted. Rule (d) is matrix health.
    # A leakage FAIL aborts non-zero; a weak-structure or implausibility result
    # refuses and exits 0 (a legitimate finding, not a failure).
    leakage_rules = {
        "a_no_first_trade_derived_column",
        "b_scaler_fitted_within_fold",
        "c_no_sum_and_parts_double_count",
    }
    leakage_failures = [f for f in findings if f.rule in leakage_rules and not f.passed]
    health_failures = [f for f in findings if f.rule not in leakage_rules and not f.passed]
    clean = not leakage_failures and not health_failures

    if leakage_failures:
        print("\nABORTING: leakage guard has a FAIL — the matrix is contaminated.")
        for f in leakage_failures:
            print(f"  {f}")
        print("A leak makes every score meaningless. Exit non-zero.")
        return 1

    matrix, columns = prepare_matrix(features)

    results = []
    winner = None
    if health_failures:
        print("\nREFUSING to report a winning k: matrix health check failed.")
        for f in health_failures:
            print(f"  {f}")
        print("This run exits 0 and reports the refusal — that is the successful outcome here.")
    else:
        print("\nsweeping k")
        results = sweep(matrix, k_range=range(2, 11))
        for r in results:
            flag = "  <- beats both baselines" if r.beats_baselines else ""
            print(
                f"  k={r.k:2d}  silhouette={r.silhouette:.4f}  "
                f"db={r.davies_bouldin:.3f}  random={r.baseline_random:.4f}  "
                f"k2={r.baseline_k2:.4f}{flag}"
            )
        winner = best(results)
        print(f"\nchosen k={winner.k} (silhouette {winner.silhouette:.4f})")
        if winner.implausible:
            print(
                "  SUSPECTED LEAK: silhouette above the implausibility threshold. "
                "Treat as a finding, not a result."
            )
        if not winner.beats_baselines:
            print("  WARNING: no k beat both baselines — the structure here is weak.")

    payload = {
        "run_id": run_id,
        "valuation_date": str(VALUATION_DATE.date()),
        "feature_columns": list(FEATURE_COLUMNS),
        "inputs": {
            name: {"sha256_16": _hash(CSV / name), "bytes": (CSV / name).stat().st_size}
            for name in ("trades.csv", "instruments.csv", "prices.csv")
        },
        "leakage": [{"rule": f.rule, "passed": f.passed, "detail": f.detail} for f in findings],
        "refused": not clean,
        "n_customers": len(features),
        "sweep": [
            {
                "k": r.k,
                "silhouette": r.silhouette,
                "davies_bouldin": r.davies_bouldin,
                "sizes": list(r.sizes),
                "baseline_random": r.baseline_random,
                "baseline_k2": r.baseline_k2,
            }
            for r in results
        ],
        "chosen_k": winner.k if winner else None,
    }
    (DOCS / "segments.json").write_text(json.dumps(payload, indent=2))

    _write_report(features, columns, findings, results, winner, payload)
    print(f"\nwrote {DOCS / 'segments.json'} and {DOCS / 'report.md'}")
    return 0


def _write_report(features, columns, findings, results, winner, payload) -> None:
    lines: list[str] = []
    lines.append("# Customer segmentation — results\n")
    lines.append(
        f"Run `{payload['run_id']}` · {payload['n_customers']:,} customers · "
        f"{len(payload['feature_columns'])} features · "
        f"valued at {payload['valuation_date']}\n"
    )

    # Leakage first, deliberately: it is printed before any score in the console and it
    # reads before any score here.
    lines.append("## Leakage check\n")
    lines.append(
        "Reported before the scores, because a check written after a good number "
        "is a check under pressure to pass.\n"
    )
    lines.append("| Rule | Verdict | Detail |")
    lines.append("|---|---|---|")
    for f in findings:
        lines.append(f"| `{f.rule}` | {'PASS' if f.passed else '**FAIL**'} | {f.detail} |")
    lines.append("")

    if payload["refused"]:
        lines.append("## Refused\n")
        lines.append(
            "The guard reported a FAIL, so no winning k is named. "
            "The run completed successfully; it declined to report a result.\n"
        )
    else:
        lines.append("## The sweep\n")
        lines.append(
            "Every k is reported, not just the winner, and every score sits "
            "beside the two baselines it has to beat.\n"
        )
        lines.append(
            "| k | silhouette | Davies–Bouldin | random baseline | k=2 baseline | beats both |"
        )
        lines.append("|---|---|---|---|---|---|")
        for r in results:
            lines.append(
                f"| {r.k} | {r.silhouette:.4f} | {r.davies_bouldin:.3f} | "
                f"{r.baseline_random:.4f} | {r.baseline_k2:.4f} | "
                f"{'yes' if r.beats_baselines else 'no'} |"
            )
        lines.append("")

        lines.append(f"## Chosen: k={winner.k}\n")
        if winner.implausible:
            lines.append(
                "> **Suspected leak.** The silhouette is above the implausibility "
                "threshold. On real behavioural data this usually means a column "
                "restated the answer. Treated as a finding, not a result.\n"
            )
        if not winner.beats_baselines:
            lines.append(
                "> **Weak structure.** No k beat both baselines. The honest reading "
                "is that k-means over these features does not find strong "
                "separation — reported rather than hidden.\n"
            )

        labels = pd.Series(winner.labels, index=features.index, name="segment")
        profile = features.join(labels).groupby("segment").agg(["median"])
        profile.columns = [c[0] for c in profile.columns]
        sizes = labels.value_counts().sort_index()

        lines.append("### Segment sizes\n")
        lines.append("| Segment | Customers | Share |")
        lines.append("|---|---|---|")
        for seg, n in sizes.items():
            lines.append(f"| {seg} | {n:,} | {n / len(labels):.1%} |")
        lines.append("")

        lines.append("### Median profile per segment\n")
        keep = [
            "n_trades",
            "total_volume",
            "mean_trade_size",
            "realized_pnl",
            "virtual_pnl",
            "n_instruments",
            "n_sectors",
            "sector_coverage",
            "days_since_last_trade",
            "tenure_days",
        ]
        lines.append("| Segment | " + " | ".join(keep) + " |")
        lines.append("|---" * (len(keep) + 1) + "|")
        for seg in profile.index:
            row = " | ".join(f"{profile.loc[seg, c]:,.2f}" for c in keep)
            lines.append(f"| {seg} | {row} |")
        lines.append("")

    lines.append("## Provenance\n")
    lines.append("| Input | sha256 (16) | bytes |")
    lines.append("|---|---|---|")
    for name, meta in payload["inputs"].items():
        lines.append(f"| `{name}` | `{meta['sha256_16']}` | {meta['bytes']:,} |")
    lines.append("")

    (DOCS / "report.md").write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
