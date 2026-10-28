from __future__ import annotations

import hashlib
from pathlib import Path

from core.pipelines.corpus.models import Article

_MIN_LENGTH = 20


def _content_hash(article: Article) -> str:
    return hashlib.sha256(article.text.encode("utf-8")).hexdigest()


def clean_and_dedupe(articles: list[Article]) -> list[Article]:
    """Strip whitespace, drop too-short articles, and drop exact-content duplicates."""
    seen: set[str] = set()
    cleaned: list[Article] = []
    for article in articles:
        text = " ".join(article.text.split())
        if len(text) < _MIN_LENGTH:
            continue
        normalized = article.model_copy(update={"text": text})
        digest = _content_hash(normalized)
        if digest in seen:
            continue
        seen.add(digest)
        cleaned.append(normalized)
    return cleaned


def write_jsonl(articles: list[Article], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
