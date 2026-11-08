from __future__ import annotations

import json
from pathlib import Path

import pytest
from kg_store_helpers import put

from kg.models import NotApplicable, Usage, Verdict
from kg.route import (
    BuildHalted,
    Prices,
    apply_decisions,
    assign,
    band_rate,
    floor_point,
    halt_if_over,
    render_table,
    risk_coverage,
    thresholds,
)
from kg.route.review_queue import review_rows
from kg.store import SqliteStore

# The course note's worked example: pay a problem 150, reject a good one 30, review 3,
# catch 0.9, false alarm 0.02. Note thresholds are on P(problem): pay < 0.027, reject > 0.595.
COURSE = Prices(wrong_accept=150, wrong_reject=30, review=3, reviewer_tpr=0.9, reviewer_fpr=0.02)


def _v(label: str, score: float) -> Verdict:
    return Verdict(label=label, score=score, usage=Usage(model="fake"))  # type: ignore[arg-type]


def test_course_worked_example_thresholds() -> None:
    t_lo, t_hi = thresholds(COURSE)
    assert 1 - t_hi == pytest.approx(0.027, abs=5e-4)  # pay threshold on P(problem)
    assert 1 - t_lo == pytest.approx(0.595, abs=5e-4)  # reject threshold on P(problem)


def test_course_perfect_clerk_and_hand_check() -> None:
    perfect = Prices(150, 30, 3, reviewer_tpr=1.0, reviewer_fpr=0.0)
    t_lo, t_hi = thresholds(perfect)
    assert (1 - t_hi, 1 - t_lo) == pytest.approx((0.020, 0.900))
    hand = Prices(150, 30, 10, reviewer_tpr=0.75, reviewer_fpr=0.02)  # answer 1 in the note
    t_lo, t_hi = thresholds(hand)
    assert (1 - t_hi, 1 - t_lo) == pytest.approx((0.094, 0.290), abs=5e-4)


@pytest.mark.parametrize("a", [2, 10, 50, 150])
@pytest.mark.parametrize("r", [1, 3, 30])
@pytest.mark.parametrize("h", [0.1, 0.5, 1, 3])
@pytest.mark.parametrize("tpr,fpr", [(0.95, 0.05), (0.9, 0.02), (0.75, 0.1), (1.0, 0.0)])
def test_thresholds_ordered_for_every_positive_price_set(
    a: float, r: float, h: float, tpr: float, fpr: float
) -> None:
    t_lo, t_hi = thresholds(Prices(a, r, h, tpr, fpr))
    assert 0 <= t_lo <= t_hi <= 1 or t_lo == t_hi
    keep = r * (1 - fpr)
    band_exists = (h + fpr * r) / (tpr * a + fpr * r) < (keep - h) / ((1 - tpr) * a + keep)
    assert (t_lo < t_hi) == band_exists


def test_cheap_review_always_has_a_band() -> None:
    for a in (2, 10, 150):
        t_lo, t_hi = thresholds(Prices(a, 3, 0.1, 0.95, 0.05))
        assert t_lo < t_hi


def test_defaults_have_a_band() -> None:
    t_lo, t_hi = thresholds(Prices())
    assert t_lo < t_hi


def test_expensive_review_falls_back_to_one_threshold() -> None:
    t_lo, t_hi = thresholds(Prices(10, 1, 1))
    assert t_lo == t_hi


def test_prices_reject_nonpositive() -> None:
    with pytest.raises(ValueError):
        Prices(wrong_accept=0)
    with pytest.raises(ValueError):
        Prices(reviewer_tpr=0.04, reviewer_fpr=0.05)


def test_unclear_review_regardless_of_score() -> None:
    assert assign(_v("unclear", 0.99), 0.3, 0.8) == "review"
    assert assign(_v("unclear", 0.0), 0.3, 0.8) == "review"


def test_assign_by_score_and_contradiction() -> None:
    assert assign(_v("supported", 0.9), 0.3, 0.8) == "accept"
    assert assign(_v("not_supported", 0.1), 0.3, 0.8) == "reject"
    assert assign(_v("supported", 0.5), 0.3, 0.8) == "review"
    assert assign(_v("not_supported", 0.99), 0.3, 0.8) == "review"
    assert assign(_v("supported", 0.05), 0.3, 0.8) == "review"


