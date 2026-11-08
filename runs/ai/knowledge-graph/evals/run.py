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

Retrieval eval (`--retrieval`): four arms over `evals/questions.jsonl` -- Librarian baseline
with expansion off, baseline with expansion on, graph on SQLite, graph on Neo4j -- scored on the
weak-gold set and the hand-written set separately. `--dry-run` uses scripted arms (no Librarian,
no store); without it a missing Librarian, built graph or Neo4j refuses rather than skipping an arm.
    uv run python evals/run.py --retrieval --dry-run
    uv run python evals/run.py --retrieval --db evals/graph.sqlite --build-id <id>

`questions.jsonl` holds one JSON object per line. Weak rows are generated, never typed:
`PYTHONPATH=src uv run python -m kg.retrieve.weak_gold --out evals/questions.jsonl` rewrites
the `source: "weak"` rows and keeps every other row. Hand-written rows are Ramsey's to write:
`{"id": "h01", "source": "hand", "question": "...", "expected": ["eval/some-page.md"]}` with
`expected` a non-empty list of page paths relative to the corpus root and `id` unique. The
goal-1 verdict is read on the hand rows only; with none, that set prints NotApplicable.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

_RUN = Path(__file__).resolve().parent.parent
# `kg` lives in this run's src/; `experiments` (the shared NotApplicable) at the repo root.
sys.path[:0] = [str(_RUN / "src"), str(_RUN.parents[2])]

from kg.config import ConfigError, Settings  # noqa: E402
from kg.judge.calibration import Kappa, Obs, Rate, SeatCalibration, calibrate  # noqa: E402
from kg.judge.seat import JudgeSeat, window  # noqa: E402
from kg.label import GoldRow, read_gold  # noqa: E402
from kg.models import Candidate, NotApplicable, NotRun, Usage, Verdict  # noqa: E402
from kg.profile import census, iter_pages  # noqa: E402
from kg.retrieve import BaselineError, BaselineResult, ask, make_baseline  # noqa: E402
from kg.route.tiers import floor_point  # noqa: E402
from kg.store import GraphStore, SqliteStore  # noqa: E402

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


def open_store(args: argparse.Namespace, settings: Settings) -> Any:
    """`--store neo4j`: a `Neo4jStore`, or exit naming `NEO4J_URI` / the unreachable server.
    `--store sqlite` opens nothing (the judge eval reads no graph)."""
    if args.store != "neo4j":
        return None
    try:
        uri = settings.require_neo4j_uri()
    except ConfigError as exc:
        _refuse(f"refused: store 'neo4j' unavailable — {exc}")
    from kg.store.neo4j import Neo4jStore  # lazy: the driver is only needed here

    try:
        return Neo4jStore(uri, corpus_root=settings.corpus_root)
    except Exception as exc:  # noqa: BLE001 — any driver failure is a refusal by name
        _refuse(f"refused: store 'neo4j' unreachable at NEO4J_URI ({type(exc).__name__}: {exc})")


def select_seat(
    args: argparse.Namespace, settings: Settings, *, jev_client: httpx.AsyncClient | None = None
) -> JudgeSeat:
    """Return the seat, or exit non-zero naming why not. Refusals come before any work.

    `jev_client` is an injected `httpx.AsyncClient` for the jev seat (a `MockTransport` in tests)."""
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
        from kg.judge.jev import JevSeat

        seat = JevSeat(settings, client=jev_client)
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


# -- retrieval eval --------------------------------------------------------------------

QUESTIONS_PATH = RUN_DIR / "evals" / "questions.jsonl"
PREREG_PATH = RUN_DIR / "docs" / "preregistration.md"
BAR_POINTS = 10
TOP_K = 5
LATENCY_RUNS = 5
BOOT_N = 2000
BOOT_SEED = 0
SETS = ("weak", "hand")
ARMS = ("baseline_off", "baseline_on", "graph_sqlite", "graph_neo4j")
REFERENCE_ARM = "baseline_on"
VERDICT_ARM = "graph_sqlite"
NEO4J_UNAVAILABLE = "refused: arm 'graph_neo4j' unavailable — "


