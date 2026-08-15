"""Loader tests — the brace parser and the two date formats."""

from __future__ import annotations

import pandas as pd
import pytest
from load import EMPTY_SENTINEL, PRICE_DATE_FORMAT, TRADE_TIME_FORMAT, parse_brace_array


class TestParseBraceArray:
    def test_single_value(self):
        assert parse_brace_array("{Software}") == ("Software",)

    def test_multi_value_with_quoted_element(self):
        got = parse_brace_array('{Computer,"Elektronik & Haushalt","Large Caps"}')
        assert got == ("Computer", "Elektronik & Haushalt", "Large Caps")

    def test_empty_sentinel_is_no_elements_not_one(self):
        """The finding this whole parser exists for.

        `{""}` must be zero elements. If it came back as `("",)` then `len()` would be 1
        and an unknown-sector instrument would be indistinguishable from a genuine
        single-sector one — which is how the diversification axis silently dies.
        """
        assert parse_brace_array(EMPTY_SENTINEL) == ()
        assert len(parse_brace_array(EMPTY_SENTINEL)) == 0

    def test_non_string_and_malformed_are_empty(self):
        assert parse_brace_array(None) == ()
        assert parse_brace_array(float("nan")) == ()
        assert parse_brace_array("Software") == ()


class TestDateFormats:
    def test_trade_format_parses_the_real_shape(self):
        got = pd.to_datetime("2020-01-02 20:00:00", format=TRADE_TIME_FORMAT)
        assert (got.year, got.month, got.day) == (2020, 1, 2)

    def test_price_format_is_day_first(self):
        """`12/10/20` is 12 October, not 10 December.

        Measured over the real panel: the first component reaches 31, the second never
        exceeds 12. If this assertion ever flips, every open-position valuation moves by
        up to a month and nothing else in the pipeline would notice.
        """
        got = pd.to_datetime("12/10/20", format=PRICE_DATE_FORMAT)
        assert (got.year, got.month, got.day) == (2020, 10, 12)

    def test_day_first_and_month_first_disagree_silently(self):
        """Both readings parse, which is why inference cannot be trusted here."""
        day_first = pd.to_datetime("12/10/20", format="%d/%m/%y")
        month_first = pd.to_datetime("12/10/20", format="%m/%d/%y")
        assert day_first != month_first
        assert pd.notna(day_first) and pd.notna(month_first)


class TestSyntheticFixtures:
    def test_instruments_fixture_carries_both_states(self, synthetic_instruments):
        by_id = synthetic_instruments.set_index("instrument_id")
        assert by_id.loc[1, "sectors"] == ("Software",)
        assert by_id.loc[2, "sectors"] == ()

    def test_prices_fixture_has_year_end_for_every_instrument(self, synthetic_prices):
        year_end = synthetic_prices[synthetic_prices["date"] == pd.Timestamp("2020-12-31")]
        assert set(year_end["instrument_id"]) == {1, 2}

    @pytest.mark.parametrize("customer,expected_trades", [(1, 2), (2, 1), (3, 1)])
    def test_trades_fixture_shape(self, synthetic_trades, customer, expected_trades):
        assert len(synthetic_trades[synthetic_trades["customer_id"] == customer]) == expected_trades
