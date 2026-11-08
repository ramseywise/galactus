"""Weak gold for the retrieval eval, read from Librarian's typed wikilinks.

A line like `- [[Golden Set Mechanics]] — extends (why)` on page P says the author linked P to
that page. The question stem comes from P's title and the expected pages are P's resolved
link targets. These rows are weak on purpose: the same typed edges feed Librarian's
expansion, so a baseline with expansion on is partly graded against its own input. They are
scored apart from the hand-written set and never carry the goal-1 verdict (fog FA-009).

Row: `{id, source: "weak", question, expected: [page paths], from_page}`; paths are relative to
the corpus root. A link whose target matches no title or file stem is dropped and counted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

DOMAIN = "eval"
RELATIONS = ("related", "extends", "prerequisite-for", "instance-of", "alternative-to")
_LINK = re.compile(
    r"^\s*[-*]\s+\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]\s*—\s*(" + "|".join(RELATIONS) + r")\b",
    re.MULTILINE,
)
_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_SKIP_DIRS = frozenset({"private"})
MIN_EXPECTED = 1


@dataclass(frozen=True)
class WeakGoldResult:
    rows: list[dict[str, object]]
    links_seen: int
    links_unresolved: int


def _title(text: str, stem: str) -> str:
    head = text.split("\n---", 1)[0] if text.startswith("---") else ""
    m = _TITLE.search(head)
    if m:
        return m.group(1).strip().strip("\"'")
    m = _H1.search(text)
    return m.group(1).strip() if m else stem


def _files(corpus_root: Path) -> Iterator[Path]:
    for f in sorted(corpus_root.rglob("*.md")):
        rel = f.relative_to(corpus_root)
        if rel.parts[0] in _SKIP_DIRS or f.name.startswith("_"):
            continue
        yield f


def _key(s: str) -> str:
    return " ".join(s.casefold().split())


def title_index(corpus_root: Path) -> dict[str, str]:
    """casefolded title (and file stem) -> corpus-relative path, across every domain."""
    out: dict[str, str] = {}
    for f in _files(corpus_root):
        rel = f.relative_to(corpus_root).as_posix()
        text = f.read_text(encoding="utf-8")
        out.setdefault(_key(_title(text, f.stem)), rel)
        out.setdefault(_key(f.stem), rel)
    return out


def weak_gold(corpus_root: Path, domain: str = DOMAIN) -> WeakGoldResult:
    index = title_index(corpus_root)
    rows: list[dict[str, object]] = []
    seen = unresolved = 0
    for f in _files(corpus_root):
        rel = f.relative_to(corpus_root).as_posix()
        if not rel.startswith(f"{domain}/"):
            continue
        text = f.read_text(encoding="utf-8")
        expected: list[str] = []
        for target, _rel in _LINK.findall(text):
            seen += 1
            path = index.get(_key(target))
            if path is None:
                unresolved += 1
            elif path != rel and path not in expected:
                expected.append(path)
        if len(expected) < MIN_EXPECTED:
            continue
        title = _title(text, f.stem)
        rows.append(
            {
                "id": hashlib.sha256(f"weak|{rel}".encode()).hexdigest()[:16],
                "source": "weak",
                "question": f"What does {title} connect to?",
                "expected": expected,
                "from_page": rel,
            }
        )
    return WeakGoldResult(rows, seen, unresolved)


def write_rows(rows: list[dict[str, object]], out: Path) -> None:
    """Rewrite the weak rows of `out`; hand-written rows already in it are kept untouched."""
    keep: list[str] = []
    if out.is_file():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("source") != "weak":
                keep.append(line)
    body = keep + [json.dumps(r, ensure_ascii=False) for r in rows]
    out.write_text("\n".join(body) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    from kg.config import Settings

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--corpus-root", type=Path, default=None)
    args = ap.parse_args(argv)
    root = args.corpus_root or Settings.load().require_corpus_root()
    res = weak_gold(root)
    print(
        f"{len(res.rows)} weak rows; {res.links_seen} typed links, "
        f"{res.links_unresolved} unresolved (dropped)"
    )
    if args.out:
        write_rows(res.rows, args.out)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
