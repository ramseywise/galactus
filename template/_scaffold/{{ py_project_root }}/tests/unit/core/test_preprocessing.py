from __future__ import annotations

import json
from pathlib import Path

from core.pipelines.corpus.models import Article
from core.pipelines.corpus.preprocessing import clean_and_dedupe, write_jsonl


def _article(**overrides: object) -> Article:
    defaults: dict[str, object] = {
        "id": "sample",
        "title": "Sample Title",
        "text": "This is a perfectly normal article body with plenty of content.",
        "category": "general",
        "source_path": "sample.md",
    }
    defaults.update(overrides)
    return Article(**defaults)  # type: ignore[arg-type]


def test_clean_and_dedupe_drops_too_short_article() -> None:
    too_short = _article(id="short", text="too short")
    normal = _article(id="normal")

    result = clean_and_dedupe([too_short, normal])

    ids = {article.id for article in result}
    assert "short" not in ids
    assert "normal" in ids


def test_clean_and_dedupe_drops_exact_duplicate_content() -> None:
    original = _article(id="first", text="Duplicate content that is definitely long enough.")
    duplicate = _article(id="second", text="Duplicate content that is definitely long enough.")

    result = clean_and_dedupe([original, duplicate])

    assert len(result) == 1
    assert result[0].id == "first"


def test_clean_and_dedupe_collapses_whitespace() -> None:
    messy = _article(id="messy", text="Lots   of\n\nextra   whitespace   in this body of text.")

    result = clean_and_dedupe([messy])

    assert len(result) == 1
    assert "  " not in result[0].text
    assert "\n" not in result[0].text


def test_clean_and_dedupe_keeps_distinct_articles() -> None:
    first = _article(id="first", text="First unique article with sufficiently long text.")
    second = _article(id="second", text="Second unique article with different long text.")

    result = clean_and_dedupe([first, second])

    assert {article.id for article in result} == {"first", "second"}


def test_write_jsonl_round_trips(tmp_path: Path) -> None:
    articles = [
        _article(id="one", title="One", text="First article body long enough to survive."),
        _article(id="two", title="Two", text="Second article body long enough to survive."),
    ]
    out_path = tmp_path / "nested" / "articles.jsonl"

    write_jsonl(articles, out_path)

    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(articles)

    loaded = [json.loads(line) for line in lines]
    assert [row["id"] for row in loaded] == ["one", "two"]
    assert loaded[0]["title"] == "One"
    assert loaded[1]["text"] == "Second article body long enough to survive."
