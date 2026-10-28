from __future__ import annotations

from pathlib import Path

from core.pipelines.corpus.ingestion import load_raw_articles

EXPECTED_ARTICLE_COUNT = 6
# pytest runs from the project root (see pythonpath = [..., "."] in pyproject.toml),
# so this mirrors how `make corpus-ingest` locates the corpus in a real project.
CORPUS_DIR = Path("data/raw_corpus")


def test_load_raw_articles_finds_all_corpus_files() -> None:
    articles = load_raw_articles(CORPUS_DIR)
    assert len(articles) == EXPECTED_ARTICLE_COUNT

    ids = {article.id for article in articles}
    assert ids == {
        "descaling",
        "cleaning",
        "troubleshooting",
        "warranty",
        "brewing_guide",
        "water_filter",
    }


def test_load_raw_articles_extracts_title_and_id() -> None:
    articles = load_raw_articles(CORPUS_DIR)
    descaling = next(article for article in articles if article.id == "descaling")

    assert descaling.title == "How do I descale the machine?"
    assert descaling.source_path.endswith("descaling.md")
    assert descaling.category == "general"


def test_load_raw_articles_body_excludes_title_line() -> None:
    articles = load_raw_articles(CORPUS_DIR)
    descaling = next(article for article in articles if article.id == "descaling")

    assert "# How do I descale the machine?" not in descaling.text
    assert "Descale every 2-3 months" in descaling.text


def test_load_raw_articles_body_is_nonempty_for_every_article() -> None:
    articles = load_raw_articles(CORPUS_DIR)
    for article in articles:
        assert article.text.strip() != ""
