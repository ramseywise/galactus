"""Build orchestration: dry run, full scripted pipeline, halting, promote refusals."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from kg_fakes import SCRIPTED, ScriptedProposer, ScriptedSeat

from experiments.io import read_record
from experiments.record import NotApplicable
from kg import build as kb
from kg.config import Settings
from kg.contract import NotApproved, approve, load_pack
from kg.models import Candidate, NotRun, PageResult, Usage, Verdict
from kg.profile import BuildRefused
from kg.store import SqliteStore

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
REAL_PACK = HERE.parent / "packs" / "eval-v1.json"

CAL = Candidate(
    subject="ECE",
    subject_type="Metric",
    relation="measures",
    object="Calibration",
    object_type="Method",
    quote="Calibration is measured with ECE, and the Gold Set supplies the labels.",
)
GRADER = Candidate(
    subject="grader",
    subject_type="Role",
    relation="produces",
    object="rubric",
    object_type="Artifact",
    quote="A rubric is an Artifact that a grader produces before scoring begins.",
)
REQUIRES = Candidate(
    subject="Rubric grading",
    subject_type="Method",
    relation="requires",
    object="named wrong answers",
    object_type="Artifact",
    quote="Rubric grading requires named wrong answers for each criterion.",
)
BAD_QUOTE = CAL.model_copy(update={"quote": "this sentence is nowhere in the page at all"})


def settings_for(root: Path = FIXTURES, **kw: object) -> Settings:
    return Settings(
        anthropic_api_key=None,
        openrouter_api_key=None,
        neo4j_uri=None,
        corpus_root=root,
        librarian_root=Path("."),
        **kw,  # type: ignore[arg-type]
    )


class Env:
    """Everything a build touches, under tmp_path."""

    def __init__(self, tmp: Path, *, approved: bool = True, root: Path = FIXTURES) -> None:
        self.pack_path = tmp / "eval-v1.json"
        shutil.copy(REAL_PACK, self.pack_path)
        if approved:
            approve(self.pack_path, "test-human")
        self.pack = load_pack(self.pack_path)
        self.records = tmp / "records"
        self.decisions = tmp / "decisions"
        self.store = SqliteStore(tmp / "kg.db", corpus_root=root)
        self.settings = settings_for(root)

    def run(
        self,
        proposer: object,
        seat: object | None = None,
        *,
        dry_run: bool = False,
        build_id: str = "b1",
        settings: Settings | None = None,
    ) -> kb.BuildReport:
        return kb.build(
            "pages",
            settings or self.settings,
            proposer,
            seat or ScriptedSeat(),
            None if dry_run else self.store,
            pack=self.pack,
            pack_path=self.pack_path,
            dry_run=dry_run,
            records_dir=self.records,
            build_id=build_id,
        )


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


def good_proposer() -> ScriptedProposer:
    return ScriptedProposer({"pages/normal.md": [CAL], "pages/injected.md": [GRADER]})


# -- dry run ----------------------------------------------------------------------------


def test_dry_run_names_every_denominator_and_separates_not_run(env: Env) -> None:
    proposer = ScriptedProposer()
    seat = ScriptedSeat()
    r = env.run(proposer, seat, dry_run=True)
    assert proposer.calls == [] and seat.calls == []
    assert r.status == "dry_run" and r.pages_total == 3
    assert r.pages_not_run == 3 and r.pages_no_candidates == 0
    assert isinstance(r.cost_usd, NotApplicable) and r.cost_usd.reason == "dry run"
    assert isinstance(r.band_rate, NotApplicable)
    assert not r.promotable
    text = r.render()
    for phrase in (
        "3 profiled = 0 proposed + 0 no_candidates + 3 not_run",
        "candidates: 0 proposed",
        "0 verdicts",
        "not_run: all 3 of 3 pages",
        "DRY RUN",
    ):
        assert phrase in text


def test_dry_run_with_unapproved_pack_still_reports_and_says_so(tmp_path: Path) -> None:
    e = Env(tmp_path, approved=False)
    r = e.run(ScriptedProposer(), dry_run=True)
    assert not r.pack_approved
    assert "pack eval v1 not approved; dry run only" in r.render()


def test_live_build_refuses_unapproved_pack(tmp_path: Path) -> None:
    e = Env(tmp_path, approved=False)
    with pytest.raises(NotApproved):
        e.run(ScriptedProposer())


def test_dry_run_record_round_trips(env: Env) -> None:
    r = env.run(ScriptedProposer(), dry_run=True)
    rec = read_record(env.records / f"{r.build_id}.json")
    assert rec.data.n_rows == 3 and rec.data.frame_hash == r.profile_hash
    assert rec.run_kind == "kg-build"
    assert rec.execution.resolved_config["dry_run"] is True
    assert rec.metrics["not_run_count"] == 3.0
    assert "cost_usd" not in rec.metrics
    assert rec.execution.resolved_config["not_applicable_metrics"]["cost_usd"] == "dry run"


def test_estimate_over_ceiling_is_refused_before_any_call(env: Env) -> None:
    proposer = ScriptedProposer()
    s = settings_for(build_ceiling_usd=0.0001, band_ceiling_usd=1.0)
    with pytest.raises(BuildRefused, match="exceeds the build ceiling"):
        env.run(proposer, settings=s)
    assert proposer.calls == []


# -- full scripted pipeline --------------------------------------------------------------


def test_full_pipeline_accepts_and_records_denominators(env: Env) -> None:
    proposer = ScriptedProposer(
        {"pages/normal.md": [CAL, BAD_QUOTE], "pages/injected.md": [GRADER]}
    )
    r = env.run(proposer)
    assert r.status == "complete"
    assert (r.pages_proposed, r.pages_no_candidates, r.pages_not_run) == (2, 1, 0)
    assert (r.candidates_proposed, r.gate_failed, r.gate_passed) == (3, 1, 2)
    assert r.gate_failures_by_gate == {"verbatim": 1, "attested": 1}
    assert r.verdicts == 2 and r.accepted == 2 and r.band_rate == 0.0
    assert r.gate_pass_rate == pytest.approx(2 / 3)
    assert r.promotable, r.reasons
    stats = env.store.stats("b1")
    assert stats.status == "complete" and stats.triples == {"accept": 2}
    # complete is not promoted: default reads still serve nothing
    assert env.store.hops({"grader"}, 1) == []
    rec = read_record(env.records / "b1.json")
    assert rec.headline_metric == "band_rate" and rec.metrics["band_rate"] == 0.0
    assert rec.metrics["accepted_count"] == 2.0


def test_judge_not_run_is_counted_and_page_becomes_not_run(env: Env) -> None:
    seat = ScriptedSeat(lambda c, w: NotRun(reason="sdk_error: boom"))
    r = env.run(good_proposer(), seat)
    assert r.judge_not_run == 2 and r.verdicts == 0 and r.accepted == 0
    assert isinstance(r.band_rate, NotApplicable)
    assert {p for p, _ in r.not_run} == {"pages/normal.md", "pages/injected.md"}
    assert env.store.triples("b1") == []
    assert not r.promotable


def test_duplicates_are_counted_not_judged_twice(env: Env) -> None:
    seat = ScriptedSeat()
    r = env.run(ScriptedProposer({"pages/normal.md": [CAL, CAL]}), seat)
    assert r.duplicates == 1 and r.judged_candidates == 1 and len(seat.calls) == 1


def test_no_candidates_everywhere_is_not_promotable_and_band_rate_not_applicable(env: Env) -> None:
    r = env.run(ScriptedProposer())
    assert r.pages_no_candidates == 3 and r.accepted == 0
    assert isinstance(r.band_rate, NotApplicable)
    assert not r.promotable
    assert any("zero accepted" in x for x in r.reasons)
    assert any("more than half" in x for x in r.reasons)
    rec = read_record(env.records / "b1.json")
    assert "band_rate" not in rec.metrics  # never 0.0
    assert rec.headline_metric == "accepted_count"
    assert "band_rate" in rec.execution.resolved_config["not_applicable_metrics"]
    with pytest.raises(BuildRefused, match="zero accepted"):
        kb.promote(env.store, "b1", records_dir=env.records, decisions_dir=env.decisions)


# -- halting -----------------------------------------------------------------------------


def test_meter_halt_after_accepts_serves_nothing(env: Env) -> None:
    calls = {"n": 0}

    def rule(c: Candidate, w: str) -> Verdict:
        calls["n"] += 1
        big = calls["n"] >= 2
        usage = (
            Usage(model="claude-sonnet-5-5", input_tokens=50_000_000, output_tokens=0)
            if big
            else SCRIPTED
        )
        return Verdict(label="supported", score=0.95, usage=usage)

    proposer = ScriptedProposer({"pages/injected.md": [GRADER, REQUIRES]})
    r = env.run(proposer, ScriptedSeat(rule))
    assert r.status == "halted" and "runtime meter" in (r.halted_reason or "")
    stats = env.store.stats("b1")
    assert stats.status == "halted" and stats.triples == {"accept": 1}  # accepts were written
    assert env.store.hops({"grader"}, 1) == []
    assert env.store.passages({"grader"}, 1) == []
    assert len(env.store.hops({"grader"}, 1, build_id="b1")) == 1
    assert "pages/normal.md" in {p for p, _ in r.not_run}  # never reached
    assert "pages/injected.md" in {p for p, _ in r.not_run}  # cut off mid-page
    assert not r.promotable
    with pytest.raises(BuildRefused, match="halted"):
        kb.promote(env.store, "b1", records_dir=env.records, decisions_dir=env.decisions)


def test_band_rate_over_limit_halts(env: Env) -> None:
    r = env.run(good_proposer(), ScriptedSeat(lambda c, w: ("unclear", 0.5)))
    assert r.status == "halted" and "band rate" in (r.halted_reason or "")
    assert env.store.stats("b1").status == "halted"


def test_crash_marks_halted_and_reraises(env: Env) -> None:
    class Boom(ScriptedProposer):
        async def propose(self, page, pack):  # type: ignore[no-untyped-def]
            raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError, match="kaboom"):
        env.run(Boom())
    assert env.store.stats("b1").status == "halted"


def test_unavailable_seat_refuses_by_name(env: Env) -> None:
    seat = ScriptedSeat(available=(False, "ANTHROPIC_API_KEY not set"))
    with pytest.raises(BuildRefused, match="ANTHROPIC_API_KEY"):
        env.run(good_proposer(), seat)


# -- promote / unpromote / verify / repeat -----------------------------------------------


def not_run_proposer() -> ScriptedProposer:
    return ScriptedProposer(
        {
            "pages/normal.md": PageResult(
                page_path="pages/normal.md", status="not_run", reason="truncated: max_tokens"
            ),
            "pages/injected.md": [GRADER],
        }
    )


def test_promote_refuses_naming_the_not_run_page_then_waiver_allows(env: Env) -> None:
    r = env.run(not_run_proposer())
    assert r.pages_not_run == 1 and not r.promotable
    with pytest.raises(BuildRefused, match=r"pages/normal\.md"):
        kb.promote(env.store, "b1", records_dir=env.records, decisions_dir=env.decisions)
    with pytest.raises(BuildRefused, match="--reason"):
        kb.promote(
            env.store,
            "b1",
            records_dir=env.records,
            decisions_dir=env.decisions,
            waive=["pages/normal.md"],
        )
    waived = kb.promote(
        env.store,
        "b1",
        records_dir=env.records,
        decisions_dir=env.decisions,
        waive=["pages/normal.md"],
        reason="page is a stub",
    )
    assert waived == ["pages/normal.md"]
    assert env.store.stats("b1").status == "promoted"
    assert len(env.store.hops({"grader"}, 1)) == 1
    kinds = [e["kind"] for e in kb.read_decisions(env.decisions, "b1")]
    assert kinds == ["waiver", "promote"]
    assert kb.read_decisions(env.decisions, "b1")[0]["reason"] == "page is a stub"


def test_waiver_cannot_name_a_page_that_is_not_not_run(env: Env) -> None:
    env.run(not_run_proposer())
    with pytest.raises(BuildRefused, match="not not_run"):
        kb.promote(
            env.store,
            "b1",
            records_dir=env.records,
            decisions_dir=env.decisions,
            waive=["pages/injected.md"],
            reason="x",
        )


def test_unpromote_restores_previous_build(env: Env) -> None:
    env.run(good_proposer(), build_id="b1")
    env.run(good_proposer(), build_id="b2")
    kw = {"records_dir": env.records, "decisions_dir": env.decisions}
    kb.promote(env.store, "b1", **kw)
    kb.promote(env.store, "b2", **kw)
    assert env.store.stats("b1").status == "complete"
    assert env.store.stats("b2").status == "promoted"
    assert kb.unpromote(env.store, "b2", decisions_dir=env.decisions) == "b1"
    assert env.store.stats("b1").status == "promoted"
    assert env.store.stats("b2").status == "complete"
    assert kb.current_promoted(env.decisions) == "b1"


def test_verify_flags_a_quote_the_corpus_no_longer_contains(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    shutil.copytree(FIXTURES / "pages", root / "pages")
    e = Env(tmp_path, root=root)
    e.run(good_proposer())
    ok = kb.verify(e.store, "b1", root)
    assert (ok.checked, ok.fresh, ok.stale) == (2, 2, [])
    (root / "pages" / "normal.md").write_text("# gone\n\nNothing here now.\n", encoding="utf-8")
    bad = kb.verify(e.store, "b1", root)
    assert bad.fresh == 1 and len(bad.stale) == 1 and bad.stale[0][0] == "pages/normal.md"


def test_repeat_reports_jaccard_over_canonical_keys(env: Env) -> None:
    from kg.profile import iter_pages

    page = next(p for p in iter_pages(FIXTURES, "pages") if p.path == "pages/normal.md")
    import asyncio

    same = asyncio.run(kb.repeat(page, env.pack, ScriptedProposer({page.path: [CAL]}), 3))
    assert same == 1.0
    none = asyncio.run(kb.repeat(page, env.pack, ScriptedProposer(), 3))
    assert isinstance(none, NotApplicable)


# -- real domain -------------------------------------------------------------------------


def test_real_eval_domain_dry_run_profiles_80_pages_with_zero_spend(tmp_path: Path) -> None:
    root = os.environ.get("KG_CORPUS_ROOT")
    if not root:
        pytest.skip("KG_CORPUS_ROOT is not set; real-corpus dry run not run")
    e = Env(tmp_path, root=Path(root).expanduser())
    proposer, seat = ScriptedProposer(), ScriptedSeat()
    r = kb.build(
        "eval",
        e.settings,
        proposer,
        seat,
        None,
        pack=e.pack,
        pack_path=e.pack_path,
        dry_run=True,
        records_dir=e.records,
    )
    assert r.pages_total == 80 and r.pages_not_run == 80
    assert proposer.calls == [] and seat.calls == []
    assert isinstance(r.cost_usd, NotApplicable)
