"""Step 2 — provenance capture degrades to a recorded reason instead of
raising, both outside a git repository and for an absent scoring-relevant
package."""

from __future__ import annotations

import subprocess
from pathlib import Path

from experiments.provenance import SCORING_RELEVANT, capture_code_state
from experiments.record import NotApplicable


def test_git_sha_matches_rev_parse_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "a.txt").write_text("hello")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    expected_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    state = capture_code_state(repo)
    assert state.git_sha == expected_sha
    assert state.dirty is False


def test_dirty_true_when_status_porcelain_nonempty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "a.txt").write_text("hello")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    # Uncommitted change after the commit -> status --porcelain is non-empty.
    (repo / "a.txt").write_text("changed")

    state = capture_code_state(repo)
    assert state.dirty is True


def test_outside_git_repo_returns_not_applicable_instead_of_raising(tmp_path: Path) -> None:
    non_repo = tmp_path / "not_a_repo"
    non_repo.mkdir()

    state = capture_code_state(non_repo)
    assert isinstance(state.git_sha, NotApplicable)
    assert state.git_sha.reason


def test_versions_contains_installed_scoring_relevant_names() -> None:
    state = capture_code_state(Path.cwd())
    # numpy and pandas are always installed in the rendered test environment
    # (pandas ships whenever include_ml is true, which the render matrix used
    # by make test_render always sets).
    assert "numpy" in state.versions
    assert "python" in state.versions
    for name in state.versions:
        assert name in SCORING_RELEVANT


def test_versions_omits_absent_packages_rather_than_nulling() -> None:
    state = capture_code_state(Path.cwd())
    # A package that is not installed must be absent from the dict entirely,
    # never present with a None/null value.
    assert "definitely-not-a-real-package-xyz" not in state.versions
    for value in state.versions.values():
        assert value is not None
