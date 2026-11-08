"""`evals/run.py --retrieval` and the two carried fixes (neo4j refusal, jev client seam).

`evals/` would resolve to marketing-comms' package, so run.py is loaded by path."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

RUN = Path(__file__).resolve().parent.parent
SCRIPT = RUN / "evals" / "run.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("kg_eval_run", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kg_eval_run"] = mod
    spec.loader.exec_module(mod)
    return mod


ev = _load()


def cli(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "VIRTUAL_ENV")}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env={**base, **env}, cwd=Path("/"), timeout=120,
        check=False,
    )  # fmt: skip


def write_questions(path: Path, n_hand: int, n_weak: int = 6) -> Path:
    rows = [
        {"id": f"w{i}", "source": "weak", "question": f"weak {i}?", "expected": [f"eval/p{i}.md", "eval/q.md"]}
        for i in range(n_weak)
    ] + [
        {"id": f"h{i}", "source": "hand", "question": f"hand {i}?", "expected": [f"eval/h{i}.md"]}
        for i in range(n_hand)
    ]  # fmt: skip
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


# -- pure figures ----------------------------------------------------------------------


def test_recall_counts_expected_in_first_five_distinct_paths() -> None:
    q = ev.Question("1", "weak", "q", ("eval/a.md", "eval/b.md"))
    dup = ["x/1.md", "x/1.md", "x/2.md", "wiki/eval/a.md", "x/3.md", "x/4.md", "eval/b.md"]
    # distinct top 5 = 1, 2, a, 3, 4: b is sixth distinct, so only a counts
    assert ev.recall_at_k(q, dup) == 0.5


def test_p95_nearest_rank_and_empty_is_not_applicable() -> None:
    assert ev.p95(list(range(1, 101))) == 95
    assert isinstance(ev.p95([]), ev.NotApplicable)


def test_bootstrap_is_seeded_and_needs_two_pairs() -> None:
    d = [0.0, 0.5, 0.25, 0.0, 1.0]
    assert ev.bootstrap_ci(d) == ev.bootstrap_ci(d)
    assert isinstance(ev.bootstrap_ci([0.1]), ev.NotApplicable)


def _hand(diff: float, lo: float | None = None, hi: float | None = None) -> dict:
    cmp = {"status": "measured", "diff": diff}
    if lo is not None:
        cmp.update(lo=lo, hi=hi)
    return {"n": 20, "arms": {ev.VERDICT_ARM: {"vs_reference": cmp}}}


def test_verdict_bar_and_straddle_note() -> None:
    assert ev.verdict(_hand(0.12, 0.11, 0.2))["verdict"] == "gain"
    assert "note" not in ev.verdict(_hand(0.12, 0.11, 0.2))
    below = ev.verdict(_hand(0.04, -0.05, 0.12))
    assert below["verdict"] == "no gain recorded" and "straddles" in below["note"]
    assert ev.verdict({"n": 0, "arms": {}})["verdict"] == "cannot be read yet"


# -- dry-run report --------------------------------------------------------------------


def test_dry_run_with_no_hand_rows_prints_not_applicable_and_unreadable_verdict(
    tmp_path: Path,
) -> None:
    q = write_questions(tmp_path / "q.jsonl", n_hand=0)
    proc = cli("--retrieval", "--dry-run", "--questions", str(q))
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "== hand" in out and "n=0" in out and "NotApplicable" in out
    assert "goal-1 verdict: cannot be read yet" in out
    for token in ("baseline_off", "graph_neo4j", "entry-miss", "grounding", "p95", "Recall parity"):
        assert token in out
    assert "librarian_index_id" in out and "graph_profile_hash" in out


def test_dry_run_with_hand_rows_reads_a_verdict_with_interval(tmp_path: Path) -> None:
    q = write_questions(tmp_path / "q.jsonl", n_hand=30)
    proc = cli("--retrieval", "--dry-run", "--json", "--questions", str(q))
    assert proc.returncode == 0, proc.stderr
    rep = json.loads(proc.stdout)
    assert rep["sets"]["hand"]["n"] == 30 and rep["sets"]["weak"]["n"] == 6
    cmp = rep["sets"]["hand"]["arms"]["graph_sqlite"]["vs_reference"]
    assert {"diff", "lo", "hi"} <= cmp.keys()
    assert rep["verdict"]["verdict"] in ("gain", "no gain recorded")
    assert rep["sets"]["hand"]["arms"]["baseline_on"]["vs_reference"]["status"] == "n/a"
    assert rep["sets"]["hand"]["arms"]["baseline_off"]["entry_miss"]["status"] == "n/a"


def test_dry_run_is_deterministic(tmp_path: Path) -> None:
    q = write_questions(tmp_path / "q.jsonl", n_hand=5)
    a = cli("--retrieval", "--dry-run", "--questions", str(q)).stdout
    assert a == cli("--retrieval", "--dry-run", "--questions", str(q)).stdout


def test_shipped_questions_file_parses_and_has_weak_rows() -> None:
    qs = ev.load_questions(ev.QUESTIONS_PATH)
    assert sum(q.source == "weak" for q in qs) >= 30


def test_bad_question_rows_refuse(tmp_path: Path) -> None:
    f = tmp_path / "q.jsonl"
    f.write_text(json.dumps({"id": "a", "source": "guess", "question": "q", "expected": ["x"]}))
    proc = cli("--retrieval", "--dry-run", "--questions", str(f))
    assert proc.returncode != 0 and "refused" in proc.stderr


# -- live-mode refusals ----------------------------------------------------------------


def test_missing_librarian_refuses_instead_of_skipping_an_arm(tmp_path: Path) -> None:
    proc = cli("--retrieval", LIBRARIAN_ROOT=str(tmp_path / "nope"))
    assert proc.returncode != 0 and "Librarian" in proc.stderr and "refused" in proc.stderr


def test_unavailable_neo4j_refuses_the_whole_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kg.store import SqliteStore

    db = tmp_path / "g.sqlite"
    SqliteStore(db)
    monkeypatch.setattr(ev, "make_baseline", lambda s, expand=True: lambda q, k: None)
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with pytest.raises(SystemExit) as exc:
        ev.main(["--retrieval", "--db", str(db)])
    assert "graph_neo4j" in str(exc.value) and "NEO4J_URI" in str(exc.value)


# -- carried fixes ---------------------------------------------------------------------


def test_store_neo4j_without_uri_refuses_naming_it() -> None:
    proc = cli("--dry-run", "--store", "neo4j")
    assert proc.returncode != 0 and "NEO4J_URI" in proc.stderr


def test_dry_run_jev_completes_with_a_fake_key_and_mock_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={"probability": 0.9})

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert ev.main(["--dry-run", "--judge", "jev", "--repeats", "1"], jev_client=client) == 0
    assert calls and "jev" in capsys.readouterr().out
