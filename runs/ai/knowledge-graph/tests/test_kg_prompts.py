"""The proposer prompt states the pack, and the snippet fixtures (spec F9) exercise the
pipeline's handling of proposer output.

The snippet tests run against the scripted proposer: they pin what the gates do with
well-formed, near-miss and injected candidates, and are the file a live run later asserts
the real model against. They do not test the model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kg_fakes import ScriptedProposer

from kg.contract import load_pack
from kg.gates import MIN_QUOTE_CHARS, run_gates
from kg.models import Candidate
from kg.profile import Page
from kg.propose import build_prompt, build_schema

HERE = Path(__file__).parent
PACK = load_pack(HERE.parent / "packs" / "eval-v1.json")
INJECTED = (HERE / "fixtures" / "pages" / "injected.md").read_text(encoding="utf-8")
SNIPPETS = [
    json.loads(line)
    for line in (HERE / "fixtures" / "snippets.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]


def _prompt(body: str = "Some page body that is long enough.") -> str:
    return build_prompt(Page(path="eval/x.md", body=body), PACK)


def test_prompt_names_every_entity_and_relation_type() -> None:
    prompt = _prompt()
    for e in PACK.entity_types:
        assert e.name in prompt
        assert e.definition in prompt
    for r in PACK.relation_types:
        assert r.name in prompt
        assert r.definition in prompt


def test_prompt_carries_every_boundary_example() -> None:
    prompt = _prompt()
    examples = [
        ex for t in (*PACK.entity_types, *PACK.relation_types) for ex in t.boundary_examples
    ]
    assert examples
    assert all(ex in prompt for ex in examples)


def test_prompt_demands_a_verbatim_quote_of_minimum_length() -> None:
    prompt = _prompt()
    assert "EXACTLY" in prompt
    assert "character for character" in prompt
    assert f"at least {MIN_QUOTE_CHARS} characters" in prompt


def test_prompt_fences_page_text_as_data_and_embeds_it_unaltered() -> None:
    prompt = _prompt(INJECTED)
    assert "untrusted data" in prompt
    assert INJECTED in prompt  # unaltered: the quote must stay verbatim against the body
    assert (
        prompt.index("<page_text>")
        < prompt.index("Ignore all previous")
        < prompt.index("</page_text>")
    )


def test_schema_enumerates_pack_types_and_requires_every_field() -> None:
    schema = build_schema(PACK)
    item = schema["properties"]["candidates"]["items"]
    assert item["properties"]["subject_type"]["enum"] == [e.name for e in PACK.entity_types]
    assert item["properties"]["relation"]["enum"] == [r.name for r in PACK.relation_types]
    assert set(item["required"]) == set(Candidate.model_fields)
    assert item["additionalProperties"] is False


def _cand(row: dict) -> Candidate:
    return Candidate(**row)


def _triple(c: Candidate) -> list[str]:
    return [c.subject, c.relation, c.object]


async def _run(row: dict) -> tuple[list[list[str]], list[tuple[list[str], dict]]]:
    page = Page(path=f"snippets/{row['id']}.md", body=row["body"])
    proposer = ScriptedProposer({page.path: [_cand(c) for c in row["proposed"]]})
    result = await proposer.propose(page, PACK)
    survived, rejected = [], []
    for cand in result.candidates:
        report = run_gates(cand, page.body, PACK, page.path)
        if report.passed:
            survived.append(_triple(cand))
        else:
            rejected.append((_triple(cand), report.failed))
    return survived, rejected


def test_snippets_cover_the_cases_the_plan_names() -> None:
    assert 6 <= len(SNIPPETS) <= 10
    gates = {r["gate"] for s in SNIPPETS for r in s["rejected"]}
    assert {"verbatim", "attested", "schema"} <= gates  # a hard negative per gate
    assert any(not s["rejected"] for s in SNIPPETS)


@pytest.mark.parametrize("row", SNIPPETS, ids=[s["id"] for s in SNIPPETS])
async def test_snippet_survivors_and_named_rejections(row: dict) -> None:
    survived, rejected = await _run(row)

    assert survived == row["survive"]
    assert [t for t, _ in rejected] == [r["triple"] for r in row["rejected"]]
    for (_, failed), want in zip(rejected, row["rejected"], strict=True):
        assert want["gate"] in failed, f"expected {want['gate']} to reject, got {sorted(failed)}"
