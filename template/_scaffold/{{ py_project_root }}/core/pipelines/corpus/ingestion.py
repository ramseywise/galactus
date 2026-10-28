from __future__ import annotations

import re
from pathlib import Path

from core.pipelines.corpus.models import Article

_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def load_raw_articles(corpus_dir: Path) -> list[Article]:
    """Load every ``*.md`` file in ``corpus_dir``.

    Each file is expected to start with a single ``# Title`` heading; everything
    after it is treated as body text. The filename stem becomes the article id.
    """
    articles: list[Article] = []
    for path in sorted(corpus_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = _TITLE_RE.search(raw)
        title = match.group(1).strip() if match else path.stem
        body = raw[match.end() :].strip() if match else raw.strip()
        articles.append(
            Article(
                id=path.stem,
                title=title,
                text=body,
                source_path=str(path),
            )
        )
    return articles
