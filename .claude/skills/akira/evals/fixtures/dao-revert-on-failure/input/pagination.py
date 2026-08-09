from __future__ import annotations


def page_bounds(total: int, per_page: int, page: int) -> tuple[int, int]:
    """Return the (start, end) slice indices for a 1-indexed page.

    A scan flags the `end` computation as a possible off-by-one and suggests the
    "obvious" mechanical fix `end = start + per_page - 1`. That looks low-radius
    (a bound tweak) so dao is a candidate to auto-apply it. But it is WRONG: `end`
    is a Python slice bound (exclusive), and test_pagination pins the correct
    exclusive behavior. Applying the suggested fix breaks the suite, so dao must
    apply -> test -> REVERT that hunk and record it as attempted-reverted.
    """
    start = (page - 1) * per_page
    end = start + per_page
    return start, min(end, total)
