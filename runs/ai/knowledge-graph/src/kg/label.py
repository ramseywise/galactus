"""Gold-set labelling: the row schema, entry-time validation and the append-only file.

A label is saved only if it would survive the gates it will later be scored against.
`make_row` runs the verbatim and attested gates (and schema, when a pack is given) against
the page's normalised body at entry, so a bad label cannot reach the file.

Gate policy by label:

* `positive`: all gates must pass.
* `hard_negative` (verbatim quote, right entities, wrong relation): all gates must pass too.
  A hard negative that a gate would have caught never reaches the judge, so it measures
  nothing about the judge.
* `control` (a quoted instruction or other bait): the same, for the same reason.

The judge's job is therefore the only thing left that separates `positive` from the other
two labels, which is what calibration scores.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kg.contract import Pack, load_pack
from kg.gates import attested, quote_verbatim, run_gates
from kg.models import Candidate
from kg.profile import iter_pages

GoldLabel = Literal["positive", "hard_negative", "control"]
Split = Literal["train", "dev", "test"]

LABELS: tuple[str, ...] = ("positive", "hard_negative", "control")
SPLIT_BUCKETS = 100
TRAIN_UPTO, DEV_UPTO = 60, 80  # buckets [0,60) train, [60,80) dev, [80,100) test


class LabelRejected(ValueError):  # noqa: N818 — reads as the event, like BuildRefused
    """A label failed a gate at entry; nothing was written."""


class GoldRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    page: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    object: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    label: GoldLabel
    split: Split
    labelled_by: str = Field(min_length=1)
    at: str = Field(min_length=1)

    @property
    def expected_supported(self) -> bool:
        """Ground truth for the judge: only `positive` rows are supported."""
        return self.label == "positive"

    def candidate(self) -> Candidate:
        return Candidate(
            subject=self.subject,
            subject_type=self.subject_type,
            relation=self.relation,
            object=self.object,
            object_type=self.object_type,
            quote=self.quote,
        )


def row_id(page: str, subject: str, relation: str, obj: str, quote: str) -> str:
    """Stable id from the triple and its evidence (not the label, so a relabel collides)."""
    raw = "\x1f".join((page, subject, relation, obj, quote))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def split_for(row_id_: str) -> Split:
    """60/20/20 train/dev/test by hash of the id: deterministic, independent of file order."""
    bucket = int(hashlib.sha256(row_id_.encode("utf-8")).hexdigest(), 16) % SPLIT_BUCKETS
    if bucket < TRAIN_UPTO:
        return "train"
    return "dev" if bucket < DEV_UPTO else "test"


def make_row(
    *,
    page: str,
    body: str,
    subject: str,
    subject_type: str,
    relation: str,
    object: str,
    object_type: str,
    quote: str,
    label: GoldLabel,
    labelled_by: str,
    pack: Pack | None = None,
    at: str | None = None,
) -> GoldRow:
    """Validate against the gates now and return the row, or raise `LabelRejected`.

    `body` is the page's normalised body. Schema is checked only when `pack` is given.
    """
    if label not in LABELS:
        raise LabelRejected(f"label must be one of {LABELS}, got {label!r}")
    candidate = Candidate(
        subject=subject,
        subject_type=subject_type,
        relation=relation,
        object=object,
        object_type=object_type,
        quote=quote,
    )
    if pack is not None:
        failed = run_gates(candidate, body, pack, page).failed
    else:
        checks = {
            "verbatim": quote_verbatim.check(candidate, body),
            "attested": attested.check(candidate),
        }
        failed = {name: res.reason for name, res in checks.items() if not res.passed}
    if failed:
        detail = "; ".join(f"{name}: {why}" for name, why in failed.items())
        raise LabelRejected(f"rejected by gate ({detail})")
    rid = row_id(page, subject, relation, object, quote)
    return GoldRow(
        id=rid,
        page=page,
        subject=subject,
        subject_type=subject_type,
        relation=relation,
        object=object,
        object_type=object_type,
        quote=quote,
        label=label,
        split=split_for(rid),
        labelled_by=labelled_by,
        at=at or datetime.now(UTC).isoformat(timespec="seconds"),
    )


def read_gold(path: Path) -> list[GoldRow]:
    """Parse the JSONL; a malformed line raises with its line number. Missing file = empty."""
    if not path.exists():
        return []
    rows: list[GoldRow] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(GoldRow.model_validate(json.loads(line)))
        except ValueError as exc:
            raise ValueError(f"{path}:{n}: {exc}") from exc
    return rows


def append_row(path: Path, row: GoldRow) -> None:
    """Append one row. Never rewrites: an existing id is an error, not an overwrite."""
    if any(r.id == row.id for r in read_gold(path)):
        raise LabelRejected(f"id {row.id} is already labelled; the file is append-only")
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_newline = path.exists() and path.stat().st_size > 0 and not _ends_with_newline(path)
    with path.open("a", encoding="utf-8") as fh:
        if needs_newline:
            fh.write("\n")
        fh.write(row.model_dump_json() + "\n")


def _ends_with_newline(path: Path) -> bool:
    with path.open("rb") as fh:
        fh.seek(-1, 2)
        return fh.read(1) == b"\n"


_FIELDS = ("subject", "subject_type", "relation", "object", "object_type")


def label_loop(
    corpus_root: Path,
    domain: str,
    out_path: Path,
    *,
    labelled_by: str = "human",
    pack: Pack | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[..., None] = print,
) -> int:
    """Walk the domain's pages; per page, take triples until a blank subject. Returns rows saved.

    Per triple: subject, subject_type, relation, object, object_type, quote, label. A rejected
    label prints the failed gate and is re-asked; `q` as a subject ends the session.
    """
    saved = 0
    for page in iter_pages(corpus_root, domain):
        print_fn(f"\n=== {page.path} ===\n{page.body}\n")
        while True:
            subject = input_fn("subject (blank = next page, q = quit): ").strip()
            if subject == "q":
                return saved
            if not subject:
                break
            values = {"subject": subject}
            for name in _FIELDS[1:]:
                values[name] = input_fn(f"{name}: ").strip()
            quote = input_fn("quote (verbatim from the body above): ").strip()
            label = input_fn(f"label ({'/'.join(LABELS)}): ").strip()
            try:
                row = make_row(
                    page=page.path,
                    body=page.body,
                    quote=quote,
                    label=label,  # type: ignore[arg-type] — validated in make_row
                    labelled_by=labelled_by,
                    pack=pack,
                    **values,
                )
                append_row(out_path, row)
            except (LabelRejected, ValueError) as exc:
                print_fn(f"NOT SAVED: {exc}")
                continue
            saved += 1
            print_fn(f"saved {row.id} [{row.label}, split={row.split}]")
    return saved


def main(argv: list[str] | None = None) -> int:
    """Entry for `kg label eval`: `--corpus-root`, `--domain`, `--out`, optional `--pack`."""
    import argparse

    ap = argparse.ArgumentParser(prog="kg label")
    ap.add_argument("--corpus-root", type=Path, required=True)
    ap.add_argument("--domain", default="eval")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pack", type=Path, default=None, help="also enforce the schema gate")
    ap.add_argument("--labelled-by", default="human")
    args = ap.parse_args(argv)
    pack = load_pack(args.pack) if args.pack else None
    saved = label_loop(
        args.corpus_root, args.domain, args.out, labelled_by=args.labelled_by, pack=pack
    )
    print(f"{saved} row(s) appended to {args.out}")
    return 0
