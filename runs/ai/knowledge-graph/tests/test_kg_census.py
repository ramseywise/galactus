"""Census: counts, stable hash, empty-domain and over-ceiling refusals."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from kg.profile import (
    BuildRefused,
    Estimate,
    census,
    estimate_cost,
    iter_pages,
    refuse_if_empty,
    refuse_if_over,
)
from kg.profile.prices_table import PRICES, SOURCE_URL

FIXTURES = Path(__file__).parent / "fixtures"


def test_census_counts_fixture_pages() -> None:
    profile = census(FIXTURES, "pages")
    assert profile.page_count == 3
    assert profile.empty_count == 1
    assert profile.split_count == 0
    assert [p.path for p in profile.pages] == [
        "pages/empty.md",
        "pages/injected.md",
        "pages/normal.md",
    ]
    assert all(p.bytes > 0 for p in profile.pages)


def test_profile_hash_is_stable_across_runs() -> None:
    assert census(FIXTURES, "pages").profile_hash == census(FIXTURES, "pages").profile_hash


def test_profile_hash_changes_when_a_page_changes(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES / "pages", tmp_path / "pages")
    before = census(tmp_path, "pages").profile_hash
    (tmp_path / "pages" / "normal.md").write_text("# changed\n", encoding="utf-8")
    assert census(tmp_path, "pages").profile_hash != before


def test_census_skips_private_and_underscore_files(tmp_path: Path) -> None:
    d = tmp_path / "eval"
    (d / "private").mkdir(parents=True)
    (d / "page.md").write_text("# Page\n\nbody", encoding="utf-8")
    (d / "_index.md").write_text("# Index", encoding="utf-8")
    (d / "private" / "secret.md").write_text("# Secret", encoding="utf-8")
    assert [p.path for p in census(tmp_path, "eval").pages] == ["eval/page.md"]


def test_large_page_is_marked_split(tmp_path: Path) -> None:
    d = tmp_path / "eval"
    d.mkdir()
    (d / "big.md").write_text("word " * 5000, encoding="utf-8")  # ~25k chars ≈ 6250 tokens
    (page,) = census(tmp_path, "eval").pages
    assert page.split and page.calls == 2


def test_empty_domain_refused(tmp_path: Path) -> None:
    (tmp_path / "evl").mkdir()
    with pytest.raises(BuildRefused, match="no pages"):
        refuse_if_empty(census(tmp_path, "evl"))


def test_missing_domain_refused(tmp_path: Path) -> None:
    with pytest.raises(BuildRefused, match="'nope'"):
        refuse_if_empty(census(tmp_path, "nope"))


def test_estimate_states_its_assumptions() -> None:
    est = estimate_cost(census(FIXTURES, "pages"))
    assert est.usd > 0
    assert "survival rate 75%" in est.basis
    assert "claude-haiku-5-5" in est.basis and "claude-sonnet-5-5" in est.basis
    assert str(est).startswith("$")


def test_estimate_over_ceiling_refused_with_dollar_figure() -> None:
    est = Estimate(usd=12.34, basis="test basis")
    with pytest.raises(BuildRefused, match=r"\$12\.34 exceeds the build ceiling \$10\.00"):
        refuse_if_over(est, 10.0)
    refuse_if_over(est, 20.0)  # under the ceiling: no raise


def test_unpriced_model_refused_rather_than_free() -> None:
    with pytest.raises(BuildRefused, match="no price for model"):
        estimate_cost(census(FIXTURES, "pages"), PRICES, judge_model="mystery-model")


def test_price_table_names_its_source() -> None:
    assert SOURCE_URL.startswith("https://")


def test_iter_pages_yields_normalised_bodies() -> None:
    pages = {p.path: p.body for p in iter_pages(FIXTURES, "pages")}
    assert pages["pages/empty.md"] == ""
    assert "Frontmatter says" not in pages["pages/normal.md"]


def test_real_eval_corpus_has_80_pages() -> None:
    root = os.environ.get("KG_CORPUS_ROOT")
    if not root:
        pytest.skip("KG_CORPUS_ROOT is not set; real-corpus census not run")
    profile = census(Path(root).expanduser(), "eval")
    assert profile.page_count == 80
    est = estimate_cost(profile)
    print(f"eval/: {profile.page_count} pages, {profile.est_tokens} est tokens, estimate {est}")