@dataclass(frozen=True)
class Question:
    id: str
    source: str
    question: str
    expected: tuple[str, ...]


@dataclass(frozen=True)
class Outcome:
    """What one arm returned for one question."""

    paths: tuple[str, ...]
    ms: float
    graph_status: str | None = None
    """`ok | entry_miss | no_hops` for graph arms; None for baselines."""
    all_fresh: bool | None = None
    """Every returned passage's quote still verbatim; None when no passage came back."""


Arm = Callable[[Question, int], Outcome]
"""`(question, run_index) -> Outcome`. Recall is read from run 0; every run feeds latency."""


def load_questions(path: Path) -> list[Question]:
    if not path.is_file():
        _refuse(f"refused: questions file {path} does not exist")
    out: list[Question] = []
    seen: set[str] = set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            q = Question(
                str(d["id"]), str(d["source"]), str(d["question"]), tuple(map(str, d["expected"]))
            )
        except (ValueError, KeyError, TypeError) as exc:
            _refuse(f"refused: {path}:{n} is not a question row ({exc})")
        if q.source not in SETS or not q.expected or not q.question.strip() or q.id in seen:
            _refuse(
                f"refused: {path}:{n} needs source weak|hand, a question, a non-empty "
                "expected list and a unique id"
            )
        seen.add(q.id)
        out.append(q)
    return out


def _matches(path: str, expected: str) -> bool:
    return path == expected or path.endswith("/" + expected)


def distinct(paths: Sequence[str], k: int = TOP_K) -> tuple[str, ...]:
    return tuple(dict.fromkeys(paths))[:k]


def recall_at_k(q: Question, paths: Sequence[str]) -> float:
    top = distinct(paths)
    return sum(any(_matches(p, e) for p in top) for e in q.expected) / len(q.expected)


def p95(values: Sequence[float]) -> float | NotApplicable:
    if not values:
        return NotApplicable("no latency samples")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def bootstrap_ci(diffs: Sequence[float]) -> tuple[float, float] | NotApplicable:
    """Seeded percentile interval of the mean paired difference."""
    if len(diffs) < 2:
        return NotApplicable(f"n={len(diffs)}: an interval needs at least 2 paired questions")
    rng = random.Random(BOOT_SEED)
    n = len(diffs)
    means = sorted(sum(rng.choices(diffs, k=n)) / n for _ in range(BOOT_N))
    return means[int(0.025 * BOOT_N)], means[int(0.975 * BOOT_N) - 1]


def _na(x: object) -> dict[str, Any]:
    return {"status": "n/a", "reason": x.reason if isinstance(x, NotApplicable) else str(x)}


