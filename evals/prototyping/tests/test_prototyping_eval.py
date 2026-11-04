"""Tests for the prototyping eval: deterministic metrics and the --judgments path.

The module is loaded by file path. Importing it as `evals...` or `run` would collide with
`runs/ai/marketing-comms/evals/run.py`, which `pyproject.toml` puts on the import path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

RUN_PATH = Path(__file__).resolve().parent.parent / "run.py"
spec = importlib.util.spec_from_file_location("prototyping_eval_run", RUN_PATH)
assert spec is not None and spec.loader is not None
run = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = run
spec.loader.exec_module(run)


def good_reply(verdict: str) -> str:
    return f"<critique>Reasoned.</critique>\n<verdict>{verdict}</verdict>"


@pytest.fixture
def course_root(tmp_path: Path) -> Path:
    root = tmp_path / "learn-ai-engineering"
    (root / "generative-ai" / "notes").mkdir(parents=True)
    (root / "generative-ai" / "notes" / "01-rag.md").write_text("Recall was 0.81.\n")
    return root


@pytest.fixture
def one_case() -> list:
    return [
        run.Case(
            case_id="only-case",
            category="rag",
            prompt="We have 38 pages. What should we use?",
            minimum_solution="One LLM call with the file in the prompt.",
            minimum_size="very_small",
        )
    ]


OUTPUT = """# task
Date: 2026-11-04
Status: RESEARCHED

### Scope
Read docs/listed-only.md.

### Findings
- Recall was 0.81 on the support corpus (docs/source.md:1).
- Reranking helps a lot (docs/absent.md).

