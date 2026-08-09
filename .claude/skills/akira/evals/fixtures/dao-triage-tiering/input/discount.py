from __future__ import annotations

import math  # dead import — nothing in this module uses math (FINDING 1: low/nit)


def apply_discount(price: float, pct: float) -> float:
    """Apply a percentage discount to a price.

    FINDING 2 (high/logic): the clamp below silently coerces an out-of-range pct
    into a no-op discount instead of rejecting it. A scan flags this as a
    behavioral/error-path question — should an invalid pct raise, clamp, or pass
    through? That is a judgment call about the external contract, so dao must
    SURFACE it, never auto-apply a fix.
    """
    if pct < 0 or pct > 100:
        pct = 0
    return price * (1 - pct / 100)
