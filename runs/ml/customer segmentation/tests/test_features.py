"""Feature tests — hand-computed P&L, the oversell branch, and the exclusion guarantee."""

from __future__ import annotations

import pandas as pd
from features import (
    FEATURE_COLUMNS,
    FORBIDDEN_COLUMNS,
    VALUATION_DATE,
    _fifo_realized_pnl,
    build_customer_features,
)


class TestFifoMatching:
    def _frame(self, rows):
        df = pd.DataFrame(rows, columns=["direction", "execution_size", "execution_price"])
        return df

    def test_simple_buy_then_sell(self):
        """Buy 10 @ 2.0, sell 4 @ 5.0 -> realized 4 * (5 - 2) = 12.0, 6 units open."""
        realized, open_qty, unmatched, open_cost = _fifo_realized_pnl(
            self._frame([("BUY", 10.0, 2.0), ("SELL", 4.0, 5.0)])
        )
        assert realized == 12.0
        assert open_qty == 6.0
        assert unmatched == 0.0
        assert open_cost == 12.0

    def test_fifo_order_matters(self):
        """Two lots at different costs; the *first* is consumed first.

        Buy 5 @ 1.0, buy 5 @ 3.0, sell 6 @ 4.0.
        FIFO: 5 * (4-1) + 1 * (4-3) = 15 + 1 = 16. LIFO would give 5*(4-3)+1*(4-1) = 8.
        """
        realized, open_qty, _, _ = _fifo_realized_pnl(
            self._frame([("BUY", 5.0, 1.0), ("BUY", 5.0, 3.0), ("SELL", 6.0, 4.0)])
        )
        assert realized == 16.0
        assert open_qty == 4.0

    def test_oversell_records_remainder_instead_of_going_negative(self):
        """Sell 3 with no inventory: nothing realized, 3 unmatched, no negative position.

        The two plausible wrong answers this pins down: running the position negative
        (silently manufactures profit) or dropping the trade (silently loses volume).
        """
        realized, open_qty, unmatched, _ = _fifo_realized_pnl(
            self._frame([("SELL", 3.0, 4.0)])
        )
        assert realized == 0.0
        assert open_qty == 0.0
        assert unmatched == 3.0

    def test_partial_oversell(self):
        """Buy 2 @ 1.0 then sell 5 @ 3.0 -> 2 matched (+4.0), 3 unmatched."""
        realized, open_qty, unmatched, _ = _fifo_realized_pnl(
            self._frame([("BUY", 2.0, 1.0), ("SELL", 5.0, 3.0)])
        )
        assert realized == 4.0
        assert open_qty == 0.0
        assert unmatched == 3.0


class TestBuildCustomerFeatures:
    def test_hand_computed_pnl(self, synthetic_trades, synthetic_instruments, synthetic_prices):
        f = build_customer_features(synthetic_trades, synthetic_instruments, synthetic_prices)

        # customer 1: realized 4 * (5-2) = 12. Open 6 units @ cost 2.0 = 12, marked at
        # the 2020-12-31 price of 4.0 -> 24 - 12 = +12 virtual.
        assert f.loc[1, "realized_pnl"] == 12.0
        assert f.loc[1, "virtual_pnl"] == 12.0

        # customer 2: never sold -> realized 0. Open 5 @ cost 10 = 50, marked at 12.0
        # -> 60 - 50 = +10 virtual.
        assert f.loc[2, "realized_pnl"] == 0.0
        assert f.loc[2, "virtual_pnl"] == 10.0

    def test_every_customer_survives(self, synthetic_trades, synthetic_instruments, synthetic_prices):
        f = build_customer_features(synthetic_trades, synthetic_instruments, synthetic_prices)
        assert set(f.index) == set(synthetic_trades["customer_id"])

    def test_empty_sentinel_does_not_count_as_a_sector(
        self, synthetic_trades, synthetic_instruments, synthetic_prices
    ):
        """Customer 2 trades only instrument 2, whose sector is `{""}`.

        Its `n_sectors` must be 0, not 1. If this ever reads 1, an unknown-sector
        customer has become indistinguishable from a single-sector one and the
        diversification axis is quietly dead.
        """
        f = build_customer_features(synthetic_trades, synthetic_instruments, synthetic_prices)
        assert f.loc[2, "n_sectors"] == 0
        assert f.loc[2, "sector_coverage"] == 0.0
        # Customer 1 trades instrument 1, which has a real sector.
        assert f.loc[1, "n_sectors"] == 1
        assert f.loc[1, "sector_coverage"] == 1.0

    def test_no_forbidden_column_is_a_feature(self):
        """The exclusion is a property of the constant, asserted rather than assumed."""
        assert not set(FEATURE_COLUMNS) & set(FORBIDDEN_COLUMNS)

    def test_output_columns_are_exactly_the_declared_set(
        self, synthetic_trades, synthetic_instruments, synthetic_prices
    ):
        f = build_customer_features(synthetic_trades, synthetic_instruments, synthetic_prices)
        assert tuple(f.columns) == FEATURE_COLUMNS

    def test_valuation_date_is_year_end(self):
        assert pd.Timestamp("2020-12-31") == VALUATION_DATE