### Recommendation
Use one call.
"""


# ---------------------------------------------------------------------------
# Case file
# ---------------------------------------------------------------------------


def test_case_file_holds_two_cases_per_category_with_minimums() -> None:
    cases = run.load_cases()
    assert Counter(c.category for c in cases) == {
        "rag": 2,
        "evals": 2,
        "agent_loops": 2,
        "guardrails": 2,
    }
    assert all(c.minimum_solution.strip() for c in cases)


def test_case_file_has_very_small_minimums_so_overbuilding_is_detectable() -> None:
    sizes = Counter(c.minimum_size for c in run.load_cases())
    assert sizes["very_small"] >= 3


def test_prompts_do_not_leak_their_minimum_or_the_metrics() -> None:
    for case in run.load_cases():
        lowered = case.prompt.lower()
        assert "minimum" not in lowered
        assert "scope fit" not in lowered
        assert "smallest" not in lowered


def test_duplicate_case_ids_fail(tmp_path: Path) -> None:
    row = {
        "case_id": "same",
        "category": "rag",
        "prompt": "p",
        "minimum_solution": "m",
        "minimum_size": "small",
    }
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        run.load_cases(path)


def test_blank_minimum_solution_fails(tmp_path: Path) -> None:
    row = {
        "case_id": "c",
        "category": "rag",
        "prompt": "p",
        "minimum_solution": "  ",
        "minimum_size": "small",
    }
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="minimum_solution"):
        run.load_cases(path)


# ---------------------------------------------------------------------------
# Unsourced numbers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Recall reaches 92%.",
        "Latency drops to ~200ms.",
        "It costs $0.02 per call.",
        "Use 1,200 documents.",
        "Set a threshold of 0.85.",
        "It is 3x faster.",
        "Chunks of 512 work well.",
        "It takes 5 ms.",
    ],
)
def test_bare_measurements_are_unsourced(text: str) -> None:
    unsourced, total = run.unsourced_numbers(text)
    assert len(unsourced) == 1
    assert total == 1


@pytest.mark.parametrize(
    "text",
    [
        "Date: 2026-11-04",
        "It shipped in 2024.",
        "Use Python 3.12 here.",
        "Upgrade to v1.2.3 first.",
        "Use BM25 with GPT-4o.",
        "See `top_k=50` in the config.",
        "Phase 2 and Step 12 come later.",
        "There are 3 options.",
        "Write 2-3 sentences.",
        "See src/module_42/file_100.py:210 for that.",
        "https://example.com/1234 is the page.",
        "1. First thing\n2. Second thing",
        "# Heading with 500 in it",
        "```\nrecall = 0.92\n```",
    ],
)
def test_digits_that_are_not_measurements_do_not_count(text: str) -> None:
    assert run.unsourced_numbers(text) == ([], 0)


@pytest.mark.parametrize(
    "text",
    [
        "Recall was 92% (docs/eval.md:12).",
        "Recall was 92%, see https://example.com/paper.",
        "Recall was 92% (Lewis et al., 2020).",
        "Recall was 92% per [the eval](notes.md).",
        "Recall was 92% on a held-out set of real queries.",
        "Recall was 92% with n=200.",
        "We assume 500 requests.",
        "Recall was 92%. See docs/eval.md for the setup.",
        "| Recall | 92% | docs/eval.md |",
    ],
)
def test_a_source_or_setup_beside_the_number_clears_it(text: str) -> None:
    unsourced, total = run.unsourced_numbers(text)
    assert unsourced == []
    assert total >= 1


def test_a_source_two_sentences_away_is_not_beside() -> None:
    text = "Recall was 92%. That is good. See docs/eval.md."
    assert run.unsourced_numbers(text)[0] == ["92%"]


def test_a_source_in_another_table_row_is_not_beside() -> None:
    text = "| Recall | 92% |\n| Source | docs/eval.md |"
    assert run.unsourced_numbers(text)[0] == ["92%"]


def test_a_source_on_the_next_wrapped_line_is_beside() -> None:
    text = "Recall was 92% on the\ncorpus (docs/eval.md:12)."
    assert run.unsourced_numbers(text)[0] == []


def test_numbers_the_request_gave_need_no_source() -> None:
    request = "We have 1,200 pages and 40 KB."
    assert run.unsourced_numbers("With 1200 pages and 40KB this fits.", request) == ([], 0)
    assert run.unsourced_numbers("With 1300 pages this fits.", request)[0] == ["1300"]


# ---------------------------------------------------------------------------
# Course citations and practice reuse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        "learn-ai-engineering/generative-ai/notes/01-rag.md",
        "~/workspace/learn-ai-engineering/generative-ai/notes/01-rag.md",
        "../learn-ai-engineering/generative-ai/notes/01-rag.md",
        "course/generative-ai/notes/01-rag.md",
        "course/generative-ai/notes/01-rag",
        "course/generative-ai/notes",
    ],
)
def test_course_path_that_resolves_counts(ref: str, course_root: Path) -> None:
    resolved, unresolved = run.course_citations(f"See `{ref}`.", course_root)
    assert resolved == [ref]
    assert unresolved == []


def test_course_path_that_does_not_resolve_is_not_a_citation(course_root: Path) -> None:
    resolved, unresolved = run.course_citations(
        "See course/generative-ai/notes/99.md.", course_root
    )
    assert resolved == []
    assert unresolved == ["course/generative-ai/notes/99.md"]


def test_course_path_cannot_escape_the_course_root(course_root: Path, tmp_path: Path) -> None:
    (tmp_path / "outside.md").write_text("secret")
    resolved, unresolved = run.course_citations("See course/../outside.md.", course_root)
    assert resolved == []
    assert unresolved == ["course/../outside.md"]


def test_paths_merely_containing_course_are_not_citations(course_root: Path) -> None:
    text = "See data/courses/x.md and runs/course/x.md, and of course nothing else."
    assert run.course_citations(text, course_root) == ([], [])


def test_practice_paths_are_named_and_deduplicated() -> None:
    text = (
        "Reuse generative-ai/02-rag/practice/ablation.py and generative-ai/02-rag/practice/ablation.py, "
        "or practice/interviewing/round.md, or course/x/practice/."
    )
    assert run.practice_paths(text) == [
        "course/x/practice/",
        "generative-ai/02-rag/practice/ablation.py",
        "practice/interviewing/round.md",
    ]


def test_the_word_practice_is_not_a_path() -> None:
    assert run.practice_paths("In practice/theory this differs, in practice it is fine.") == []


# ---------------------------------------------------------------------------
# Claims and prompts
# ---------------------------------------------------------------------------


def test_claims_come_from_cited_sentences_outside_listing_sections() -> None:
    claims = run.extract_claims(OUTPUT)
    assert [c.citations[0].ref for c in claims] == ["docs/source.md:1", "docs/absent.md"]


def test_claim_ids_change_when_the_claim_changes() -> None:
    before = run.extract_claims("Recall was 0.81 (docs/a.md).")[0]
    after = run.extract_claims("Recall was 0.99 (docs/a.md).")[0]
    assert before.claim_id != after.claim_id


def test_product_names_are_not_citations() -> None:
    assert run.extract_citations("We could use Node.js or Next.js here.") == []


def test_a_sentence_with_two_sources_is_one_claim() -> None:
    claims = run.extract_claims("Both agree (docs/a.md, https://example.com/b).")
    assert len(claims) == 1
    assert {c.kind for c in claims[0].citations} == {"url", "local"}


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "source.md").write_text("Recall was 0.81 on the support corpus.\n")
    (root / ".env.local").write_text("KEY=do-not-copy")
    (root / "docs" / "api_secrets.md").write_text("KEY=do-not-copy")
    return root


def test_prompts_give_each_judge_only_what_its_criterion_needs(
    one_case: list, repo_root: Path, course_root: Path
) -> None:
    roots = (repo_root, course_root)
    prompts = run.build_prompts(one_case, {"only-case": OUTPUT}, roots, course_root)
    by_metric = {
        m: [p for p in prompts if p.metric == m] for m in (run.SCOPE_FIT, run.CLAIM_SUPPORT)
    }

    assert len(by_metric[run.SCOPE_FIT]) == 1
    assert len(by_metric[run.CLAIM_SUPPORT]) == 2
    scope = by_metric[run.SCOPE_FIT][0].text
    assert one_case[0].minimum_solution in scope
    assert OUTPUT in scope
    for prompt in by_metric[run.CLAIM_SUPPORT]:
        assert one_case[0].minimum_solution not in prompt.text


def test_critique_comes_before_verdict_in_both_judges() -> None:
    for judge in (run.SCOPE_FIT_JUDGE, run.CLAIM_SUPPORT_JUDGE):
        task = judge.partition("## Task")[2]
        assert task.index("<critique>") < task.index("<verdict>")
        assert "one thing only" in judge


def test_cited_source_text_is_inlined_and_a_missing_one_is_marked(
    repo_root: Path, course_root: Path
) -> None:
    roots = (repo_root, course_root)
    found = run.render_source(run.Citation("docs/source.md:1", "local"), roots, course_root)
    absent = run.render_source(run.Citation("docs/absent.md", "local"), roots, course_root)
    assert 'status="inlined"' in found
    assert "1: Recall was 0.81" in found
    assert 'status="unresolved"' in absent


def test_url_citation_is_left_for_the_judge_to_read(repo_root: Path, course_root: Path) -> None:
    rendered = run.render_source(
        run.Citation("https://example.com/x", "url"), (repo_root,), course_root
    )
    assert 'status="external"' in rendered
    assert "CANNOT_GRADE" in rendered


@pytest.mark.parametrize("ref", [".env.local", "docs/api_secrets.md", "../../etc/passwd.txt"])
def test_secrets_and_escaping_paths_are_never_inlined(
    ref: str, repo_root: Path, course_root: Path
) -> None:
    rendered = run.render_source(run.Citation(ref, "local"), (repo_root,), course_root)
    assert 'status="unresolved"' in rendered
    assert "do-not-copy" not in rendered


def test_emit_refuses_a_directory_with_earlier_prompts(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_text("stale")
    with pytest.raises(ValueError, match="already holds"):
        run.emit_prompts([], tmp_path)


# ---------------------------------------------------------------------------
# Verdict parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", ["PASS", "FAIL", "CANNOT_GRADE"])
def test_well_formed_reply_parses(verdict: str) -> None:
    assert run.parse_verdict(good_reply(verdict)) == verdict


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "PASS",
        "<verdict>PASS</verdict>",
        "<verdict>PASS</verdict><critique>Too late.</critique>",
        "<critique>  </critique><verdict>PASS</verdict>",
        "<critique>Fine.</critique><verdict>pass</verdict>",
        "<critique>Fine.</critique><verdict>MAYBE</verdict>",
        "<critique>Fine.</critique><verdict>PASS</verdict><verdict>FAIL</verdict>",
    ],
)
def test_malformed_reply_is_a_grader_error_not_a_fail(reply: str) -> None:
    assert run.parse_verdict(reply) == run.GRADER_ERROR


# ---------------------------------------------------------------------------
# The --judgments path
# ---------------------------------------------------------------------------


@pytest.fixture
def scored_setup(tmp_path: Path, one_case: list, course_root: Path) -> dict:
    cases_path = tmp_path / "cases.jsonl"
    case = one_case[0]
    cases_path.write_text(
        json.dumps(
            {
                "case_id": case.case_id,
                "category": case.category,
                "prompt": case.prompt,
                "minimum_solution": case.minimum_solution,
                "minimum_size": case.minimum_size,
            }
        )
    )
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "only-case.md").write_text(OUTPUT)
    claim_ids = [c.claim_id for c in run.extract_claims(OUTPUT)]
    return {
        "args": [
            "--cases",
            str(cases_path),
            "--outputs",
            str(outputs),
            "--course-root",
            str(course_root),
            "--json",
        ],
        "scope_id": run.scope_prompt_id("only-case"),
        "claim_ids": [run.claim_prompt_id("only-case", c) for c in claim_ids],
        "judgments": tmp_path / "judgments.jsonl",
        "outputs": outputs,
    }


def write_judgments(path: Path, replies: dict[str, str]) -> None:
    path.write_text("\n".join(json.dumps({"id": k, "response": v}) for k, v in replies.items()))


def score(setup: dict, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    code = run.main([*setup["args"], "--judgments", str(setup["judgments"])])
    return code, json.loads(capsys.readouterr().out)


def test_cannot_grade_is_not_a_pass_and_is_counted_separately(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = scored_setup["claim_ids"]
    write_judgments(
        scored_setup["judgments"],
        {
            run.components_prompt_id("only-case"): "<critique>None.</critique><count>0</count>",
            run.deferred_prompt_id("only-case"): "<critique>None.</critique><count>0</count>",
            scored_setup["scope_id"]: good_reply("PASS"),
            first: good_reply("PASS"),
            second: good_reply("CANNOT_GRADE"),
        },
    )
    code, report = score(scored_setup, capsys)
    claims = report["evidence"]["claim_support"]

    assert code == 0  # CANNOT_GRADE is a legitimate answer, so the run is complete.
    assert claims["pass"] == 1
    assert claims["cannot_grade"] == 1
    assert claims["n"] == 2
    assert claims["pass_rate"] == 50.0


def test_all_cannot_grade_scores_zero_not_a_vacuous_pass(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = scored_setup["claim_ids"]
    write_judgments(
        scored_setup["judgments"],
        {
            scored_setup["scope_id"]: good_reply("CANNOT_GRADE"),
            first: good_reply("CANNOT_GRADE"),
            second: good_reply("CANNOT_GRADE"),
        },
    )
    _, report = score(scored_setup, capsys)
    assert report["evidence"]["claim_support"]["pass_rate"] == 0.0
    assert report["evidence"]["scope_fit_primary"]["pass_rate"] == 0.0
    assert report["evidence"]["scope_fit_primary"]["cannot_grade"] == 1


def test_missing_judgment_is_not_a_pass_and_fails_the_run(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    first, _ = scored_setup["claim_ids"]
    write_judgments(
        scored_setup["judgments"],
        {scored_setup["scope_id"]: good_reply("PASS"), first: good_reply("PASS")},
    )
    code, report = score(scored_setup, capsys)
    claims = report["evidence"]["claim_support"]
    assert code == 1
    assert report["complete"] is False
    assert claims["missing_judgments"] == 1
    assert claims["pass_rate"] == 50.0


def test_malformed_judgment_is_a_grader_error_and_fails_the_run(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = scored_setup["claim_ids"]
    write_judgments(
        scored_setup["judgments"],
        {
            scored_setup["scope_id"]: "looks fine",
            first: good_reply("PASS"),
            second: good_reply("FAIL"),
        },
    )
    code, report = score(scored_setup, capsys)
    scope = report["evidence"]["scope_fit_primary"]
    assert code == 1
    assert scope["grader_errors"] == 1
    assert scope["fail"] == 0
    assert scope["pass"] == 0


def test_judgment_matching_no_prompt_fails_the_run(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = scored_setup["claim_ids"]
    write_judgments(
        scored_setup["judgments"],
        {
            scored_setup["scope_id"]: good_reply("PASS"),
            first: good_reply("PASS"),
            second: good_reply("PASS"),
            "claim_support--only-case--99-stale0": good_reply("PASS"),
        },
    )
    code, report = score(scored_setup, capsys)
    assert code == 1
    assert report["unknown_judgments"] == ["claim_support--only-case--99-stale0"]


def test_judgment_goes_stale_when_the_output_changes(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = scored_setup["claim_ids"]
    write_judgments(
        scored_setup["judgments"],
        {
            scored_setup["scope_id"]: good_reply("PASS"),
            first: good_reply("PASS"),
            second: good_reply("PASS"),
        },
    )
    edited = OUTPUT.replace("0.81", "0.99")
    (scored_setup["outputs"] / "only-case.md").write_text(edited)
    code, report = score(scored_setup, capsys)
    assert code == 1
    assert report["evidence"]["claim_support"]["missing_judgments"] == 1
    assert first in report["unknown_judgments"]


def test_duplicate_judgments_are_refused(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    row = json.dumps({"id": scored_setup["scope_id"], "response": good_reply("PASS")})
    scored_setup["judgments"].write_text(f"{row}\n{row}\n")
    code = run.main([*scored_setup["args"], "--judgments", str(scored_setup["judgments"])])
    assert code == 2
    assert "duplicate" in capsys.readouterr().err


def test_judgments_row_without_a_response_is_refused(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    scored_setup["judgments"].write_text(json.dumps({"id": "x"}))
    assert run.main([*scored_setup["args"], "--judgments", str(scored_setup["judgments"])]) == 2
    assert "expected id and response" in capsys.readouterr().err


def test_judgments_directory_matches_emitted_prompt_names(
    scored_setup: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompts_dir = tmp_path / "prompts"
    assert run.main([*scored_setup["args"], "--emit-prompts", str(prompts_dir)]) == 0
    capsys.readouterr()

    replies = tmp_path / "replies"
    replies.mkdir()
    for prompt in prompts_dir.glob("*.txt"):
        is_count = prompt.name.startswith((run.EXTRA_COMPONENTS, run.DEFERRED_COMPONENTS))
        (replies / prompt.name).write_text(
            "<critique>None.</critique><count>0</count>" if is_count else good_reply("FAIL")
        )

    code = run.main([*scored_setup["args"], "--judgments", str(replies)])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["evidence"]["claim_support"]["fail"] == 2
    assert report["evidence"]["scope_fit_primary"]["fail"] == 1


def test_no_cited_claims_is_na_and_counted_not_a_perfect_score(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    (scored_setup["outputs"] / "only-case.md").write_text("### Recommendation\nUse one call.\n")
    write_judgments(
        scored_setup["judgments"],
        {
            scored_setup["scope_id"]: good_reply("PASS"),
            run.components_prompt_id("only-case"): "<critique>None.</critique><count>0</count>",
            run.deferred_prompt_id("only-case"): "<critique>None.</critique><count>0</count>",
        },
    )
    code, report = score(scored_setup, capsys)
    claims = report["evidence"]["claim_support"]
    assert code == 0
    assert claims["n"] == 0
    assert claims["pass_rate"] is None
    assert claims["cases_with_no_cited_claims"] == 1


def test_without_judgments_the_judge_metrics_are_absent_not_zero(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run.main(scored_setup["args"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["mode"] == "deterministic-only"
    assert report["evidence"]["scope_fit_primary"] is None
    assert report["evidence"]["claim_support"] is None


@pytest.mark.parametrize("content", [None, "  \n"])
def test_missing_or_empty_output_is_excluded_and_fails_the_run(
    content: str | None, scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    path = scored_setup["outputs"] / "only-case.md"
    path.unlink()
    if content is not None:
        path.write_text(content)
    code = run.main(scored_setup["args"])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["missing_outputs"] == ["only-case"]
    assert report["scored"] == 0


def test_misnamed_output_file_fails_the_run(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    (scored_setup["outputs"] / "only-cse.md").write_text(OUTPUT)
    code = run.main(scored_setup["args"])
    assert code == 1
    assert json.loads(capsys.readouterr().out)["unexpected_outputs"] == ["only-cse.md"]


# ---------------------------------------------------------------------------
# Dry run and labelling
# ---------------------------------------------------------------------------


def test_dry_run_is_complete_and_exercises_every_verdict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run.main(["--dry-run", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    claims = report["evidence"]["claim_support"]
    scope = report["evidence"]["scope_fit_primary"]

    assert report["complete"] is True
    assert report["scored"] == 8
    assert scope["pass"] and scope["fail"]
    assert claims["pass"] and claims["fail"] and claims["cannot_grade"]
    assert report["evidence"]["unsourced_numbers"]["unsourced"] > 0
    assert report["compliance"]["course_citations"]["resolved"] > 0
    assert report["compliance"]["course_citations"]["unresolved"] > 0
    assert report["compliance"]["practice_reuse"]["paths_named"] > 0


def test_dry_run_writes_nothing_into_the_repo(capsys: pytest.CaptureFixture[str]) -> None:
    before = sorted(p.name for p in RUN_PATH.parent.iterdir())
    run.main(["--dry-run"])
    capsys.readouterr()
    assert sorted(p.name for p in RUN_PATH.parent.iterdir()) == before


def test_compliance_is_labelled_in_output_and_docstring(
    capsys: pytest.CaptureFixture[str],
) -> None:
    run.main(["--dry-run"])
    text = capsys.readouterr().out
    assert "COMPLIANCE" in text
    assert "can never show improvement on their own" in text
    assert "COMPLIANCE" in run.__doc__
    assert "can never show improvement" in " ".join(run.__doc__.split())

    run.main(["--dry-run", "--json"])
    report = json.loads(capsys.readouterr().out)
    assert "course_citations" in report["compliance"]
    assert "course_citations" not in report["evidence"]


def test_direction_not_significance_is_stated(capsys: pytest.CaptureFixture[str]) -> None:
    assert "Eight cases give a direction, not" in " ".join(run.__doc__.split())
    run.main(["--dry-run"])
    assert "direction, not significance" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--dry-run", "--outputs", "x"],
        ["--outputs", "x", "--emit-prompts", "y", "--judgments", "z"],
    ],
)
def test_contradictory_modes_are_refused(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run.main(argv)
    assert excinfo.value.code == 2
    capsys.readouterr()


def _resolver_tree(root):
    for rel in (
        ".claude/specs/agent-eval.md",
        "README.md",
        "template/llm_kit/README.md",
        "template/core/index.py",
        "template/core/settings.py",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")
    return root


def test_shortened_spec_name_resolves_to_its_only_file(tmp_path):
    root = _resolver_tree(tmp_path / "shortened")
    found = run.resolve_local("agent-eval.md:3", (root,), root)
    assert found == (root / ".claude/specs/agent-eval.md").resolve()


def test_ambiguous_bare_name_does_not_resolve_even_at_the_root(tmp_path):
    root = _resolver_tree(tmp_path / "ambiguous")
    assert run.resolve_local("README.md:11", (root,), root) is None


def test_full_path_to_a_name_used_elsewhere_still_resolves(tmp_path):
    root = _resolver_tree(tmp_path / "full")
    found = run.resolve_local("template/llm_kit/README.md", (root,), root)
    assert found == (root / "template/llm_kit/README.md").resolve()


def test_bare_code_name_outside_claude_stays_unresolved(tmp_path):
    root = _resolver_tree(tmp_path / "code")
    assert run.resolve_local("settings.py", (root,), root) is None


def test_partial_path_resolves_by_suffix_with_or_without_leading_slash(tmp_path):
    root = _resolver_tree(tmp_path / "suffix")
    expected = (root / "template/core/index.py").resolve()
    assert run.resolve_local("core/index.py", (root,), root) == expected
    assert run.resolve_local("/core/index.py", (root,), root) == expected


def test_line_shorthand_adds_citations_to_the_file_before_it():
    claims = run.extract_claims("It breaks (`docs/a.md:24`) and again (`:35`), see (`:44-46`).")
    assert [c.ref for c in claims[0].citations] == [
        "docs/a.md:24",
        "docs/a.md:35",
        "docs/a.md:44-46",
    ]


def test_line_shorthand_carries_into_a_later_sentence():
    claims = run.extract_claims("One holds (`docs/a.md:1`). Another holds too (`:78`).")
    assert [c.ref for c in claims[1].citations] == ["docs/a.md:78"]


def test_line_shorthand_without_an_earlier_file_is_not_a_claim():
    assert run.extract_claims("Nothing named this one (`:78`).") == []


def test_parse_count_is_strict():
    assert run.parse_count("<critique>1. A store.</critique>\n<count>1</count>") == 1
    assert run.parse_count("<critique>None.</critique><count>0</count>") == 0
    assert (
        run.parse_count("<critique>Empty.</critique><count>CANNOT_GRADE</count>") == "CANNOT_GRADE"
    )
    assert run.parse_count("<count>3</count>") == run.GRADER_ERROR
    assert run.parse_count("<critique> </critique><count>3</count>") == run.GRADER_ERROR
    assert run.parse_count("<critique>x</critique><count>many</count>") == run.GRADER_ERROR


def test_components_summary_never_counts_an_ungraded_case_as_zero():
    summary = run._components_summary([2, 4, "CANNOT_GRADE", run.MISSING])
    assert (summary["total"], summary["graded"], summary["mean"]) == (6, 2, 3.0)
    assert summary["cannot_grade"] == 1
    assert summary["missing_judgments"] == 1


def test_deferred_components_are_scored_apart_from_extra_components(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    (scored_setup["outputs"] / "only-case.md").write_text("### Recommendation\nUse one call.\n")
    write_judgments(
        scored_setup["judgments"],
        {
            scored_setup["scope_id"]: good_reply("PASS"),
            run.components_prompt_id("only-case"): "<critique>None.</critique><count>1</count>",
            run.deferred_prompt_id("only-case"): "<critique>a, b, c</critique><count>3</count>",
        },
    )
    code, report = score(scored_setup, capsys)
    assert code == 0
    assert report["evidence"]["extra_components"]["total"] == 1
    assert report["evidence"]["deferred_components"]["total"] == 3
    assert report["per_case"][0]["deferred_components"] == 3


def test_missing_deferred_count_makes_the_run_incomplete(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    (scored_setup["outputs"] / "only-case.md").write_text("### Recommendation\nUse one call.\n")
    write_judgments(
        scored_setup["judgments"],
        {
            scored_setup["scope_id"]: good_reply("PASS"),
            run.components_prompt_id("only-case"): "<critique>None.</critique><count>0</count>",
        },
    )
    code, report = score(scored_setup, capsys)
    assert code == 1
    assert report["evidence"]["deferred_components"]["missing_judgments"] == 1


def test_adding_the_deferred_judge_left_the_baseline_judges_unchanged():
    baseline = json.loads((Path(run.__file__).parent / "baseline-2026-11-04.json").read_text())
    current = run._sha256(
        run.SCOPE_FIT_JUDGE + run.EXTRA_COMPONENTS_JUDGE + run.CLAIM_SUPPORT_JUDGE
    )
    assert current == baseline["judges"]["prompt_sha256"]


def test_missing_component_count_makes_the_run_incomplete(
    scored_setup: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    (scored_setup["outputs"] / "only-case.md").write_text("### Recommendation\nUse one call.\n")
    write_judgments(scored_setup["judgments"], {scored_setup["scope_id"]: good_reply("PASS")})
    code, report = score(scored_setup, capsys)
    assert code == 1
    assert report["evidence"]["extra_components"]["missing_judgments"] == 1


def test_line_shorthand_after_a_sentence_naming_two_files_attaches_to_neither():
    claims = run.extract_claims(
        "Both agree (`docs/a.md:1`, `docs/b.md:2`). That spec differs (`:9`)."
    )
    assert len(claims) == 1
    assert {c.ref for c in claims[0].citations} == {"docs/a.md:1", "docs/b.md:2"}


def test_line_shorthand_in_the_same_sentence_follows_the_nearest_file():
    claims = run.extract_claims("See (`docs/a.md:1`, `:2`) and (`docs/b.md:3`, `:4`).")
    assert {c.ref for c in claims[0].citations} == {
        "docs/a.md:1",
        "docs/a.md:2",
        "docs/b.md:3",
        "docs/b.md:4",
    }


def test_course_grounding_section_makes_no_claims() -> None:
    """Grounding lists what was read, so its `- used:` lines are not claims about the source."""
    output = (
        "### Course grounding\n"
        "- query: retrieval design\n"
        "- used: `notes/01-chunking.md`\n\n"
        "### Findings\n"
        "Chunking helps, per `notes/01-chunking.md`.\n"
    )
    claims = run.extract_claims(output)
    assert len(claims) == 1
    assert "Chunking helps" in claims[0].text