def test_floor_point_smallest_band_hits_floor() -> None:
    scores = [0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
    labels = [True, True, True, True, False, True, False, True, False, False, False, False]
    fp = floor_point(scores, labels, precision=0.90)
    assert not isinstance(fp, NotApplicable)
    assert fp.accept_precision >= 0.90
    assert fp.t_hi == 0.8  # 0.7 would admit a wrong accept: 4/5 < 0.9
    assert fp.t_lo == 0.4  # rejects {0.3 .. 0.05}: all five unsupported
    assert fp.t_lo <= fp.t_hi
    assert fp.band_rate == pytest.approx(4 / 12)
    # smallest: no lower t_hi reaches the floor
    for cut in (0.7, 0.6, 0.5, 0.4):
        acc = [lab for s, lab in zip(scores, labels, strict=True) if s >= cut]
        assert sum(acc) / len(acc) < 0.90


def test_floor_point_unreachable_is_not_applicable() -> None:
    assert isinstance(floor_point([0.9, 0.8], [False, False]), NotApplicable)
    assert isinstance(floor_point([], []), NotApplicable)


def test_risk_coverage_monotone_in_coverage() -> None:
    scores = [0.9, 0.9, 0.8, 0.6, 0.5, 0.3, 0.2]
    labels = [True, True, False, True, False, False, True]
    curve = risk_coverage(scores, labels)
    covs = [c for c, _ in curve]
    assert covs == sorted(covs) and len(set(covs)) == len(covs)
    assert covs[-1] == 1.0
    assert curve[0] == (2 / 7, 0.0)
    assert all(0 <= risk <= 1 for _, risk in curve)


def test_band_rate_empty_is_not_applicable() -> None:
    r = band_rate([])
    assert isinstance(r, NotApplicable)
    assert r.reason == "no judged candidates"
    assert band_rate(["review", "accept", "reject", "accept"]) == 0.25


def test_halt_if_over() -> None:
    with pytest.raises(BuildHalted):
        halt_if_over(0.41)
    halt_if_over(0.40)
    halt_if_over(NotApplicable("no judged candidates"))
    with pytest.raises(BuildHalted):
        halt_if_over(0.3, limit=0.2)


def test_review_queue_render_and_apply(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "kg.db")
    store.open_build("b1", "pack0", "p0")
    t1 = put(store, "b1", "A", "beats", "B", tier="review", score=0.5)
    t2 = put(store, "b1", "C", "beats", "D", tier="review", score=0.4)
    put(store, "b1", "E", "beats", "F", tier="accept")
    rows = review_rows(store, "b1")
    table = render_table(rows)
    assert table.splitlines()[1].startswith("0.40")
    assert render_table([]) == "review queue empty"

    path = tmp_path / "d.jsonl"
    path.write_text(
        json.dumps({"key": list(t1.key), "decision": "accept"})
        + "\n"
        + json.dumps({"key": list(t2.key), "decision": "reject"})
        + "\n"
    )
    assert apply_decisions(store, "b1", path) == 2
    tiers = {st.triple.key: st.tier for st in store.triples("b1")}
    assert tiers[t1.key] == "accept" and tiers[t2.key] == "reject"
    assert review_rows(store, "b1") == []


def test_apply_decisions_unknown_key_writes_nothing(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "kg.db")
    store.open_build("b1", "pack0", "p0")
    t1 = put(store, "b1", "A", "beats", "B", tier="review")
    path = tmp_path / "d.jsonl"
    path.write_text(
        json.dumps({"key": list(t1.key), "decision": "accept"})
        + "\n"
        + json.dumps({"key": ["x", "y", "z", "w"], "decision": "reject"})
        + "\n"
    )
    with pytest.raises(ValueError):
        apply_decisions(store, "b1", path)
    assert [st.tier for st in store.triples("b1")] == ["review"]
