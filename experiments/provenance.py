"""Provenance capture — which code produced this run.

`capture_code_state()` is the only entry point. It never raises on a missing
git repo or a missing package: both are recordable absences (see
`record.CodeState`), not failures that should abort a run whose numbers are
otherwise fine. A run outside version control is still worth recording — it
just is not code-identified the way a committed run is.
"""

from __future__ import annotations

import subprocess
from importlib import metadata
from pathlib import Path

from experiments.record import CodeState, NotApplicable

SCORING_RELEVANT: tuple[str, ...] = (
    "python",
    "numpy",
    "pandas",
    "scikit-learn",
    "lightgbm",
    "xgboost",
)
"""The libraries whose version can change the numbers a run produces.

Deliberately not a full dependency freeze — that is noisy and most of it
(a logging library, a CLI parser) has no bearing on a metric. Deliberately
not a lockfile hash either — `template/_scaffold/` ships `pyproject.toml`
with no `uv.lock`, so there is no lockfile to hash for a freshly scaffolded
project. This is the fixed, small tuple of distributions that actually
compute the numbers.
"""


def _package_version(name: str) -> str | None:
    """Resolved version of an installed distribution, or `None` if absent."""
    if name == "python":
        import sys

        return ".".join(str(part) for part in sys.version_info[:3])
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _capture_versions() -> dict[str, str]:
    """Every installed name in `SCORING_RELEVANT`, versions resolved.

    Absent packages are omitted, never recorded as null — a null version
    reads as "installed but the lookup failed", which is a different claim
    than "not installed".
    """
    versions: dict[str, str] = {}
    for name in SCORING_RELEVANT:
        version = _package_version(name)
        if version is not None:
            versions[name] = version
    return versions


def _run_git(args: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def capture_code_state(repo: Path | None = None) -> CodeState:
    """Git SHA + dirty flag + versions of the libraries that produce numbers.

    Dirty is recorded rather than rejected: the honest record of an
    uncommitted run is 'this SHA plus changes', not a refusal to record.
    Outside a git repository (or when git is unavailable), `git_sha` is a
    `NotApplicable` carrying the reason — the run is still recorded, just
    not code-identified.
    """
    repo = repo if repo is not None else Path.cwd()
    versions = _capture_versions()

    try:
        sha_result = _run_git(["rev-parse", "HEAD"], repo)
    except FileNotFoundError:
        return CodeState(
            git_sha=NotApplicable("git executable not found on PATH"),
            dirty=False,
            versions=versions,
        )

    if sha_result.returncode != 0:
        return CodeState(
            git_sha=NotApplicable(
                f"not inside a git repository at {repo} "
                f"({sha_result.stderr.strip() or 'git rev-parse failed'})"
            ),
            dirty=False,
            versions=versions,
        )

    sha = sha_result.stdout.strip()
    status_result = _run_git(["status", "--porcelain"], repo)
    dirty = bool(status_result.stdout.strip())

    return CodeState(git_sha=sha, dirty=dirty, versions=versions)
