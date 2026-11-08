"""Exports: JSONL (one stored triple per line, with evidence) and Obsidian markdown."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from kg.store.protocol import GraphStore, StoredTriple

_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]]+')


def export_jsonl(store: GraphStore, build_id: str, path: Path) -> int:
    rows = store.triples(build_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(row.model_dump_json() + "\n")
    return len(rows)


def read_jsonl(path: Path) -> list[StoredTriple]:
    return [
        StoredTriple.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _page_name(surface: str) -> str:
    return _UNSAFE.sub("-", surface).strip(" -") or "untitled"


def export_markdown(store: GraphStore, build_id: str, out_dir: Path) -> list[Path]:
    """One page per subject entity: `- relation [[Object]]`, the quote, and its source page."""
    by_subject: dict[str, list[StoredTriple]] = defaultdict(list)
    for row in store.triples(build_id):
        by_subject[row.triple.subject].append(row)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for subject in sorted(by_subject):
        rows = by_subject[subject]
        lines = [
            "---",
            f"type: {rows[0].triple.subject_type}",
            f"build_id: {build_id}",
            "---",
            "",
            f"# {subject}",
            "",
        ]
        for r in sorted(rows, key=lambda r: (r.triple.relation, r.triple.object)):
            t = r.triple
            lines.append(f"- {t.relation} [[{_page_name(t.object)}]] ({r.tier})")
            lines.append(f"  > {r.evidence.quote}")
            lines.append(f"  source: `{r.evidence.page_path}`")
        f = out_dir / f"{_page_name(subject)}.md"
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(f)
    return written