def score_set(qs: Sequence[Question], outcomes: dict[str, list[list[Outcome]]]) -> dict[str, Any]:
    """Per-arm figures for one question set. `outcomes[arm][run]` is aligned with `qs`."""
    if not qs:
        why = "no questions in this set"
        return {"n": 0, "arms": {}, "reason": why}
    recalls = {
        a: [recall_at_k(q, o.paths) for q, o in zip(qs, runs[0], strict=True)]
        for a, runs in outcomes.items()
    }
    ref = recalls.get(REFERENCE_ARM)
    arms: dict[str, Any] = {}
    for a, runs in outcomes.items():
        first = runs[0]
        fig: dict[str, Any] = {
            "recall5": {"status": "measured", "value": sum(recalls[a]) / len(qs)}
        }
        if a == REFERENCE_ARM or ref is None:
            fig["vs_reference"] = _na("this is the reference arm")
        else:
            diffs = [x - y for x, y in zip(recalls[a], ref, strict=True)]
            ci = bootstrap_ci(diffs)
            cmp: dict[str, Any] = {"status": "measured", "diff": sum(diffs) / len(diffs)}
            if isinstance(ci, NotApplicable):
                cmp["reason"] = ci.reason
            else:
                cmp["lo"], cmp["hi"] = ci
            fig["vs_reference"] = cmp
        graph = [o for o in first if o.graph_status is not None]
        if graph:
            fig["entry_miss"] = {
                "status": "measured",
                "value": sum(o.graph_status == "entry_miss" for o in graph) / len(graph),
                "n": len(graph),
            }
            fresh = [o.all_fresh for o in first if o.all_fresh is not None]
            fig["grounding"] = (
                {"status": "measured", "value": sum(fresh) / len(fresh), "n": len(fresh)}
                if fresh
                else _na("no passage came back, so no quote was checked")
            )
        else:
            fig["entry_miss"] = _na("baseline arm has no entity-match step")
            fig["grounding"] = _na("baseline arm returns pages, not quoted passages")
        arms[a] = fig
    return {"n": len(qs), "arms": arms}


def verdict(hand: dict[str, Any]) -> dict[str, Any]:
    """Goal-1 verdict on the hand set only: graph (SQLite) vs the expansion-on baseline."""
    if hand["n"] == 0:
        return {
            "verdict": "cannot be read yet",
            "note": "no hand-written questions (source: hand) in questions.jsonl; "
            "the weak set shares its typed edges with baseline expansion and cannot carry goal 1",
        }
    cmp = hand["arms"][VERDICT_ARM]["vs_reference"]
    pts = cmp["diff"] * 100
    out: dict[str, Any] = {
        "verdict": "gain" if pts >= BAR_POINTS else "no gain recorded",
        "points": pts,
        "bar": BAR_POINTS,
    }
    if "lo" in cmp and cmp["lo"] * 100 < BAR_POINTS <= cmp["hi"] * 100:
        out["note"] = (
            f"the interval ({cmp['lo'] * 100:+.1f}..{cmp['hi'] * 100:+.1f} points) "
            f"straddles the {BAR_POINTS}-point bar: the point estimate does not settle it"
        )
    return out


