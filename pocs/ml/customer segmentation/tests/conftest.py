"""Path shim and synthetic fixtures for the segmentation POC.

No real row enters a test file — every fixture here is hand-written, in the spirit of
`pocs/ml/fraud/tests/conftest.py`. The real 1.1M-row frame is exercised only by
`src/run.py`, which is an integration concern, not a unit-test one.

The `sys.path` insert follows the fraud POC: nothing installs this POC into the venv, so
`from load import ...` needs `src/` on the path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def synthetic_trades() -> pd.DataFrame:
    """Three customers with hand-computable P&L.

    - customer 1: buys 10 @ 2.0, sells 4 @ 5.0  -> realized +12.0, 6 units open
    - customer 2: buys 5 @ 10.0, never sells    -> realized 0.0, 5 units open
    - customer 3: sells 3 @ 4.0 with no buy     -> the oversell branch
    """
    rows = [
        (1, "2020-01-02 10:00:00", "BUY", 10.0, 2.0, 1),
        (1, "2020-03-05 11:00:00", "SELL", 4.0, 5.0, 1),
        (2, "2020-02-10 09:00:00", "BUY", 5.0, 10.0, 2),
        (3, "2020-04-01 15:00:00", "SELL", 3.0, 4.0, 1),
    ]
    df = pd.DataFrame(
        rows,
        columns=[
            "customer_id",
            "execution_time",
            "direction",
            "execution_size",
            "execution_price",
            "instrument_id",
        ],
    )
    df["execution_time"] = pd.to_datetime(df["execution_time"])
    df["volume"] = df["execution_size"] * df["execution_price"]
    return df


@pytest.fixture
def synthetic_instruments() -> pd.DataFrame:
    """Two catalogued instruments: one with a real sector, one with the empty sentinel."""
    from load import parse_brace_array

    df = pd.DataFrame(
        [
            (1, '{Software}', '{USA}', '{SP500}', "STOCK"),
            (2, '{""}', '{""}', '{""}', "DERIVATIVE"),
        ],
        columns=[
            "instrument_id",
            "sector_name",
            "country_name",
            "index_name",
            "instrument_type",
        ],
    )
    for raw_col, parsed_col in (
        ("sector_name", "sectors"),
        ("country_name", "countries"),
        ("index_name", "indices"),
    ):
        df[parsed_col] = df[raw_col].map(parse_brace_array)
    return df


@pytest.fixture
def synthetic_prices() -> pd.DataFrame:
    """Year-end prices for both instruments, plus an earlier date to make it a panel."""
    rows = [
        ("2020-06-30", 3.0, 1),
        ("2020-12-31", 4.0, 1),
        ("2020-06-30", 11.0, 2),
        ("2020-12-31", 12.0, 2),
    ]
    df = pd.DataFrame(rows, columns=["date", "price", "instrument_id"])
    df["date"] = pd.to_datetime(df["date"])
    return df
