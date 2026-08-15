"""Per-customer feature matrix, one row per customer.

Two things here are deliberate and were not obvious:

**`cohort` and every first-trade-derived label are excluded by construction.** `cohort` in
the supplied `final_df.csv` is *exactly* the customer's first-trade month — verified as a
perfect 6x6 diagonal, zero off-diagonal. A model that clusters on it segments customers by
signup date and calls the result behaviour. `FORBIDDEN_COLUMNS` names the family and
`check_leakage` (see `prepare.py`) fails on any of them reaching the matrix.

`tenure_days` is included even though it derives from the first trade *date*. It is a
duration — how long the customer has been active — not a restatement of which month they
joined; two customers who joined in different months can have identical tenure. The
distinction is the reason the constant is a list of names rather than a rule about
provenance.

**The sector/country fields are arrays with an empty sentinel.** 81% of catalogued
instruments carry `{""}` for sector and 85% for country. Counting distinct raw strings
would give an unknown-sector customer `n_sectors == 1`, identical to a genuine
single-sector trader, and the diversification axis the brief names would collapse to a
near-constant and drop out of the distance metric with nothing raising. So the parsed
tuples are counted instead, and `sector_coverage` reports how much of a customer's volume
was in instruments that have a sector at all — which is what makes "diversified" and
"unknown" separable downstream.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Open positions are valued here. One date for every customer, so the valuation is not a
#: function of how recently they happened to trade. Switching it is a one-line change.
VALUATION_DATE = pd.Timestamp("2020-12-31")

FEATURE_COLUMNS: tuple[str, ...] = (
    # Activity
    "n_trades",
    "total_volume",
    "mean_trade_size",
    "active_months",
    # Performance
    "realized_pnl",
    "virtual_pnl",
    # Diversification
    "n_instruments",
    "n_sectors",
    "n_countries",
    "sector_coverage",
    "share_derivative",
    "share_etf",
    "share_stock",
    # Timing
    "days_since_last_trade",
    "mean_days_between_trades",
    "tenure_days",
)

#: Excluded by construction — see the module docstring. `check_leakage` rule (a) fails on
#: any of these appearing in a feature matrix.
FORBIDDEN_COLUMNS: tuple[str, ...] = (
    "cohort",
    "first_trade_month",
    "first_trade_date",
    "group_label",
)


def _fifo_realized_pnl(group: pd.DataFrame) -> tuple[float, float, float, float]:
    """FIFO-match SELLs against prior BUYs for one customer.

    Returns `(realized_pnl, open_quantity, unmatched_sell_qty, open_cost)`.

    The oversell branch is explicit rather than incidental: a SELL larger than the
    accumulated BUY quantity (a short, or a data artifact) matches what inventory exists
    and records the remainder in `unmatched_sell_qty`. Letting it run negative would
    silently manufacture profit; dropping the trade would silently lose volume. Both are
    plausible-looking wrong answers, which is why this returns the count instead.
    """
    lots: list[list[float]] = []  # [quantity, unit_cost], oldest first
    realized = 0.0
    unmatched = 0.0

    for _, row in group.iterrows():
        qty = float(row["execution_size"])
        price = float(row["execution_price"])
        if row["direction"] == "BUY":
            lots.append([qty, price])
            continue

        remaining = qty
        while remaining > 0 and lots:
            lot = lots[0]
            take = min(lot[0], remaining)
            realized += take * (price - lot[1])
            lot[0] -= take
            remaining -= take
            if lot[0] <= 0:
                lots.pop(0)
        if remaining > 0:
            unmatched += remaining

    open_qty = sum(q for q, _ in lots)
    open_cost = sum(q * c for q, c in lots)
    return realized, open_qty, unmatched, open_cost


def _open_position_value(
    trades: pd.DataFrame, prices: pd.DataFrame
) -> pd.DataFrame:
    """Per (customer, instrument) open quantity and its value at `VALUATION_DATE`."""
    eod = (
        prices[prices["date"] <= VALUATION_DATE]
        .sort_values("date")
        .groupby("instrument_id")
        .last()["price"]
    )

    records = []
    for (cust, inst), grp in trades.groupby(["customer_id", "instrument_id"], sort=False):
        grp = grp.sort_values("execution_time")
        realized, open_qty, unmatched, open_cost = _fifo_realized_pnl(grp)
        mark = eod.get(inst, np.nan)
        # An instrument absent from the catalog (or from the panel) leaves the position
        # unmarked rather than valued at zero — zero is a claim, NaN is the absence of one.
        virtual = (open_qty * mark - open_cost) if pd.notna(mark) else np.nan
        records.append(
            {
                "customer_id": cust,
                "instrument_id": inst,
                "realized_pnl": realized,
                "virtual_pnl": virtual,
                "unmatched_sell_qty": unmatched,
            }
        )
    return pd.DataFrame.from_records(records)


def build_customer_features(
    trades: pd.DataFrame, instruments: pd.DataFrame, prices: pd.DataFrame
) -> pd.DataFrame:
    """Build the per-customer matrix. Index is `customer_id`; columns are FEATURE_COLUMNS.

    Every customer present in `trades` appears in the output — a customer whose features
    are all-zero is a finding, not a reason to drop the row.
    """
    t = trades.sort_values("execution_time")
    cat = instruments.set_index("instrument_id")

    # Per-instrument attributes, joined so an orphan instrument survives as "unknown"
    # rather than dropping the trade. `n_sectors` counts *parsed elements*, so the empty
    # sentinel contributes nothing — see the module docstring.
    sectors = cat["sectors"] if "sectors" in cat else pd.Series(dtype=object)
    countries = cat["countries"] if "countries" in cat else pd.Series(dtype=object)
    t = t.join(cat[["instrument_type"]], on="instrument_id")
    t["_sectors"] = t["instrument_id"].map(sectors)
    t["_countries"] = t["instrument_id"].map(countries)

    grouped = t.groupby("customer_id")

    out = pd.DataFrame(index=grouped.size().index.rename("customer_id"))
    out["n_trades"] = grouped.size()
    out["total_volume"] = grouped["volume"].sum()
    out["mean_trade_size"] = grouped["volume"].mean()
    out["active_months"] = grouped["execution_time"].apply(
        lambda s: s.dt.to_period("M").nunique()
    )
    out["n_instruments"] = grouped["instrument_id"].nunique()

    def _distinct(series: pd.Series) -> int:
        seen: set[str] = set()
        for value in series:
            if isinstance(value, tuple):
                seen.update(value)
        return len(seen)

    out["n_sectors"] = grouped["_sectors"].apply(_distinct)
    out["n_countries"] = grouped["_countries"].apply(_distinct)

    # How much of the customer's volume sits in instruments that have a sector at all.
    # This is what separates "trades one sector" from "sector unknown".
    t["_has_sector"] = t["_sectors"].map(lambda v: bool(v) if isinstance(v, tuple) else False)
    covered = t[t["_has_sector"]].groupby("customer_id")["volume"].sum()
    out["sector_coverage"] = (covered / out["total_volume"]).fillna(0.0)

    for label, kind in (("share_derivative", "DERIVATIVE"), ("share_etf", "ETF"), ("share_stock", "STOCK")):
        vol = t[t["instrument_type"] == kind].groupby("customer_id")["volume"].sum()
        out[label] = (vol / out["total_volume"]).fillna(0.0)

    pnl = _open_position_value(t, prices)
    agg = pnl.groupby("customer_id").agg(
        realized_pnl=("realized_pnl", "sum"),
        virtual_pnl=("virtual_pnl", "sum"),
        unmatched_sell_qty=("unmatched_sell_qty", "sum"),
    )
    out = out.join(agg)

    last = grouped["execution_time"].max()
    first = grouped["execution_time"].min()
    out["days_since_last_trade"] = (VALUATION_DATE - last).dt.days
    out["tenure_days"] = (last - first).dt.days
    out["mean_days_between_trades"] = np.where(
        out["n_trades"] > 1, out["tenure_days"] / (out["n_trades"] - 1), 0.0
    )

    return out[list(FEATURE_COLUMNS)].fillna(0.0)
