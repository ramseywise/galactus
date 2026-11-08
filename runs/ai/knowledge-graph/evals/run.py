"""Eval harness for the knowledge-graph judge seats: turns assertions into numbers.

Scores a human-labelled gold set with one judge seat and reports, per seat and with `n`,
every figure in the spec's Measurement table that a seat evaluation can produce. Figures
that belong to another instrument (a build, a retrieval eval) are listed too, as `n/a`
with the reason, so the table is complete and nothing reads as 0.0 by omission.

`--dry-run` scores with a scripted seat: no network, no key, no spend. It uses the real
gold when it has rows and otherwise the 12-row fixture, and says which in the report.

Usage (from runs/ai/knowledge-graph):
    uv run python evals/run.py --dry-run
    uv run python evals/run.py --dry-run --json
    uv run python evals/run.py --dry-run --split all    # fixture only has 2 test rows
    KG_LIVE=1 uv run python evals/run.py --judge claude   # spends money; see the refusal text
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_RUN = Path(__file__).resolve().parent.parent
# `kg` lives in this run's src/; `experiments` (the shared NotApplicable) at the repo root.
sys.path[:0] = [str(_RUN / "src"), str(_RUN.parents[2])]

from kg.config import ConfigError, Settings  # noqa: E402
from kg.judge.calibration import Kappa, Obs, Rate, SeatCalibration, calibrate  # noqa: E402
from kg.judge.seat import JudgeSeat, window  # noqa: E402
from kg.label import GoldRow, read_gold  # noqa: E402
from kg.models import Candidate, NotApplicable, NotRun, Usage, Verdict  # noqa: E402
from kg.profile import iter_pages  # noqa: E402
from kg.route.tiers import floor_point  # noqa: E402

RUN_DIR = Path(__file__).resolve().parent.parent
GOLD_PATH = RUN_DIR / "evals" / "gold" / "eval-v1.jsonl"
FIXTURE_GOLD_PATH = RUN_DIR / "tests" / "fixtures" / "gold_small.jsonl"
REPEATS = 5
PRECISION_FLOOR = 0.90

SPEND_REFUSAL = (
    "refused: live evaluation is a separate decision; see docs/spend-decision.md "
    "(--judge claude spends money; set KG_LIVE=1 after the spend decision)"
)
AGREEMENT_NOTE = (
    "agreement is not precision (F4): a repeatable or agreeing judge can still accept "
    "unsupported triples, so read precision on the hard-negative pool, not agreement."
)

# -- the dry-run seat ------------------------------------------------------------------

_BAIT_WORDS = ("ignore", "instruction", "disregard", "you must", "system prompt")


class DryRunSeat:
    """Deterministic, zero-spend `JudgeSeat` with a fixed, imperfect rule.

    Bait-looking quotes are rejected. Everything else gets a verdict from a hash of the
    triple's relation and object: 70% supported (0.9), 20% unclear (0.5), 10% not supported
    (0.2). The rule never reads the gold label, so confusion cells of every kind are
    populated and each metric has something to compute. Repeats 3 and 4 flip the rows that
    hash to 6, so test-retest is below 1.0. The numbers mean nothing about any model.
    """

    name = "scripted"

    def __init__(self) -> None:
        self.repeat = 0

    @staticmethod
    def _bucket(c: Candidate) -> int:
        return int(hashlib.sha256(f"{c.relation}|{c.object}".encode()).hexdigest(), 16) % 10

    async def judge(self, candidate: Candidate, window: str) -> Verdict | NotRun:
        usage = Usage(model="scripted")
        if any(w in candidate.quote.lower() for w in _BAIT_WORDS):
            return Verdict(label="not_supported", score=0.1, usage=usage)
        h = self._bucket(candidate)
        if self.repeat >= 3 and h == 6:
            h = 8
        if h < 7:
            return Verdict(label="supported", score=0.9, usage=usage)
        if h < 9:
            return Verdict(label="unclear", score=0.5, usage=usage)
        return Verdict(label="not_supported", score=0.2, usage=usage)

    def available(self) -> tuple[bool, str]:
        return True, ""


# -- seat selection and refusals -------------------------------------------------------


def _refuse(message: str) -> None:
    sys.exit(message)


def select_seat(args: argparse.Namespace, settings: Settings) -> JudgeSeat:
    """Return the seat, or exit non-zero naming why not. Refusals come before any work."""
    if args.store != "sqlite":
        _refuse(
            f"refused: store '{args.store}' is Phase B and is not implemented; "
            "only --store sqlite is available"
        )
    if args.judge == "scripted":
        if not args.dry_run:
            _refuse("refused: the scripted seat measures nothing real; use it with --dry-run")
        return DryRunSeat()
    if args.judge == "claude":
        if not os.environ.get("KG_LIVE"):
            _refuse(SPEND_REFUSAL)
        from kg.judge.claude import ClaudeSeat  # lazy: only the live path needs it

        seat: JudgeSeat = ClaudeSeat(settings)
    else:  # jev
        try:
            settings.require_openrouter_key()
        except ConfigError as exc:
            _refuse(f"refused: judge seat 'jev' unavailable — {exc}")
        try:
            from kg.judge.jev import JevSeat  # type: ignore[import-not-found]  # Phase B2
        except ImportError:
            _refuse(
                "refused: judge seat 'jev' unavailable — OPENROUTER_API_KEY is set but the "
                "Jev seat is not implemented yet (Phase B2)"
            )
        seat = JevSeat(settings)
    ok, why = seat.available()
    if not ok:
        _refuse(f"refused: judge seat '{seat.name}' unavailable — {why}")
    return seat


# -- scoring ---------------------------------------------------------------------------


def load_gold(args: argparse.Namespace) -> tuple[list[GoldRow], Path, str]:
    """(rows, path, source). A dry run falls back to the fixture when the real gold is empty."""
    path = Path(args.gold)
    rows = read_gold(path)
    if rows:
        return rows, path, "gold"
    if args.dry_run and Path(args.gold) == GOLD_PATH:
        return read_gold(FIXTURE_GOLD_PATH), FIXTURE_GOLD_PATH, "fixture-fallback"
    _refuse(f"refused: gold set {path} has no rows; label it first (kg label eval)")
    raise AssertionError  # unreachable


def _windows(
    rows: Sequence[GoldRow], args: argparse.Namespace, settings: Settings
) -> dict[str, str]:
    """Judge window per row id. A dry run uses the quote; live reads the normalised page."""
    if args.dry_run:
        return {r.id: r.quote for r in rows}
    bodies = {p.path: p.body for p in iter_pages(settings.require_corpus_root(), "eval")}
    out: dict[str, str] = {}
    for r in rows:
        body = bodies.get(r.page)
        start = body.find(r.quote) if body else -1
        if body is None or start < 0:
            _refuse(f"refused: gold row {r.id} quote is not verbatim in {r.page}; run verify-gold")
        out[r.id] = window(body, (start, start + len(r.quote)))
    return out


async def _judge_all(
    seat: JudgeSeat, rows: Sequence[GoldRow], windows: dict[str, str], repeats: int, split_all: bool
) -> list[list[Obs]]:
    out: list[list[Obs]] = []
    for k in range(repeats):
        if isinstance(seat, DryRunSeat):
            seat.repeat = k
        obs: list[Obs] = []
        for r in rows:
            v = await seat.judge(r.candidate(), windows[r.id])
            split = "test" if split_all else r.split
            if isinstance(v, Verdict):
                obs.append(Obs(r.id, r.label, split, v.label, v.score))
            else:
                obs.append(Obs(r.id, r.label, split, None, None))
        out.append(obs)
    return out


def _metric(
    key: str,
    seat: str,
    value: Rate | Kappa | NotApplicable,
    *,
    threshold: str = "reported",
    detail: str | None = None,
) -> dict[str, Any]:
    m: dict[str, Any] = {
        "metric": key,
        "seat": seat,
        "threshold": threshold,
        "n": None,
        "value": None,
        "ci": None,
        "status": "n/a",
        "reason": None,
        "detail": detail,
    }
    if isinstance(value, NotApplicable):
        m["reason"] = value.reason
    else:
        m.update(n=value.n, value=value.value, status="measured")
        if isinstance(value, Kappa):
            m["ci"] = [value.lo, value.hi]
    return m


def _not_here(key: str, seat: str, reason: str, threshold: str) -> dict[str, Any]:
    return _metric(key, seat, NotApplicable(reason), threshold=threshold)


def seat_metrics(
    cal: SeatCalibration, repeats: Sequence[Sequence[Obs]], split: str
) -> list[dict[str, Any]]:
    """Every Measurement-table row, for one seat."""
    s = cal.seat
    primary = [o for o in repeats[0] if o.split == split]
    scored = [(o.score, o.gold == "positive") for o in primary if o.label and o.score is not None]
    fp = floor_point([x for x, _ in scored], [t for _, t in scored], PRECISION_FLOOR)
    if isinstance(fp, NotApplicable):
        band: Rate | NotApplicable = fp
        band_detail = None
    else:
        band = Rate(fp.band_rate, len(scored))
        band_detail = (
            f"t_lo={fp.t_lo:.2f} t_hi={fp.t_hi:.2f} accept_precision={fp.accept_precision:.3f}"
        )
    n_run = cal.n_test - cal.n_not_run
    return [
        _metric(
            "judge_precision_hard_negative",
            s,
            cal.hard_negative_precision,
            threshold=">= 0.90 at the accept tier",
            detail="precision over positives + hard negatives only (F3); controls excluded",
        ),
        _metric(
            "review_band_rate_at_floor",
            s,
            band,
            threshold="<= 0.40 or the build halts",
            detail=band_detail,
        ),
        _metric("tpr", s, cal.tpr),
        _metric("tnr", s, cal.tnr),
        _metric("kappa", s, cal.kappa),
        _metric("hard_negative_tnr", s, cal.hard_negative_tnr),
        _metric("control_tnr", s, cal.control_tnr),
        _metric("ece", s, cal.ece),
        _metric(
            "test_retest_agreement",
            s,
            cal.retest,
            detail="repeatability, not validity: a repeatable judge reproduces its bias",
        ),
        _metric(
            "not_run_rows",
            s,
            Rate(cal.n_not_run / cal.n_test, cal.n_test)
            if cal.n_test
            else NotApplicable("no rows in the split"),
            threshold="reported",
            detail=f"{cal.n_not_run} of {cal.n_test} rows; {n_run} judged",
        ),
        _not_here(
            "grounding_rate", s, "measured at build time by the verbatim gate + test", "100%"
        ),
        _not_here("not_run_pages_per_build", s, "a build metric; see the conformance record", "0"),
        _not_here(
            "cost_per_100_accepted",
            s,
            "needs a build ledger; the judge eval meters no accepted triples",
            "build <= $10, band <= $30",
        ),
        _not_here(
            "retrieval_recall_at_5",
            s,
            "Phase B retrieval eval; not part of the judge eval",
            ">= 10 points absolute",
        ),
        _not_here("ask_p95_latency", s, "Phase B retrieval eval", "< 3 s"),
        _not_here(
            "source_size_lines", s, "measured once with wc -l in the build report", "reported"
        ),
    ]


def build_report(
    args: argparse.Namespace,
    seat: JudgeSeat,
    rows: list[GoldRow],
    path: Path,
    source: str,
    repeats: list[list[Obs]],
) -> dict[str, Any]:
    split = "test" if args.split == "all" else args.split
    cal = calibrate({seat.name: repeats}, split=split)[seat.name]
    return {
        "mode": "dry-run" if args.dry_run else "live",
        "judge": seat.name,
        "store": args.store,
        "gold": {
            "path": str(path),
            "source": source,
            "rows": len(rows),
            "by_label": dict(Counter(r.label for r in rows)),
            "by_split": dict(Counter(r.split for r in rows)),
        },
        "split": args.split,
        "repeats": len(repeats),
        "n_scored": cal.n_test,
        "confusion": {
            "tp": cal.confusion.tp,
            "fn": cal.confusion.fn,
            "fp": cal.confusion.fp,
            "tn": cal.confusion.tn,
            "not_run": cal.confusion.not_run,
        },
        "notes": [AGREEMENT_NOTE],
        "metrics": seat_metrics(cal, repeats, split),
    }


def render_text(rep: dict[str, Any]) -> str:
    g = rep["gold"]
    lines = [
        f"knowledge-graph judge eval  mode={rep['mode']}  seat={rep['judge']}  store={rep['store']}",
        f"gold: {g['rows']} rows from {g['path']} ({g['source']})",
    ]
    if g["source"] == "fixture-fallback":
        lines.append(
            "  the real gold is empty until labelling (B1): scoring the 12-row fixture instead"
        )
    lines += [
        f"  by label {g['by_label']}  by split {g['by_split']}",
        f"split scored: {rep['split']} (n={rep['n_scored']}), repeats: {rep['repeats']}",
    ]
    if rep["split"] == "all":
        lines.append(
            "  split=all pools train/dev/test: dry-run plumbing check only, never a calibration"
        )
    c = rep["confusion"]
    lines += [
        f"confusion  tp={c['tp']} fn={c['fn']} fp={c['fp']} tn={c['tn']} not_run={c['not_run']}",
        "",
        f"{'metric':<32}{'seat':<11}{'n':>5}  value",
    ]
    hard = None
    for m in rep["metrics"]:
        if m["status"] == "measured":
            val = f"{m['value']:.4f}"
            if m["ci"]:
                val += f"  (95% CI {m['ci'][0]:.4f}..{m['ci'][1]:.4f})"
        else:
            val = f"n/a ({m['reason']})"
        n = "-" if m["n"] is None else str(m["n"])
        row = f"{m['metric']:<32}{m['seat']:<11}{n:>5}  {val}"
        if m["metric"] == "judge_precision_hard_negative":
            hard = row
            continue
        lines.append(row)
    lines += ["", "hard-negative precision (reported separately, F3):", f"  {hard}", ""]
    lines.append(f"note: {AGREEMENT_NOTE}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="scripted seat, no network, no spend")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--judge", choices=["scripted", "claude", "jev"], default="scripted")
    ap.add_argument("--store", choices=["sqlite", "neo4j"], default="sqlite")
    ap.add_argument("--gold", default=str(GOLD_PATH))
    ap.add_argument(
        "--split",
        choices=["test", "dev", "train", "all"],
        default="test",
        help="calibration split (default test); 'all' is for --dry-run only",
    )
    ap.add_argument("--repeats", type=int, default=REPEATS)
    args = ap.parse_args(argv)

    if args.split == "all" and not args.dry_run:
        _refuse("refused: --split all pools the training rows; it is for --dry-run only")
    if args.repeats < 1:
        _refuse("refused: --repeats must be >= 1")

    settings = Settings.load()
    seat = select_seat(args, settings)
    rows, path, source = load_gold(args)
    windows = _windows(rows, args, settings)
    repeats = asyncio.run(_judge_all(seat, rows, windows, args.repeats, args.split == "all"))
    rep = build_report(args, seat, rows, path, source, repeats)
    print(json.dumps(rep, indent=2) if args.json else render_text(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
