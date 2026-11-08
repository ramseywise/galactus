"""The four gates: verbatim (unique, long enough), attested, schema-conform, dedupe."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from kg.contract import load_pack
from kg.gates import MIN_QUOTE_CHARS, attested, dedupe, quote_verbatim, run_gates, schema_conform
from kg.models import Candidate, Evidence, PageResult, Triple, canonical_key
from kg.profile import normalise

HERE = Path(__file__).parent
PACK = load_pack(HERE.parent / "packs" / "eval-v1.json")
NORMAL_RAW = (HERE / "fixtures" / "pages" / "normal.md").read_text(encoding="utf-8")
NORMAL = normalise(NORMAL_RAW)


def cand(quote: str, **kw: str) -> Candidate:
    fields = {
        "subject": "swapping answer order",
        "subject_type": "Method",
        "relation": "mitigates",
        "object": "position bias",
        "object_type": "FailureMode",
        "quote": quote,
    }
    fields.update(kw)
    return Candidate(**fields)


# --- verbatim -------------------------------------------------------------------------


def test_quote_from_frontmatter_fails_but_same_text_in_body_passes() -> None:
    q = "Frontmatter says the judge drifts after every prompt change."
    assert quote_verbatim.check(cand(q), NORMAL).reason == "quote not verbatim in normalised body"
    with_body = normalise(NORMAL_RAW + f"\n{q}\n")
    assert quote_verbatim.check(cand(q), with_body).passed


def test_quote_from_wikilink_target_fails_but_display_text_passes() -> None:
    target = "Calibration is measured with Expected Calibration Error"
    display = "Calibration is measured with ECE, and the Gold Set supplies the labels."
    assert not quote_verbatim.check(cand(target), NORMAL).passed
    assert quote_verbatim.check(cand(display), NORMAL).passed


def test_quote_across_a_hard_wrap_matches() -> None:
    q = "must be calibrated against human labels before its verdicts are trusted"
    assert quote_verbatim.check(cand(q), NORMAL).passed


def test_repeated_quote_is_ambiguous() -> None:
    q = "Swapping answer order mitigates position bias in pairwise judging."
    r = quote_verbatim.check(cand(q), NORMAL)
    assert not r.passed and r.reason == "quote ambiguous: 2 occurrences"


def test_short_quote_rejected() -> None:
    q = "LLM judge."  # 10 chars
    assert len(q) == 10 < MIN_QUOTE_CHARS
    assert quote_verbatim.check(cand(q), NORMAL).reason == "quote too short to locate"


def test_span_is_recomputed() -> None:
    q = "Position bias is a FailureMode that swapping answer order mitigates."
    r = quote_verbatim.check(cand(q), NORMAL)
    assert r.passed and r.span is not None
    assert NORMAL[r.span[0] : r.span[1]] == q


# --- attested -------------------------------------------------------------------------


def test_both_entities_in_quote_pass_case_insensitively() -> None:
    q = "Position bias is a FailureMode that swapping answer order mitigates."
    assert attested.check(cand(q)).passed


def test_entity_missing_from_quote_fails() -> None:
    q = "Position bias is a FailureMode that swapping answer order mitigates."
    r = attested.check(cand(q, subject="calibration"))
    assert not r.passed and r.reason == "subject not named in the quote"
    r = attested.check(cand(q, subject="calibration", object="gold set"))
    assert r.reason == "subject and object not named in the quote"


# --- schema-conform -------------------------------------------------------------------


def test_conforming_candidate_passes() -> None:
    assert schema_conform.check(cand("x" * 20), PACK).passed


@pytest.mark.parametrize(
    ("override", "reason_part"),
    [
        ({"subject_type": "Gadget"}, "subject type 'Gadget'"),
        ({"object_type": "Gadget"}, "object type 'Gadget'"),
        ({"relation": "causes"}, "relation 'causes'"),
        ({"subject_type": "Tool"}, "needs a Method subject"),
        ({"object_type": "Metric"}, "needs a FailureMode object"),
    ],
)
def test_nonconforming_candidate_fails(override: dict[str, str], reason_part: str) -> None:
    r = schema_conform.check(cand("x" * 20, **override), PACK)
    assert not r.passed and reason_part in (r.reason or "")


def test_wildcard_domain_and_range_admit_any_pack_type() -> None:
    c = cand("x" * 20, relation="instance-of", subject_type="Tool", object_type="Role")
    assert schema_conform.check(c, PACK).passed
    c = cand("x" * 20, relation="produces", subject_type="Role", object_type="Artifact")
    assert schema_conform.check(c, PACK).passed
    c = cand("x" * 20, relation="produces", subject_type="Role", object_type="Tool")
    assert not schema_conform.check(c, PACK).passed


# --- run_gates and evidence -----------------------------------------------------------


def test_run_gates_reports_every_gate_and_builds_evidence() -> None:
    q = "Position bias is a FailureMode that swapping answer order mitigates."
    report = run_gates(cand(q), NORMAL, PACK, "eval/normal.md")
    assert report.passed and set(report.results) == {"verbatim", "attested", "schema"}
    ev = report.evidence()
    assert NORMAL[ev.span[0] : ev.span[1]] == q and ev.page_path == "eval/normal.md"


def test_failed_report_has_no_evidence() -> None:
    report = run_gates(cand("LLM judge."), NORMAL, PACK, "eval/normal.md")
    assert not report.passed and "verbatim" in report.failed
    with pytest.raises(ValueError, match="passed every gate"):
        report.evidence()


def test_evidence_span_must_fit_quote() -> None:
    with pytest.raises(ValidationError, match="does not fit"):
        Evidence(quote="abc", span=(0, 5), page_path="p")


# --- dedupe ---------------------------------------------------------------------------


def _triple(subject: str, obj: str, page: str = "eval/a.md") -> Triple:
    return Triple.from_candidate(cand("x" * 20, subject=subject, object=obj), page)


def test_dedupe_on_canonical_key() -> None:
    a = _triple("Swapping Answer Order", "position  bias")
    b = _triple("swapping answer order", "Position Bias")
    c = _triple("swapping answer order", "position bias", page="eval/b.md")
    result = dedupe([a, b, c])
    assert result.kept == [a, c] and result.duplicates == [b]
    assert a.key == canonical_key(
        "swapping answer order", "mitigates", "position bias", "eval/a.md"
    )


# --- page result ----------------------------------------------------------------------


def test_page_result_status_consistency() -> None:
    PageResult(page_path="p", status="no_candidates")
    PageResult(page_path="p", status="proposed", candidates=(cand("x" * 20),))
    with pytest.raises(ValidationError, match="must say why"):
        PageResult(page_path="p", status="not_run")
    with pytest.raises(ValidationError, match="use no_candidates"):
        PageResult(page_path="p", status="proposed")
