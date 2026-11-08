"""Librarian baseline arm: a subprocess in Librarian's own venv, never an import.

`run_baseline` shells out to `uv run --project $LIBRARIAN_ROOT python -I <probe>`. A missing
root, a missing `uv`, a non-zero exit or unparseable output raises `BaselineError` naming
the cause, so an unavailable baseline refuses rather than reading as "no results".
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg.config import Settings

PROBE = Path(__file__).with_name("_librarian_probe.py")
TIMEOUT_S = 180

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class BaselineError(RuntimeError):
    """The Librarian baseline could not run; the CLI maps this to a refusal (exit 2)."""


@dataclass(frozen=True)
class Row:
    path: str
    title: str
    tags: str
    summary: str
    content: str
    backlinks: str
    score: float


@dataclass(frozen=True)
class BaselineResult:
    rows: tuple[Row, ...]
    degraded: tuple[str, ...]
    retrieval_ms: float
    """In-process retrieval time reported by the probe; excludes `uv run` startup."""


Baseline = Callable[[str, int], BaselineResult]
"""`(query, limit) -> BaselineResult`. Injected so tests and entity-only asks skip Librarian."""


def build_command(
    root: Path, query: str, limit: int, *, expand: bool, domain: str = ""
) -> list[str]:
    cmd = ["uv", "run", "--project", str(root), "python", "-I", str(PROBE),
           "--query", query, "--limit", str(limit)]  # fmt: skip
    if domain:
        cmd += ["--domain", domain]
    if expand:
        cmd.append("--expand")
    return cmd


def run_baseline(
    query: str,
    limit: int,
    *,
    settings: Settings,
    expand: bool = True,
    domain: str = "",
    runner: Runner = subprocess.run,
) -> BaselineResult:
    root = settings.librarian_root
    if not root.is_dir():
        raise BaselineError(f"LIBRARIAN_ROOT does not exist: {root}; the baseline is unavailable")
    cmd = build_command(root, query, limit, expand=expand, domain=domain)
    try:
        proc = runner(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BaselineError(f"Librarian probe could not run ({exc}); root {root}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise BaselineError(
            f"Librarian probe exited {proc.returncode} (root {root}): {' | '.join(tail)}"
        )
    return parse_probe_output(proc.stdout)


def parse_probe_output(stdout: str) -> BaselineResult:
    try:
        data: dict[str, Any] = json.loads(stdout)
        rows = tuple(
            Row(*(str(v) if i < 6 else float(v) for i, v in enumerate(r))) for r in data["rows"]
        )
        return BaselineResult(
            rows=rows, degraded=tuple(data["degraded"]), retrieval_ms=float(data["retrieval_ms"])
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise BaselineError(f"Librarian probe output was not valid: {exc}") from exc


def make_baseline(
    settings: Settings, *, expand: bool = True, runner: Runner = subprocess.run
) -> Baseline:
    def baseline(query: str, limit: int) -> BaselineResult:
        return run_baseline(query, limit, settings=settings, expand=expand, runner=runner)

    return baseline
