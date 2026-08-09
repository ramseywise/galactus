from __future__ import annotations

from discount import apply_discount


def test_half_off():
    assert apply_discount(100.0, 50.0) == 50.0


def test_no_discount():
    assert apply_discount(100.0, 0.0) == 100.0


def test_out_of_range_is_noop():
    # Locks in the CURRENT (arguably wrong) behavior: >100 clamps to 0% off.
    # This is why the pct-clamp finding is high-radius: "fixing" it changes
    # this contract, so dao must surface it rather than auto-apply.
    assert apply_discount(100.0, 150.0) == 100.0
