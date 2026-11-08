"""Build orchestration: profile -> refuse -> propose -> gates -> judge -> route -> store.

A build opens in `building` and flips to `complete` only after every page is done. A
`BuildHalted` (band rate, runtime meter) or a crash marks it `halted`; the store serves
promoted builds only, so a halted build's partial accepts are never served (fog FA-001).
The pre-build estimate is a refusal before spend; the runtime meter is the stop during it
(fog FA-010). `not_run` pages and candidates are counted apart from `no_candidates`, and a
rate with no denominator is `NotApplicable`, never 0.0 (fog FA-002).

Human decisions (approvals, review decisions, waivers, promotions) append to
`<decisions_dir>/<build_id>.jsonl`, outside the store, so deleting or rebuilding the store
cannot lose them (fog FA-005).

Phase-B note: promotion will additionally require a measured accept-tier precision on live
proposer output in the decisions file (fog FA-004). Not enforced in Phase A.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kg.config import Settings
from kg.contract import NotApproved, Pack, pack_hash, require_approved
from kg.gates import dedupe, run_gates
from kg.judge.seat import JudgeSeat, window
from kg.models import (
    Candidate,
    GateReport,
    Judgement,
    NotApplicable,
    NotRun,
    PageResult,
    Tier,
    Triple,
    Usage,
    Verdict,
)
from kg.observability import OP_JUDGE, OP_PROPOSE, span
from kg.profile import (
    BuildRefused,
    Page,
    Profile,
    census,
    estimate_cost,
    iter_pages,
    refuse_if_empty,
    refuse_if_over,
)
from kg.profile.prices_table import PRICES, SOURCE_DATE
from kg.propose.proposer import Proposer
from kg.route import (
    BuildHalted,
    Prices,
    assign,
    band_rate,
    halt_if_over,
    thresholds,
)
from kg.store import GraphStore

RUN_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS_DIR = RUN_DIR / "docs" / "records"
DEFAULT_DECISIONS_DIR = RUN_DIR / "docs" / "decisions"
DEFAULT_DB_PATH = RUN_DIR / "data" / "kg.sqlite3"

Rate = float | NotApplicable


# -- report -------------------------------------------------------------------------------


@dataclass
class BuildReport:
    """Every number carries its denominator in `render()`; `not_run` is separate throughout."""

    build_id: str
    domain: str
    dry_run: bool
    status: str  # dry_run | complete | halted
    pack_name: str
    pack_hash: str
    pack_approved: bool
    profile_hash: str
    estimate_usd: float
    estimate_basis: str
    pages_total: int
    pages_proposed: int = 0
    pages_no_candidates: int = 0
    pages_not_run: int = 0
    candidates_proposed: int = 0
    gate_failed: int = 0
    gate_failures_by_gate: dict[str, int] = field(default_factory=dict)
    gate_passed: int = 0
    duplicates: int = 0
    judged_candidates: int = 0  # kept after dedupe: what the judge was asked about
    verdicts: int = 0
    judge_not_run: int = 0
    tiers: dict[str, int] = field(default_factory=lambda: {"accept": 0, "review": 0, "reject": 0})
    band_rate: Rate = field(default_factory=lambda: NotApplicable("no judged candidates"))
    gate_pass_rate: Rate = field(default_factory=lambda: NotApplicable("no candidates proposed"))
    cost_usd: Rate = field(default_factory=lambda: NotApplicable("dry run"))
    cost_basis: str = ""
    not_run: list[tuple[str, str]] = field(default_factory=list)
    no_candidates: list[str] = field(default_factory=list)
    halted_reason: str | None = None
    promotable: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> int:
        return self.tiers["accept"]

    def render(self) -> str:
        n = self.pages_total
        lines = [
            f"build {self.build_id}  domain={self.domain}  status={self.status}"
            + ("  (DRY RUN: no model calls, zero spend)" if self.dry_run else ""),
        ]
        if not self.pack_approved:
            lines.append(f"pack {self.pack_name} not approved; dry run only")
        lines += [
            f"estimate: ${self.estimate_usd:.2f}  ({self.estimate_basis})",
            f"cost: {_fmt_na(self.cost_usd, '${:.4f}')}  {self.cost_basis}".rstrip(),
            f"pages: {n} profiled = {self.pages_proposed} proposed + "
            f"{self.pages_no_candidates} no_candidates + {self.pages_not_run} not_run",
            f"candidates: {self.candidates_proposed} proposed = {self.gate_failed} failed a gate "
            f"+ {self.gate_passed} passed all gates",
            f"gate pass rate: {_ratio(self.gate_passed, self.candidates_proposed, self.gate_pass_rate)}"
            " of candidates proposed",
            f"gates passed {self.gate_passed} = {self.duplicates} duplicate + "
            f"{self.judged_candidates} sent to the judge",
            f"judged: {self.judged_candidates} sent = {self.verdicts} verdicts + "
            f"{self.judge_not_run} judge not_run",
            f"tiers (of {self.verdicts} verdicts): accept {self.tiers['accept']}, "
            f"review {self.tiers['review']}, reject {self.tiers['reject']}",
            f"band rate: {_ratio(self.tiers['review'], self.verdicts, self.band_rate)}"
            " of verdicts routed to review",
        ]
        if self.gate_failures_by_gate:
            lines.append(
                "gate failures: "
                + ", ".join(f"{g} {c}" for g, c in sorted(self.gate_failures_by_gate.items()))
            )
        if self.not_run and self.dry_run:
            lines.append(f"not_run: all {len(self.not_run)} of {n} pages (reason: dry run)")
        elif self.not_run:
            lines.append(
                f"not_run ({len(self.not_run)} of {n} pages, separate from no_candidates):"
            )
            lines += [f"  {p}: {why}" for p, why in self.not_run]
        if self.halted_reason:
            lines.append(f"HALTED: {self.halted_reason}")
        lines.append(
            "promotable: yes"
            if self.promotable
            else "promotable: NO" + "".join(f"\n  - {r}" for r in self.reasons)
        )
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        d = dict(self.__dict__.items())
        for k in ("band_rate", "gate_pass_rate", "cost_usd"):
            d[k] = _enc(d[k])
        d["not_run"] = [list(x) for x in self.not_run]
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> BuildReport:
        d = dict(d)
        for k in ("band_rate", "gate_pass_rate", "cost_usd"):
            d[k] = _dec(d[k])
        d["not_run"] = [(p, why) for p, why in d["not_run"]]
        return cls(**d)


def _enc(v: Rate) -> Any:
    return {"not_applicable": v.reason} if isinstance(v, NotApplicable) else v


def _dec(v: Any) -> Rate:
    return NotApplicable(v["not_applicable"]) if isinstance(v, dict) else v


def _fmt_na(v: Rate, fmt: str) -> str:
    return f"n/a ({v.reason})" if isinstance(v, NotApplicable) else fmt.format(v)


def _ratio(num: int, den: int, rate: Rate) -> str:
    if isinstance(rate, NotApplicable):
        return f"n/a ({rate.reason}; denominator {den})"
    return f"{rate:.3f} = {num}/{den}"


def report_path(records_dir: Path, build_id: str) -> Path:
    return records_dir / f"{build_id}.report.json"


def load_report(records_dir: Path, build_id: str) -> BuildReport:
    path = report_path(records_dir, build_id)
    if not path.exists():
        raise BuildRefused(f"no build report for {build_id!r} at {path}")
    return BuildReport.from_json(json.loads(path.read_text(encoding="utf-8")))


# -- decisions ----------------------------------------------------------------------------


def decisions_file(decisions_dir: Path, build_id: str) -> Path:
    return decisions_dir / f"{build_id}.jsonl"


def append_decision(decisions_dir: Path, build_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Append one human decision as a JSON line; stamps `at` and `seq`."""
    decisions_dir.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(UTC).isoformat(), "seq": time.time_ns(), **event}
    with decisions_file(decisions_dir, build_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def read_decisions(decisions_dir: Path, build_id: str | None = None) -> list[dict[str, Any]]:
    files = (
        [decisions_file(decisions_dir, build_id)]
        if build_id
        else sorted(decisions_dir.glob("*.jsonl"))
    )
    rows = [
        json.loads(line)
        for f in files
        if f.exists()
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return sorted(rows, key=lambda r: r.get("seq", 0))


# -- meter --------------------------------------------------------------------------------


def usage_usd(usage: Usage | None) -> float:
    """Dollars for one metered call. Zero tokens cost nothing even for an unpriced model
    (scripted fakes); any tokens on an unpriced model halt rather than count as free."""
    if usage is None or (usage.input_tokens == 0 and usage.output_tokens == 0):
        return 0.0
    price = PRICES.get(usage.model)
    if price is None:
        raise BuildHalted(f"metered tokens on unpriced model {usage.model!r}; halting")
    return (
        usage.input_tokens * price.input_per_mtok + usage.output_tokens * price.output_per_mtok
    ) / 1e6


class _Meter:
    def __init__(self, ceiling: float) -> None:
        self.ceiling = ceiling
        self.usd = 0.0

    def add(self, usage: Usage | None) -> None:
        self.usd += usage_usd(usage)
        if self.usd > self.ceiling:
            raise BuildHalted(
                f"runtime meter ${self.usd:.4f} exceeds the build ceiling ${self.ceiling:.2f}"
            )


# -- build --------------------------------------------------------------------------------


def new_build_id(domain: str, profile: Profile) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{domain}-{stamp}-{profile.profile_hash[:8]}"


async def abuild(
    domain: str,
    settings: Settings,
    proposer: Proposer,
    seat: JudgeSeat,
    store: GraphStore | None,
    *,
    pack: Pack,
    pack_path: Path | None = None,
    dry_run: bool,
    prices: Prices | None = None,
    records_dir: Path | None = None,
    build_id: str | None = None,
    on_page: Callable[[str], None] | None = None,
) -> BuildReport:
    """Run one build. `store` may be None only for a dry run (nothing is written)."""
    corpus_root = settings.corpus_root
    profile = census(corpus_root, domain)
    refuse_if_empty(profile)
    estimate = estimate_cost(
        profile, proposer_model=settings.proposer_model, judge_model=settings.judge_model
    )
    refuse_if_over(estimate, settings.build_ceiling_usd)

    approved = True
    try:
        if pack_path is None:
            raise NotApproved("no pack path given, so no approval record can be checked")
        require_approved(pack, pack_path)
    except NotApproved:
        if not dry_run:
            raise
        approved = False

    build_id = build_id or new_build_id(domain, profile)
    report = BuildReport(
        build_id=build_id,
        domain=domain,
        dry_run=dry_run,
        status="dry_run" if dry_run else "building",
        pack_name=f"{pack.name} v{pack.version}",
        pack_hash=pack_hash(pack),
        pack_approved=approved,
        profile_hash=profile.profile_hash,
        estimate_usd=estimate.usd,
        estimate_basis=estimate.basis,
        pages_total=profile.page_count,
    )

    if dry_run:
        report.pages_not_run = profile.page_count
        report.not_run = [(p.path, "dry run") for p in profile.pages]
        report.cost_usd = NotApplicable("dry run")
        report.reasons = ["dry run: no model was called, nothing was judged"]
        _finish(report, store=None, records_dir=records_dir)
        return report

    if store is None:
        raise BuildRefused("a live build needs a store")
    ok, why = seat.available()
    if not ok:
        raise BuildRefused(f"judge seat {seat.name!r} unavailable: {why}")

    t_lo, t_hi = thresholds(prices or Prices())
    meter = _Meter(settings.build_ceiling_usd)
    store.open_build(build_id, report.pack_hash, profile.profile_hash)
    report.cost_basis = f"metered usage x kg.profile.prices_table (as of {SOURCE_DATE})"
    all_tiers: list[Tier] = []
    pages = list(iter_pages(corpus_root, domain))
    done: set[str] = set()
    try:
        for page in pages:
            await _one_page(
                page, pack, proposer, seat, store, build_id, report, meter, all_tiers, t_lo, t_hi
            )
            done.add(page.path)
            if on_page:
                on_page(page.path)
        report.band_rate = band_rate(all_tiers)
        halt_if_over(report.band_rate, settings.band_rate_halt)
    except BuildHalted as exc:
        report.halted_reason = str(exc)
        report.band_rate = band_rate(all_tiers)
        # A page cut off mid-way, and every page never reached, is not_run, not absent.
        for page in pages:
            if page.path not in done:
                _mark_not_run(
                    store, build_id, report, page.path, "build halted before this page finished"
                )
        store.set_build_status(build_id, "halted")
        report.status = "halted"
    except BaseException:
        store.set_build_status(build_id, "halted")
        report.status = "halted"
        raise
    else:
        store.set_build_status(build_id, "complete")
        report.status = "complete"
    report.cost_usd = round(meter.usd, 6)
    _finish(report, store=store, records_dir=records_dir)
    return report


def _mark_not_run(
    store: GraphStore, build_id: str, report: BuildReport, path: str, reason: str
) -> None:
    store.write_page_result(build_id, PageResult(page_path=path, status="not_run", reason=reason))
    report.pages_not_run += 1
    report.not_run.append((path, reason))


async def _one_page(
    page: Page,
    pack: Pack,
    proposer: Proposer,
    seat: JudgeSeat,
    store: GraphStore,
    build_id: str,
    report: BuildReport,
    meter: _Meter,
    all_tiers: list[Tier],
    t_lo: float,
    t_hi: float,
) -> None:
    with span(OP_PROPOSE, getattr(proposer, "model", None) or "proposer", page=page.path):
        result = await proposer.propose(page, pack)
    meter.add(proposer.last_usage)

    if result.status == "not_run":
        store.write_page_result(build_id, result)
        report.pages_not_run += 1
        report.not_run.append((page.path, result.reason or "not_run"))
        return
    if result.status == "no_candidates":
        store.write_page_result(build_id, result)
        report.pages_no_candidates += 1
        report.no_candidates.append(page.path)
        return

    report.candidates_proposed += len(result.candidates)
    passed: list[tuple[Triple, GateReport]] = []
    for cand in result.candidates:
        g = run_gates(cand, page.body, pack, page.path)
        if g.passed:
            passed.append((Triple.from_candidate(cand, page.path), g))
        else:
            report.gate_failed += 1
            for name in g.failed:
                report.gate_failures_by_gate[name] = report.gate_failures_by_gate.get(name, 0) + 1
    report.gate_passed += len(passed)
    kept = dedupe(t for t, _ in passed)
    report.duplicates += len(kept.duplicates)
    by_key = {}
    for t, g in passed:
        by_key.setdefault(t.key, (t, g))

    judge_failures: list[str] = []
    for triple in kept.kept:
        _, g = by_key[triple.key]
        report.judged_candidates += 1
        ev = g.evidence()
        cand = g.candidate
        out = await _judge(seat, cand, window(page.body, ev.span), meter)
        if isinstance(out, NotRun):
            report.judge_not_run += 1
            judge_failures.append(out.reason)
            continue
        report.verdicts += 1
        tier = assign(out, t_lo, t_hi)
        all_tiers.append(tier)
        report.tiers[tier] += 1
        store.write_triple(build_id, triple, ev, _judgement(seat, out), tier)

    if judge_failures:
        reason = f"judge not_run for {len(judge_failures)} candidate(s): {judge_failures[0]}"
        _mark_not_run(store, build_id, report, page.path, reason)
        return
    store.write_page_result(build_id, result)
    report.pages_proposed += 1


async def _judge(seat: JudgeSeat, cand: Candidate, win: str, meter: _Meter) -> Verdict | NotRun:
    with span(OP_JUDGE, getattr(seat, "model", None) or seat.name, seat=seat.name) as sp:
        out = await seat.judge(cand, win)
        if out.usage is not None:
            sp.record_usage(out.usage.input_tokens, out.usage.output_tokens)
    meter.add(out.usage)
    return out


def _judgement(seat: JudgeSeat, v: Verdict) -> Judgement:
    return Judgement(seat=seat.name, label=v.label, score=v.score, model=v.usage.model)


def _finish(report: BuildReport, *, store: GraphStore | None, records_dir: Path | None) -> None:
    n_cand = report.candidates_proposed
    report.gate_pass_rate = (
        report.gate_passed / n_cand if n_cand else NotApplicable("no candidates proposed")
    )
    if not report.dry_run:
        report.promotable, report.reasons = assess(report, waived=set())
    if records_dir is not None:
        from kg.conformance import write_conformance

        records_dir.mkdir(parents=True, exist_ok=True)
        report_path(records_dir, report.build_id).write_text(
            json.dumps(report.to_json(), indent=2, sort_keys=True), encoding="utf-8"
        )
        write_conformance(report, records_dir)


def assess(report: BuildReport, waived: set[str]) -> tuple[bool, list[str]]:
    """Whether `report` may be promoted, and why not. `waived` names not_run pages a human
    accepted losing; no other refusal is waivable."""
    reasons: list[str] = []
    if report.dry_run:
        reasons.append("dry run: nothing was proposed or judged")
    if report.status != "complete":
        reasons.append(f"build status is {report.status!r}, not complete")
    open_pages = [(p, why) for p, why in report.not_run if p not in waived]
    if open_pages:
        names = ", ".join(p for p, _ in open_pages)
        reasons.append(f"{len(open_pages)} page(s) not_run: {names}")
    if report.pages_total and report.accepted == 0:
        reasons.append(f"zero accepted triples over {report.pages_total} page(s)")
    if report.pages_total and report.pages_no_candidates * 2 > report.pages_total:
        reasons.append(
            f"no_candidates on {report.pages_no_candidates} of {report.pages_total} pages "
            "(more than half)"
        )
    return (not reasons, reasons)


def build(*args: Any, **kwargs: Any) -> BuildReport:
    """Sync wrapper over `abuild` (same arguments)."""
    return asyncio.run(abuild(*args, **kwargs))


# -- promote / unpromote / verify / repeat -----------------------------------------------


def current_promoted(decisions_dir: Path) -> str | None:
    """Replay promote/unpromote events (across all builds) to find the promoted build."""
    stack: list[str] = []
    for ev in read_decisions(decisions_dir):
        if ev.get("kind") == "promote":
            stack.append(ev["build_id"])
        elif ev.get("kind") == "unpromote" and ev["build_id"] in stack:
            stack.remove(ev["build_id"])
    return stack[-1] if stack else None


def promote(
    store: GraphStore,
    build_id: str,
    *,
    records_dir: Path,
    decisions_dir: Path,
    waive: list[str] | None = None,
    reason: str | None = None,
) -> list[str]:
    """Promote a complete build or raise BuildRefused naming why. Returns waived pages."""
    waived = set(waive or [])
    if waived and not (reason and reason.strip()):
        raise BuildRefused("--waive needs --reason: a waiver records why the page may be lost")
    report = load_report(records_dir, build_id)
    stats = store.stats(build_id)
    if stats.status != "complete":
        raise BuildRefused(f"build {build_id} is {stats.status!r}; only a complete build promotes")
    unknown = waived - {p for p, _ in report.not_run}
    if unknown:
        raise BuildRefused(f"--waive names pages that are not not_run: {sorted(unknown)}")
    ok, reasons = assess(report, waived)
    if not ok:
        raise BuildRefused(f"refusing to promote {build_id}: " + "; ".join(reasons))
    for page in sorted(waived):
        append_decision(
            decisions_dir,
            build_id,
            {"kind": "waiver", "page": page, "reason": reason},
        )
    previous = current_promoted(decisions_dir)
    if previous and previous != build_id:
        store.set_build_status(previous, "complete")
    store.set_build_status(build_id, "promoted")
    append_decision(
        decisions_dir, build_id, {"kind": "promote", "build_id": build_id, "previous": previous}
    )
    return sorted(waived)


def unpromote(store: GraphStore, build_id: str, *, decisions_dir: Path) -> str | None:
    """Demote `build_id` and restore the build it replaced. Returns the restored build id."""
    events = [e for e in read_decisions(decisions_dir, build_id) if e.get("kind") == "promote"]
    if store.stats(build_id).status != "promoted":
        raise BuildRefused(f"build {build_id} is not promoted")
    previous = events[-1].get("previous") if events else None
    store.set_build_status(build_id, "complete")
    restored = None
    if previous:
        try:
            store.set_build_status(previous, "promoted")
            restored = previous
        except KeyError:  # UnknownBuild: the previous build's rows were deleted
            restored = None
    append_decision(
        decisions_dir,
        build_id,
        {"kind": "unpromote", "build_id": build_id, "restored": restored},
    )
    return restored


@dataclass(frozen=True)
class VerifyResult:
    checked: int
    fresh: int
    stale: list[tuple[str, str]]  # (page, quote)
    missing_pages: list[str]


def verify(store: GraphStore, build_id: str, corpus_root: Path) -> VerifyResult:
    """Re-check every stored quote against the current normalised body."""
    from kg.profile import normalise

    bodies: dict[str, str | None] = {}
    fresh = 0
    stale: list[tuple[str, str]] = []
    rows = store.triples(build_id)
    for st in rows:
        page = st.evidence.page_path
        if page not in bodies:
            f = corpus_root / page
            bodies[page] = normalise(f.read_text(encoding="utf-8")) if f.is_file() else None
        body = bodies[page]
        if body is not None and st.evidence.quote in body:
            fresh += 1
        elif body is not None:
            stale.append((page, st.evidence.quote))
    missing = sorted(p for p, b in bodies.items() if b is None)
    return VerifyResult(checked=len(rows), fresh=fresh, stale=stale, missing_pages=missing)


async def repeat(page: Page, pack: Pack, proposer: Proposer, n: int) -> float | NotApplicable:
    """Run one page through the proposer `n` times; mean pairwise Jaccard over canonical keys.

    Candidates that fail a gate are excluded: agreement is measured on what would be stored.
    """
    if n < 2:
        raise ValueError("repeat needs n >= 2")
    sets: list[set[Any]] = []
    for _ in range(n):
        result = await proposer.propose(page, pack)
        keys = {
            Triple.from_candidate(c, page.path).key
            for c in result.candidates
            if run_gates(c, page.body, pack, page.path).passed
        }
        sets.append(keys)
    scores = []
    for i in range(n):
        for j in range(i + 1, n):
            union = sets[i] | sets[j]
            if union:
                scores.append(len(sets[i] & sets[j]) / len(union))
    if not scores:
        return NotApplicable("no run produced a candidate that passed the gates")
    return sum(scores) / len(scores)
