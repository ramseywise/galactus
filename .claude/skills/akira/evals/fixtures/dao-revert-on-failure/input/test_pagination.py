from __future__ import annotations

from pagination import page_bounds


def test_first_page_slices_correctly():
    # 10 items, 3 per page, page 1 -> items[0:3]. end is EXCLUSIVE.
    items = list(range(10))
    start, end = page_bounds(10, 3, 1)
    assert (start, end) == (0, 3)
    assert items[start:end] == [0, 1, 2]


def test_last_page_clamped_to_total():
    items = list(range(10))
    start, end = page_bounds(10, 3, 4)  # page 4 -> items[9:10]
    assert (start, end) == (9, 10)
    assert items[start:end] == [9]