def latency_figures(raw: dict[str, list[list[Outcome]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for a, runs in raw.items():
        samples = [o.ms for r in runs for o in r]
        v = p95(samples)
        out[a] = (
            _na(v)
            if isinstance(v, NotApplicable)
            else {"status": "measured", "p95_ms": v, "n": len(samples)}
        )
    return out


def preregistered_line(path: Path = PREREG_PATH) -> str:
    if not path.is_file():
        return f"unknown ({path.name} not found)"
    block = path.read_text(encoding="utf-8").split("## Predictions", 1)
    if len(block) < 2:
        return f"unknown ({path.name} has no Predictions section)"
    items = re.findall(r"^\d\.\s+\*\*(.+?)\*\*\s*(.*?)(?=^\d\.|^##|\Z)", block[1], re.M | re.S)
    parts = []
    for title, rest in items:
        first = re.split(r"(?<=[.])\s", " ".join(rest.split()), maxsplit=1)[0]
        parts.append(f"{title.rstrip('.')}: {first}")
    return " | ".join(parts) if parts else f"unknown ({path.name} predictions unparseable)"


def librarian_index_id(settings: Settings) -> str:
    """Librarian's `<id>.duckdb` named by `var/index/current`. Honest unknown otherwise.

    Librarian exposes the id only inside its own venv (`artifact.corpus_id()`); here it is read
    from the pointer on disk, which is wrong if Librarian's state dir is overridden."""
    pointer = settings.librarian_root / "var" / "index" / "current"
    try:
        return pointer.resolve(strict=True).stem
    except OSError:
        return f"unknown (no index pointer at {pointer})"


# -- scripted arms (dry run) -----------------------------------------------------------

_SCRIPTED_HIT = {"baseline_off": 40, "baseline_on": 55, "graph_sqlite": 62, "graph_neo4j": 62}
_SCRIPTED_MS = {"baseline_off": 90, "baseline_on": 140, "graph_sqlite": 160, "graph_neo4j": 175}


def _h(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16)


def scripted_arm(name: str) -> Arm:
    """Deterministic stand-in: finds each expected page with a fixed per-arm probability.
    The Neo4j arm reuses the SQLite arm's hit draw (the preregistered parity), so the
    numbers show plumbing only."""
    draw_name = "graph_sqlite" if name == "graph_neo4j" else name
    graph = name.startswith("graph")

    def arm(q: Question, run: int) -> Outcome:
        found = [e for e in q.expected if _h(draw_name, q.id, e) % 100 < _SCRIPTED_HIT[name]]
        miss = graph and _h(draw_name, q.id, "miss") % 100 < 15
        paths = () if miss else tuple(found) + tuple(f"scripted/decoy-{i}.md" for i in range(TOP_K))
        ms = _SCRIPTED_MS[name] * (0.8 + (_h(name, q.id, run) % 40) / 100)
        if not graph:
            return Outcome(distinct(paths), ms)
        status = "entry_miss" if miss else ("ok" if found else "no_hops")
        return Outcome(distinct(paths), ms, status, True if found else None)

    return arm


# -- live arms -------------------------------------------------------------------------


def baseline_arm(settings: Settings, *, expand: bool) -> Arm:
    base = make_baseline(settings, expand=expand)

    def arm(q: Question, run: int) -> Outcome:
        r = base(q.question, TOP_K)
        return Outcome(distinct([row.path for row in r.rows]), r.retrieval_ms)

    return arm


def graph_arm(settings: Settings, store: GraphStore, *, build_id: str | None) -> Arm:
    """Entities come from the expansion-on baseline's entry rows, as `hybrid.ask` does with
    `query` + `baseline`. The arm returns only graph passages (no baseline backfill), so an
    entry miss is an empty answer. Latency is in-process: the probe's reported retrieval time
    plus the time in `ask` outside the subprocess."""
    base = make_baseline(settings, expand=True)

    def arm(q: Question, run: int) -> Outcome:
        seen: list[BaselineResult] = []
        wall = 0.0

        def timed(query: str, limit: int) -> BaselineResult:
            nonlocal wall
            t0 = time.perf_counter()
            r = base(query, limit)
            wall = (time.perf_counter() - t0) * 1000
            seen.append(r)
            return r

        t0 = time.perf_counter()
        res = ask(
            store,
            settings=settings,
            query=q.question,
            baseline=timed,
            build_id=build_id,
            limit=TOP_K,
        )
        total = (time.perf_counter() - t0) * 1000
        ms = total - wall + (seen[0].retrieval_ms if seen else 0.0)
        paths = distinct([p.source_path for p in res.passages])
        fresh = None if not res.passages else all(p.freshness == "fresh" for p in res.passages)
        return Outcome(paths, ms, res.graph_status, fresh)

    return arm


def _sqlite_build(store: SqliteStore) -> str | None:
    import sqlite3

    with sqlite3.connect(f"file:{store.db_path}?mode=ro", uri=True) as conn:
        row = conn.execute(
            "SELECT build_id FROM builds WHERE status = 'promoted' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None


def _profile_hash(store: GraphStore, build_id: str | None) -> str:
    if build_id is None:
        return "unknown (no promoted build found; pass --build-id)"
    try:
        return store.stats(build_id).profile_hash
    except Exception as exc:  # noqa: BLE001 — a pin the store cannot give reads 'unknown'
        return f"unknown ({type(exc).__name__}: {exc})"


def live_arms(
    args: argparse.Namespace, settings: Settings
) -> tuple[dict[str, Arm], dict[str, str], list[Any]]:
    """The four live arms, the pinned ids, and stores to close. Any gap refuses."""
    try:
        make_baseline(settings, expand=False)("probe", 1)
    except BaselineError as exc:
        _refuse(f"refused: Librarian baseline unavailable — {exc}")
    dbp = Path(args.db) if args.db else settings.db_path
    if dbp is None or not Path(dbp).is_file():
        _refuse(
            f"refused: arm 'graph_sqlite' unavailable — no built graph at {dbp} "
            "(set KG_DB_PATH or --db; a build must exist first)"
        )
    sq = SqliteStore(Path(dbp), corpus_root=settings.corpus_root)
    try:
        neo = open_store(argparse.Namespace(store="neo4j"), settings)
    except SystemExit as exc:
        why = str(exc.code).split("— ", 1)[-1]
        sys.exit(NEO4J_UNAVAILABLE + why)
    sq_build = args.build_id or _sqlite_build(sq)
    arms = {
        "baseline_off": baseline_arm(settings, expand=False),
        "baseline_on": baseline_arm(settings, expand=True),
        "graph_sqlite": graph_arm(settings, sq, build_id=sq_build),
        "graph_neo4j": graph_arm(settings, neo, build_id=sq_build),
    }
    corpus_now = census(settings.require_corpus_root(), "eval").profile_hash
    built = _profile_hash(sq, sq_build)
    pins = {
        "librarian_index_id": librarian_index_id(settings),
        "graph_build_id": sq_build or "unknown",
        "graph_profile_hash": built,
        "corpus_profile_hash_now": corpus_now,
        "same_corpus": "yes"
        if built == corpus_now
        else "NO or unknown: the arms may describe different corpora",
    }
    return arms, pins, [sq, neo]


def run_retrieval(args: argparse.Namespace, settings: Settings) -> dict[str, Any]:
    qs = load_questions(Path(args.questions))
    closers: list[Any] = []
    if args.dry_run:
        arms = {a: scripted_arm(a) for a in ARMS}
        pins = {
            "librarian_index_id": "unknown (dry run: scripted arms, no Librarian)",
            "graph_build_id": "unknown (dry run: no store)",
            "graph_profile_hash": "unknown (dry run: no build)",
        }
    else:
        arms, pins, closers = live_arms(args, settings)
    runs = max(1, args.latency_runs)
    try:
        raw = {a: [[arm(q, r) for q in qs] for r in range(runs)] for a, arm in arms.items()}
    finally:
        for c in closers:
            getattr(c, "close", lambda: None)()
    sets = {}
    for s in SETS:
        idx = [i for i, q in enumerate(qs) if q.source == s]
        sub = {a: [[r[i] for i in idx] for r in rr] for a, rr in raw.items()}
        sets[s] = score_set([qs[i] for i in idx], sub)
    return {
        "mode": "dry-run" if args.dry_run else "live",
        "questions": str(args.questions),
        "latency_runs": runs,
        "bootstrap": {"resamples": BOOT_N, "seed": BOOT_SEED, "interval": "95% percentile"},
        "sets": sets,
        "latency": latency_figures(raw),
        "pins": pins,
        "preregistered": preregistered_line(),
        "verdict": verdict(sets["hand"]),
    }


def render_retrieval(rep: dict[str, Any]) -> str:
    def val(f: dict[str, Any]) -> str:
        if f["status"] != "measured":
            return f"NotApplicable ({f['reason']})"
        return f"{f['value'] * 100:.1f}%"

    lines = [
        f"knowledge-graph retrieval eval  mode={rep['mode']}  questions={rep['questions']}",
        f"recall@{TOP_K} counts expected pages among the first {TOP_K} distinct paths; "
        f"bootstrap: {rep['bootstrap']['resamples']} resamples, seed {rep['bootstrap']['seed']}, "
        f"{rep['bootstrap']['interval']}",
    ]
    if rep["mode"] == "dry-run":
        lines.append("SCRIPTED ARMS: plumbing only, the numbers say nothing about any retriever.")
    for s in SETS:
        d = rep["sets"][s]
        tag = (
            "weak gold (typed edges shared with expansion)"
            if s == "weak"
            else "hand-written (carries goal 1)"
        )
        lines += ["", f"== {s}: {tag}  n={d['n']}"]
        if d["n"] == 0:
            lines.append(f"  recall@{TOP_K}: NotApplicable ({d['reason']})")
            continue
        for a, f in d["arms"].items():
            lines.append(f"  {a:<13} recall@{TOP_K} {val(f['recall5'])} (n={d['n']})")
            c = f["vs_reference"]
            if c["status"] == "measured":
                ci = (
                    f"95% CI {c['lo'] * 100:+.1f}..{c['hi'] * 100:+.1f}"
                    if "lo" in c
                    else f"interval NotApplicable ({c['reason']})"
                )
                lines.append(
                    f"    vs {REFERENCE_ARM} (paired): {c['diff'] * 100:+.1f} points, {ci}"
                )
            else:
                lines.append(f"    vs {REFERENCE_ARM}: reference arm")
            if a.startswith("graph"):
                g, e = f["grounding"], f["entry_miss"]
                gn = f" (n={g['n']})" if g["status"] == "measured" else ""
                lines.append(f"    grounding rate: {val(g)}{gn}")
                lines.append(f"    entry-miss rate: {val(e)} (n={e['n']})")
    lines += ["", f"p95 in-process latency (ms, {rep['latency_runs']} runs, latency only):"]
    for a, f in rep["latency"].items():
        got = (
            f"{f['p95_ms']:.1f} (n={f['n']} calls)"
            if f["status"] == "measured"
            else f"NotApplicable ({f['reason']})"
        )
        lines.append(f"  {a:<13} {got}")
    lines += ["", "pinned ids:"] + [f"  {k}: {v}" for k, v in rep["pins"].items()]
    lines += ["", f"preregistered: {rep['preregistered']}", ""]
    v = rep["verdict"]
    if v["verdict"] == "cannot be read yet":
        lines.append(f"goal-1 verdict: cannot be read yet — {v['note']}")
    else:
        lines.append(
            f"goal-1 verdict ({VERDICT_ARM} vs {REFERENCE_ARM}, hand set, bar {BAR_POINTS} "
            f"points): {v['verdict']} ({v['points']:+.1f} points)"
        )
        if "note" in v:
            lines.append(f"  note: {v['note']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, jev_client: httpx.AsyncClient | None = None) -> int:
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
    ap.add_argument("--retrieval", action="store_true", help="run the four-arm retrieval eval")
    ap.add_argument("--questions", default=str(QUESTIONS_PATH))
    ap.add_argument("--db", default=None, help="SQLite graph file for the retrieval eval")
    ap.add_argument("--build-id", default=None, help="graph build to read (default: promoted)")
    ap.add_argument("--latency-runs", type=int, default=LATENCY_RUNS)
    args = ap.parse_args(argv)

    if args.split == "all" and not args.dry_run:
        _refuse("refused: --split all pools the training rows; it is for --dry-run only")
    if args.repeats < 1:
        _refuse("refused: --repeats must be >= 1")

    settings = Settings.load()
    if args.retrieval:
        rep = run_retrieval(args, settings)
        print(json.dumps(rep, indent=2) if args.json else render_retrieval(rep))
        return 0
    store = open_store(args, settings)
    seat = select_seat(args, settings, jev_client=jev_client)
    rows, path, source = load_gold(args)
    windows = _windows(rows, args, settings)
    repeats = asyncio.run(_judge_all(seat, rows, windows, args.repeats, args.split == "all"))
    if store is not None:
        store.close()
    rep = build_report(args, seat, rows, path, source, repeats)
    print(json.dumps(rep, indent=2) if args.json else render_text(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
