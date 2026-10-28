"""PII redaction for interaction records — a pluggable pipeline step.

Applied before grading (and before any text reaches an LLM judge).
pipelines/grade.py wires the default from the project's data-sensitivity
answer; run standalone to scrub a JSONL file in place:

    python -m evals.pipelines.redaction --input raw.jsonl --output clean.jsonl

Regex-based: emails, card-like numbers, SSN-like ids, phone numbers, IPv4.
Pattern order matters — broader number patterns run before narrower ones so a
card number isn't half-eaten by the phone pattern.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from re import Pattern
from re import compile as re_compile
from typing import Any

_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("EMAIL", re_compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("CARD", re_compile(r"(?<![\d-])(?:\d[ -]?){13,16}(?![\d-])")),
    ("SSN", re_compile(r"(?<![\d-])\d{3}-\d{2}-\d{4}(?![\d-])")),
    (
        "PHONE",
        re_compile(
            r"(?<![\d-])(?:\+?\d{1,2}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]?\d{4}(?![\d-])"
        ),
    ),
    ("IP", re_compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\.?\d)")),
]

# Interaction fields that carry free text worth scrubbing.
_TEXT_FIELDS = ("query", "response")


def redact_text(text: str) -> str:
    for label, pattern in _PATTERNS:
        text = pattern.sub(f"[{label}]", text)
    return text


def redact_interaction(record: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(record)
    for field in _TEXT_FIELDS:
        if isinstance(redacted.get(field), str):
            redacted[field] = redact_text(redacted[field])
    metadata = redacted.get("metadata")
    if isinstance(metadata, dict):
        redacted["metadata"] = {
            key: redact_text(value) if isinstance(value, str) else value
            for key, value in metadata.items()
        }
    return redacted


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m evals.pipelines.redaction")
    parser.add_argument("--input", type=Path, required=True, help="Interactions JSONL to scrub.")
    parser.add_argument(
        "--output", type=Path, required=True, help="Where to write the scrubbed JSONL."
    )
    args = parser.parse_args(argv)

    lines = args.input.read_text(encoding="utf-8").splitlines()
    records = [redact_interaction(json.loads(line)) for line in lines if line.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    print(f"Redacted {len(records)} record(s) -> {args.output}")


if __name__ == "__main__":
    main()
