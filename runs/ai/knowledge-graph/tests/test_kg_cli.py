"""The `kg` CLI: argparse wiring, live-spend guard, decisions outside the store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kg_fakes import ScriptedProposer, ScriptedSeat
from test_kg_build import CAL, GRADER, REAL_PACK, Env, good_proposer

from kg import build as kb
from kg import cli

FIXTURES = Path(__file__).parent / "fixtures"


def argv(e: Env, *cmd: str) -> list[str]:
    return [
        *cmd,
        "--corpus-root", str(FIXTURES),
        "--db", str(e.store.db_path),
        "--records-dir", str(e.records),
        "--decisions-dir", str(e.decisions),
        "--pack", str(e.pack_path),
    ]  # fmt: skip


@pytest.fixture
def env(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> Env:
    return Env(tmp_path)


def test_every_command_is_registered() -> None:
    sub = next(a for a in cli.make_parser()._actions if a.dest == "command")
    assert set(sub.choices) == set(cli.COMMANDS)


@pytest.mark.parametrize("cmd", [c for c in cli.COMMANDS if c not in ("label",)])
def test_every_command_accepts_dry_run(cmd: str) -> None:
    ns, _ = cli.make_parser().parse_known_args(
        [cmd, *{"approve": ["pages", "--by", "x"], "propose": ["pages/a.md"], "repeat": ["pages/a.md"],
                "ask": ["x"]}.get(cmd, ["x"]), "--dry-run"]
    )  # fmt: skip
    assert ns.dry_run is True


def test_dry_run_build_on_unapproved_pack_reports(
    tmp_path: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    e = Env(tmp_path, approved=False)
    assert cli.main([*argv(e, "build", "pages"), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "pack eval v1 not approved; dry run only" in out
    assert "3 profiled = 0 proposed + 0 no_candidates + 3 not_run" in out
    assert not e.records.exists()  # a dry run writes no record unless asked


def test_dry_run_build_writes_record_when_asked(env: Env) -> None:
    assert cli.main([*argv(env, "build", "pages"), "--dry-run", "--write-record"]) == 0
    assert list(env.records.glob("*.json"))


def test_live_build_refuses_without_kg_live_naming_it(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(argv(env, "build", "pages"), proposer=good_proposer(), seat=ScriptedSeat())
    assert code == cli.EXIT_REFUSED
    assert "KG_LIVE=1" in capsys.readouterr().err


def test_repeat_and_propose_refuse_without_kg_live(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(argv(env, "repeat", "pages/normal.md"), proposer=ScriptedProposer()) == 2
    assert "KG_LIVE=1" in capsys.readouterr().err
    assert cli.main(argv(env, "propose", "pages/normal.md"), proposer=ScriptedProposer()) == 2


def test_live_build_unapproved_pack_refuses(
    tmp_path: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean_env.setenv("KG_LIVE", "1")
    e = Env(tmp_path, approved=False)
    code = cli.main(argv(e, "build", "pages"), proposer=good_proposer(), seat=ScriptedSeat())
    assert code == cli.EXIT_REFUSED
    assert "pack not approved" in capsys.readouterr().err


def test_approve_dry_run_writes_nothing(
    tmp_path: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    e = Env(tmp_path, approved=False)
    assert cli.main([*argv(e, "approve", "eval"), "--by", "me", "--dry-run"]) == 0
    assert not (tmp_path / "eval-v1.approval.json").exists()
    assert not e.decisions.exists()
    assert REAL_PACK.with_name("eval-v1.approval.json").exists() is False


def test_approve_records_the_decision(env: Env, tmp_path: Path) -> None:
    (tmp_path / "eval-v1.approval.json").unlink()
    assert cli.main([*argv(env, "approve", "eval"), "--by", "ramsey"]) == 0
    assert (tmp_path / "eval-v1.approval.json").exists()
    (row,) = kb.read_decisions(env.decisions, "approvals")
    assert row["kind"] == "approval" and row["by"] == "ramsey"


def run_live(
    env: Env, mp: pytest.MonkeyPatch, proposer: ScriptedProposer, build: str = "pages"
) -> int:
    mp.setenv("KG_LIVE", "1")
    return cli.main(argv(env, "build", build), proposer=proposer, seat=ScriptedSeat())


def test_full_cli_flow_with_fakes_and_decisions_outlive_the_store(
    env: Env, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_live(env, clean_env, good_proposer()) == 0
    out = capsys.readouterr().out
    (rid,) = [p.name.removesuffix(".report.json") for p in env.records.glob("*.report.json")]
    assert f"build {rid}" in out and "promotable: yes" in out

    assert cli.main(argv(env, "inspect", rid)) == 0
    assert cli.main(argv(env, "verify", rid)) == 0
    assert cli.main(argv(env, "promote", rid)) == 0
    assert cli.main(argv(env, "ask", "grader")) == 0
    assert "pages/injected.md" in capsys.readouterr().out

    assert cli.main(argv(env, "unpromote", rid)) == 0
    assert cli.main(argv(env, "ask", "grader")) == 0
    assert "nothing for 'grader'" in capsys.readouterr().out

    events = [e["kind"] for e in kb.read_decisions(env.decisions, rid)]
    assert events == ["promote", "unpromote"]
    env.store.db_path.unlink()  # the store is rebuildable; decisions are not
    assert [e["kind"] for e in kb.read_decisions(env.decisions, rid)] == events


def test_promote_via_cli_refuses_with_page_named_and_waiver_is_recorded(
    env: Env, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from test_kg_build import not_run_proposer

    assert run_live(env, clean_env, not_run_proposer()) == 0
    (rid,) = [p.name.removesuffix(".report.json") for p in env.records.glob("*.report.json")]
    capsys.readouterr()
    assert cli.main(argv(env, "promote", rid)) == cli.EXIT_REFUSED
    assert "pages/normal.md" in capsys.readouterr().err
    code = cli.main(
        [*argv(env, "promote", rid), "--waive", "pages/normal.md", "--reason", "stub page"]
    )
    assert code == 0
    waiver = kb.read_decisions(env.decisions, rid)[0]
    assert waiver["kind"] == "waiver" and waiver["reason"] == "stub page"


def test_review_decisions_are_recorded_outside_the_store(
    env: Env, clean_env: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean_env.setenv("KG_LIVE", "1")
    mid = ScriptedSeat(lambda c, w: ("supported", 0.5))
    p = ScriptedProposer({"pages/normal.md": [CAL], "pages/injected.md": [GRADER]})
    assert cli.main(argv(env, "build", "pages"), proposer=p, seat=mid) in (0, cli.EXIT_HALTED)
    (rid,) = [x.name.removesuffix(".report.json") for x in env.records.glob("*.report.json")]
    capsys.readouterr()
    assert cli.main(argv(env, "review", rid)) == 0
    assert "score" in capsys.readouterr().out
    key = ["ece", "measures", "calibration", "pages/normal.md"]
    f = tmp_path / "dec.jsonl"
    f.write_text(json.dumps({"key": key, "decision": "accept"}) + "\n", encoding="utf-8")
    assert cli.main([*argv(env, "review", rid), "--decisions", str(f)]) == 0
    (row,) = [e for e in kb.read_decisions(env.decisions, rid) if e["kind"] == "review"]
    assert row["decision"] == "accept" and row["key"] == key
    env.store.db_path.unlink()
    assert kb.read_decisions(env.decisions, rid)  # survives


def test_profile_command_prints_the_census(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(argv(env, "profile", "pages")) == 0
    out = capsys.readouterr().out
    assert "3 pages" in out and "estimate" in out


def test_label_dry_run_passes_flags_through(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        cli.main(["label", "--dry-run", "--corpus-root", str(FIXTURES), "--domain", "pages"]) == 0
    )
    assert "kg.label" in capsys.readouterr().out
