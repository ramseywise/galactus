from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from kg.contract import load_pack
from kg.label import (
    GoldRow,
    LabelRejected,
    append_row,
    label_loop,
    make_row,
    read_gold,
    split_for,
)
from kg.profile import normalise

HERE = Path(__file__).parent
PACK = load_pack(HERE.parent / "packs" / "eval-v1.json")
NORMAL = normalise((HERE / "fixtures/pages/normal.md").read_text())
GOOD_QUOTE = "Position bias is a FailureMode that swapping answer order mitigates."
GOOD = {
    "page": "eval/normal.md",
    "body": NORMAL,
    "subject": "swapping answer order",
    "subject_type": "Method",
    "relation": "mitigates",
    "object": "position bias",
    "object_type": "FailureMode",
    "quote": GOOD_QUOTE,
    "label": "positive",
    "labelled_by": "t",
}


def test_good_row_is_made_and_split_is_a_function_of_id() -> None:
    row = make_row(**GOOD, pack=PACK)
    assert row.split == split_for(row.id)
    assert make_row(**GOOD, pack=PACK) == row


def test_non_verbatim_quote_rejected_and_nothing_appended(tmp_path: Path) -> None:
    out = tmp_path / "gold.jsonl"
    with pytest.raises(LabelRejected, match="verbatim"):
        make_row(**{**GOOD, "quote": "Swapping answer order cures position bias entirely."})
    assert not out.exists()


def test_unattested_entity_rejected() -> None:
    with pytest.raises(LabelRejected, match="attested"):
        make_row(**{**GOOD, "object": "self-preference bias"})


@pytest.mark.parametrize("label", ["hard_negative", "control"])
def test_negatives_face_the_same_gates(label: str) -> None:
    bad = {**GOOD, "label": label, "quote": "this sentence is nowhere in the page at all"}
    with pytest.raises(LabelRejected, match="verbatim"):
        make_row(**bad)


def test_schema_gate_only_with_a_pack() -> None:
    wrong = {**GOOD, "relation": "invented-relation"}
    make_row(**wrong)  # no pack: not checked
    with pytest.raises(LabelRejected, match="schema"):
        make_row(**wrong, pack=PACK)


def test_append_only_refuses_duplicate_and_never_rewrites(tmp_path: Path) -> None:
    out = tmp_path / "gold.jsonl"
    row = make_row(**GOOD)
    append_row(out, row)
    before = out.read_text()
    with pytest.raises(LabelRejected, match="append-only"):
        append_row(out, row)
    assert out.read_text() == before
    assert read_gold(out) == [row]


def test_split_deterministic_and_roughly_60_20_20() -> None:
    ids = [f"id-{i}" for i in range(20000)]
    first = [split_for(i) for i in ids]
    assert first == [split_for(i) for i in ids]
    counts = Counter(first)
    for name, share in (("train", 0.6), ("dev", 0.2), ("test", 0.2)):
        assert abs(counts[name] / len(ids) - share) < 0.015


def test_gold_small_fixture_parses_with_expected_counts() -> None:
    rows = read_gold(HERE / "fixtures" / "gold_small.jsonl")
    assert Counter(r.label for r in rows) == {"positive": 6, "hard_negative": 4, "control": 2}
    assert all(r.split == split_for(r.id) for r in rows)
    assert any(r.split == "test" for r in rows)


def test_gold_small_rows_still_pass_every_gate() -> None:
    from kg.gates import run_gates

    bodies = {
        f"eval/{n}.md": normalise((HERE / f"fixtures/pages/{n}.md").read_text())
        for n in ("normal", "injected")
    }
    for r in read_gold(HERE / "fixtures" / "gold_small.jsonl"):
        assert run_gates(r.candidate(), bodies[r.page], PACK, r.page).passed, r.id


def test_extra_keys_rejected() -> None:
    d = json.loads(make_row(**GOOD).model_dump_json()) | {"extra": 1}
    with pytest.raises(ValueError):
        GoldRow.model_validate(d)


def test_label_loop_saves_good_and_rejects_bad(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    (root / "eval").mkdir(parents=True)
    shutil.copy(HERE / "fixtures/pages/normal.md", root / "eval" / "normal.md")
    answers = iter(
        [
            # bad: quote not verbatim -> not saved, re-asked
            "swapping answer order", "Method", "mitigates", "position bias", "FailureMode",
            "made up sentence that is not on the page", "positive",
            # good
            "swapping answer order", "Method", "mitigates", "position bias", "FailureMode",
            GOOD_QUOTE, "positive",
            "",  # next page / done
        ]
    )  # fmt: skip
    printed: list[str] = []
    out = tmp_path / "gold.jsonl"
    saved = label_loop(
        root,
        "eval",
        out,
        input_fn=lambda _p: next(answers),
        print_fn=lambda *a: printed.append(" ".join(map(str, a))),
    )
    assert saved == 1
    assert len(read_gold(out)) == 1
    assert any("NOT SAVED" in p and "verbatim" in p for p in printed)
