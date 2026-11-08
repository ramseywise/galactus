"""Turn a wiki page into the body the proposer reads and the verbatim gate checks.

Everything the proposer quotes must be findable in this body, and nothing outside it may
pass the verbatim gate: frontmatter and wikilink targets are metadata, not prose, so a
quote lifted from them must fail (spec F8). The rules, in order:

1. Strip the YAML frontmatter block at the top of the page.
2. Strip HTML comments (`<!-- auto-linked -->` markers Librarian leaves behind).
3. Drop the ` — <type>` suffix after a typed link, for Librarian's canonical link types
   only; prose such as `[[X]] — a pattern that...` keeps its dash.
4. Reduce `[[Target|Display]]` to `Display` and `[[Target]]` / `[[Target#Heading]]` to
   `Target`.
5. NFC-normalise.
6. Collapse every whitespace run inside a paragraph to one space and keep paragraph breaks
   as one blank line. Pages are hard-wrapped, so a sentence quoted across a wrap must
   still match.

`NORMALISATION_RULE_HASH` is the sha256 of this file, so any edit to the rules changes
every profile hash computed under them.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

# Copied from librarian/src/librarian/wiki/common.py (CANONICAL_LINK_TYPES), not imported:
# galactus never imports Librarian.
CANONICAL_LINK_TYPES = (
    "extends",
    "prerequisite-for",
    "alternative-to",
    "instance-of",
    "contradicts",
    "supersedes",
    "related",
)

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TYPED_SUFFIX = re.compile(
    r"(\[\[[^\]]+\]\])[ \t]*—[ \t]*(?:" + "|".join(CANONICAL_LINK_TYPES) + r")(?![\w-])"
)
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
_WHITESPACE = re.compile(r"\s+")

NORMALISATION_RULE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _link_text(m: re.Match[str]) -> str:
    target, display = m.group(1), m.group(2)
    if display is not None:
        return display.strip()
    return target.split("#", 1)[0].strip()


def normalise(raw: str) -> str:
    text = raw.replace("\r\n", "\n")
    text = _FRONTMATTER.sub("", text, count=1)
    text = _HTML_COMMENT.sub("", text)
    text = _TYPED_SUFFIX.sub(r"\1", text)
    text = _WIKILINK.sub(_link_text, text)
    text = unicodedata.normalize("NFC", text)
    paragraphs = (_WHITESPACE.sub(" ", p).strip() for p in _PARAGRAPH_BREAK.split(text))
    return "\n\n".join(p for p in paragraphs if p)


def norm_surface(surface: str) -> str:
    """Comparison form of an entity surface: NFC, casefolded, whitespace collapsed."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", surface).casefold()).strip()
