"""Hybrid `ask` and the Librarian baseline adapter (subprocess faked; one live probe test)."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from kg_store_helpers import promoted, put

from kg import cli
from kg.config import DEFAULT_LIBRARIAN_ROOT, Settings
from kg.retrieve import (
    BaselineError,
    BaselineResult,
    Row,
    ask,
    effective_k,
    run_baseline,
)
from kg.retrieve.librarian_baseline import PROBE, build_command
from kg.store import SqliteStore

PAGE = "eval/p.md"
QUOTE = "Alpha beats Beta on recall."
BODY = f"{QUOTE} Extra sentence here.\n\nGamma follows Beta in the chain."


def settings_for(root: Path, **kw: object) -> Settings:
    base = Settings(
        anthropic_api_key=None,
        openrouter_api_key=None,
        neo4j_uri=None,
        corpus_root=root,
        librarian_root=root / "no-librarian",
    )
    return replace(base, **kw)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    (tmp_path / "corpus" / "eval").mkdir(parents=True)
    (tmp_path / "corpus" / PAGE).write_text(BODY, encoding="utf-8")
    return tmp_path / "corpus"


@pytest.fixture
def store(tmp_path: Path, corpus: Path) -> SqliteStore:
    s = SqliteStore(tmp_path / "kg.db", corpus_root=corpus)
    promoted(s, "b1")
    put(s, "b1", "Alpha", "beats", "Beta", page=PAGE, quote=QUOTE)
    put(s, "b1", "Beta", "precedes", "Gamma", page=PAGE, quote="Gamma follows Beta")
    put(s, "b1", "Alpha", "mentions", "Delta", page=PAGE, tier="review",
        quote="Delta is only a maybe.")  # fmt: skip
    put(
        s,
        "b1",
        "Lonely",
        "touches",
        "Ghost",
        page=PAGE,
        tier="review",
        quote="Lonely touches Ghost.",
    )
    return s


def fake_baseline(rows: list[Row], degraded: tuple[str, ...] = ()):
    calls: list[tuple[str, int]] = []

    def baseline(q: str, limit: int) -> BaselineResult:
        calls.append((q, limit))
        return BaselineResult(tuple(rows), degraded, 1.5)

    baseline.calls = calls  # type: ignore[attr-defined]
    return baseline


def row(title: str, summary: str = "") -> Row:
    return Row("eval/x.md", title, "", summary, "", "", 1.0)


# -- ask ------------------------------------------------------------------------------------


def test_default_never_returns_review_tier(store: SqliteStore, corpus: Path) -> None:
    r = ask(store, settings=settings_for(corpus), entities={"Alpha"}, k=2)
    assert r.status == "ok"
    assert r.passages and all(p.tier == "accept" for p in r.passages)


def test_include_review_widens(store: SqliteStore, corpus: Path) -> None:
    r = ask(store, settings=settings_for(corpus), entities={"Alpha"}, include_review=True)
    assert "review" in {p.tier for p in r.passages}


def test_unknown_entity_is_entry_miss_not_empty_ok(store: SqliteStore, corpus: Path) -> None:
    r = ask(store, settings=settings_for(corpus), entities={"Nonesuch"})
    assert r.status == "entry_miss" and r.passages == ()


def test_known_entity_without_served_relations_is_no_hops(store: SqliteStore, corpus: Path) -> None:
    r = ask(store, settings=settings_for(corpus), entities={"Lonely"})
    assert r.status == "no_hops" and r.entities == ("lonely",)
    r2 = ask(store, settings=settings_for(corpus), entities={"Lonely"}, include_review=True)
    assert r2.status == "ok"


def test_hop_depth_never_exceeds_max_hops(store: SqliteStore, corpus: Path) -> None:
    s1 = settings_for(corpus, max_hops=1)
    assert effective_k(s1, 5) == 1 and effective_k(settings_for(corpus), 5) == 2
    r = ask(store, settings=s1, entities={"Alpha"}, k=5)
    assert r.passages and max(p.hop for p in r.passages) <= 1
    deep = ask(store, settings=settings_for(corpus), entities={"Alpha"}, k=9)
    assert max(p.hop for p in deep.passages) <= 2


def test_quote_edited_out_after_build_is_stale(store: SqliteStore, corpus: Path) -> None:
    before = ask(store, settings=settings_for(corpus), entities={"Alpha"})
    assert {p.freshness for p in before.passages} == {"fresh"}
    (corpus / PAGE).write_text("Alpha now loses to Beta.\n\nGamma follows Beta in the chain.")
    after = ask(store, settings=settings_for(corpus), entities={"Alpha"})
    fresh = {p.triple.object: p.freshness for p in after.passages}
    assert fresh["Beta"] == "stale"


def test_degraded_is_never_dropped(store: SqliteStore, corpus: Path) -> None:
    b = fake_baseline([row("Alpha")], degraded=("no_fts",))
    r = ask(store, settings=settings_for(corpus), query="alpha?", baseline=b)
    assert r.status == "degraded" and r.degraded == ("no_fts",)
    assert r.graph_status == "ok" and r.passages


def test_query_path_matches_entities_from_entry_rows(store: SqliteStore, corpus: Path) -> None:
    b = fake_baseline([row("Notes on Alpha", "Alpha and Beta compared")])  # type: ignore[arg-type]
    r = ask(store, settings=settings_for(corpus), query="who wins", baseline=b, limit=3)
    assert b.calls == [("who wins", 3)]  # type: ignore[attr-defined]
    assert r.status == "ok" and {"alpha", "beta"} <= set(r.entities)
    miss = ask(
        store, settings=settings_for(corpus), query="x", baseline=fake_baseline([row("Zzz")])
    )
    assert miss.status == "entry_miss"


def test_query_without_baseline_is_a_usage_error(store: SqliteStore, corpus: Path) -> None:
    with pytest.raises(ValueError, match="baseline"):
        ask(store, settings=settings_for(corpus), query="q")


# -- baseline adapter -----------------------------------------------------------------------


def completed(code: int, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, out, err)


def test_missing_root_refuses_naming_it(tmp_path: Path) -> None:
    s = settings_for(tmp_path, librarian_root=tmp_path / "gone")
    with pytest.raises(BaselineError, match="gone"):
        run_baseline("q", 5, settings=s, runner=lambda *a, **k: pytest.fail("must not run"))


def test_nonzero_exit_refuses_by_name(tmp_path: Path) -> None:
    s = settings_for(tmp_path, librarian_root=tmp_path)
    with pytest.raises(BaselineError, match="exited 3"):
        run_baseline("q", 5, settings=s, runner=lambda *a, **k: completed(3, err="boom"))


def test_bad_output_refuses(tmp_path: Path) -> None:
    s = settings_for(tmp_path, librarian_root=tmp_path)
    with pytest.raises(BaselineError, match="not valid"):
        run_baseline("q", 5, settings=s, runner=lambda *a, **k: completed(0, "nope"))


def test_run_baseline_parses_and_builds_command(tmp_path: Path) -> None:
    s = settings_for(tmp_path, librarian_root=tmp_path)
    seen: list[list[str]] = []
    payload = {
        "rows": [["eval/a.md", "A", "t", "s", "c", "b", 0.5]],
        "degraded": ["no_fts"],
        "retrieval_ms": 12.0,
    }

    def runner(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return completed(0, json.dumps(payload))

    r = run_baseline("q", 5, settings=s, runner=runner)
    assert r.rows[0].path == "eval/a.md" and r.degraded == ("no_fts",) and r.retrieval_ms == 12.0
    assert seen[0][:5] == ["uv", "run", "--project", str(tmp_path), "python"]
    assert "-I" in seen[0] and str(PROBE) in seen[0] and "--expand" in seen[0]
    assert "--expand" not in build_command(tmp_path, "q", 1, expand=False)


def test_kg_package_does_not_import_librarian() -> None:
    import ast

    src = Path(cli.__file__).parent
    for f in src.rglob("*.py"):
        if f.name == "_librarian_probe.py":
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not any(n.split(".")[0] == "librarian" for n in names), f


# -- CLI ------------------------------------------------------------------------------------


def cli_argv(tmp_path: Path, corpus: Path, *a: str) -> list[str]:
    return ["ask", *a, "--corpus-root", str(corpus), "--db", str(tmp_path / "kg.db")]


def test_cli_ask_statuses(
    tmp_path: Path, corpus: Path, store: SqliteStore, clean_env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    assert cli.main(cli_argv(tmp_path, corpus, "Alpha")) == 0
    out = capsys.readouterr().out
    assert "status: ok" in out and "[accept" in out and "[review" not in out
    assert cli.main(cli_argv(tmp_path, corpus, "Alpha", "--include-review")) == 0
    assert "[review" in capsys.readouterr().out
    assert cli.main(cli_argv(tmp_path, corpus, "Nobody")) == 0
    assert "status: entry_miss" in capsys.readouterr().out


def test_cli_ask_on_empty_store(
    tmp_path: Path, corpus: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(cli_argv(tmp_path, corpus, "SomeEntity")) == 0
    assert "status: entry_miss" in capsys.readouterr().out


def test_cli_via_librarian_refuses_when_root_missing(
    tmp_path: Path, corpus: Path, clean_env: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    clean_env.setenv("LIBRARIAN_ROOT", str(tmp_path / "gone"))
    assert cli.main(cli_argv(tmp_path, corpus, "q", "--via-librarian")) == cli.EXIT_REFUSED
    assert "gone" in capsys.readouterr().err


# -- live probe -----------------------------------------------------------------------------


def _live_root() -> Path | None:
    import os

    root = Path(os.environ.get("LIBRARIAN_ROOT") or DEFAULT_LIBRARIAN_ROOT).expanduser()
    return root if root.is_dir() and shutil.which("uv") else None


@pytest.mark.skipif(_live_root() is None, reason="LIBRARIAN_ROOT / uv not available")
def test_live_probe_returns_rows(tmp_path: Path) -> None:
    root = _live_root()
    assert root is not None
    s = settings_for(tmp_path, librarian_root=root)
    r = run_baseline("retrieval evaluation", 3, settings=s)
    assert r.retrieval_ms >= 0
    assert isinstance(r.degraded, tuple)
    assert all(isinstance(x, Row) for x in r.rows)
