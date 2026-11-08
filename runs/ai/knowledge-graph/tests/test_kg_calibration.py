from __future__ import annotations

import pytest

from kg.judge.calibration import (
    Confusion,
    Kappa,
    Obs,
    Rate,
    calibrate,
    cohens_kappa,
    confusion,
    expected_calibration_error,
    hard_negative_precision,
    tnr,
    tpr,
    wilson,
)
from kg.judge.calibration import (
    test_retest as retest,
)
from kg.models import NotApplicable


def _obs(
    gold: str, label: str | None, score: float | None = None, i: int = 0, split: str = "test"
) -> Obs:
    return Obs(id=f"{gold}-{i}", gold=gold, split=split, label=label, score=score)  # type: ignore[arg-type]


def test_kappa_matches_hand_computation() -> None:
    # tp=45 fn=15 fp=15 tn=25, n=100.
    # p_o = (45+25)/100 = 0.70
    # actual positive 60, negative 40; predicted positive 60, negative 40
    # p_e = (60*60 + 40*40)/100^2 = (3600+1600)/10000 = 0.52
    # kappa = (0.70 - 0.52) / (1 - 0.52) = 0.18 / 0.48 = 0.375
    k = cohens_kappa(Confusion(tp=45, fn=15, fp=15, tn=25))
    assert isinstance(k, Kappa)
    assert round(k.value, 4) == 0.3750
    assert k.n == 100
    # Wilson on p_o=0.70, n=100: centre 0.692592, half 0.088459 -> [0.60413, 0.78105];
    # mapped by (p - 0.52)/0.48.
    assert k.lo == pytest.approx((0.604133 - 0.52) / 0.48, abs=1e-4)
    assert k.hi == pytest.approx((0.781051 - 0.52) / 0.48, abs=1e-4)
    assert k.lo < k.value < k.hi


def test_wilson_known_value() -> None:
    lo, hi = wilson(70, 100)  # type: ignore[misc]
    assert (round(lo, 4), round(hi, 4)) == (0.6041, 0.7811)


def test_tpr_and_tnr_are_separate() -> None:
    c = confusion(
        [_obs("positive", "supported", i=i) for i in range(3)]
        + [_obs("positive", "not_supported", i=3)]
        + [_obs("hard_negative", "not_supported", i=i) for i in range(1)]
        + [_obs("control", "supported", i=0)]
    )
    assert tpr(c) == Rate(0.75, 4)
    assert tnr(c) == Rate(0.5, 2)


def test_unclear_is_not_accepted_and_not_run_is_excluded() -> None:
    c = confusion(
        [_obs("positive", "unclear"), _obs("hard_negative", None), _obs("control", "unclear")]
    )
    assert (c.tp, c.fn, c.fp, c.tn, c.not_run) == (0, 1, 0, 1, 1)


def test_zero_denominators_are_not_applicable() -> None:
    only_pos = confusion([_obs("positive", "supported")])
    assert isinstance(tnr(only_pos), NotApplicable)
    assert isinstance(tpr(confusion([])), NotApplicable)
    assert isinstance(cohens_kappa(confusion([])), NotApplicable)
    assert isinstance(cohens_kappa(only_pos), NotApplicable)  # single class: p_e = 1
    assert isinstance(expected_calibration_error([], []), NotApplicable)
    assert isinstance(retest([[_obs("positive", "supported")]]), NotApplicable)
    assert isinstance(hard_negative_precision([_obs("positive", "not_supported")]), NotApplicable)


def test_ece_ten_bins() -> None:
    # bin 9 holds 0.9, 0.95, 1.0: mean score .95, accuracy 2/3 -> gap .2833 * 3/4
    # bin 1 holds 0.1: score .1, accuracy 0 -> gap .1 * 1/4
    ece = expected_calibration_error([0.9, 0.95, 1.0, 0.1], [True, True, False, False])
    assert isinstance(ece, Rate) and ece.n == 4
    assert ece.value == pytest.approx(0.75 * (0.95 - 2 / 3) + 0.25 * 0.1)
    with pytest.raises(ValueError):
        expected_calibration_error([1.5], [True])


def test_retest_pairwise_agreement() -> None:
    r1 = [_obs("positive", "supported", i=1), _obs("positive", "supported", i=2)]
    r2 = [_obs("positive", "supported", i=1), _obs("positive", "not_supported", i=2)]
    r3 = [_obs("positive", "supported", i=1), _obs("positive", "not_supported", i=2)]
    out = retest([r1, r2, r3])
    # item 1: 3/3 pairs agree; item 2: pairs (1,2)x (1,3)x (2,3)ok -> 1/3
    assert out == Rate((1.0 + 1 / 3) / 2, 2)


def test_hard_negative_precision_is_separate_from_controls() -> None:
    obs = [
        _obs("positive", "supported", i=1),
        _obs("hard_negative", "supported", i=1),
        _obs("control", "supported", i=1),  # excluded from hard-negative precision
    ]
    assert hard_negative_precision(obs) == Rate(0.5, 2)


def test_calibrate_uses_test_split_only_and_first_repeat() -> None:
    train = _obs("positive", "not_supported", i=9, split="train")
    rep = [
        _obs("positive", "supported", 0.9, 1),
        _obs("hard_negative", "not_supported", 0.2, 1),
        train,
    ]
    out = calibrate({"scripted": [rep, rep]})["scripted"]
    assert out.n_test == 2
    assert out.tpr == Rate(1.0, 1) and out.tnr == Rate(1.0, 1)
    assert out.retest == Rate(1.0, 2)
    assert out.hard_negative_tnr == Rate(1.0, 1)
    assert isinstance(out.control_tnr, NotApplicable)
