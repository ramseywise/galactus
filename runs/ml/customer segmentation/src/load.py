"""Loading and cleaning the three raw frames.

Every date parse here declares an explicit `format=`, and the two files need *different*
ones. That is not defensive style, it is two measured hazards:

- `trades.csv` stores `2020-01-02 20:00:00`. Letting pandas infer it produced an `object`
  dtype with no error at all; the failure only surfaced later, as an `AttributeError` on
  a `.dt` accessor.
- `prices.csv` stores `12/10/20`, which is valid under both `%d/%m/%y` and `%m/%d/%y`.
  Inference picks one and applies it to the whole column silently, because both readings
  parse. Measured over the real file, the first component reaches 31 and the second never
  exceeds 12, so the panel is **day-first**. Had inference guessed month-first, the price
  panel would be scrambled by month with no NaT and no warning, and every `virtual_pnl`
  over an open position would be wrong-but-plausible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TRADE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
PRICE_DATE_FORMAT = "%d/%m/%y"

#: The catalog's empty sentinel. Not NULL and not absent — a present string that parses
#: and joins like any other value, which is exactly what makes it dangerous: it reads as
#: "one sector" to `nunique`.
EMPTY_SENTINEL = '{""}'


@dataclass(frozen=True)
class LoadReport:
    """What loading discarded, so a caller can assert on it instead of trusting it."""

    rows_in: int
    rows_out: int
    dropped_unparseable_time: int


def parse_brace_array(raw: object) -> tuple[str, ...]:
    """Parse the catalog's brace-wrapped array literal into its elements.

    `{Software}` -> `("Software",)`
    `{Computer,"Elektronik & Haushalt"}` -> `("Computer", "Elektronik & Haushalt")`
    `{""}` -> `()` — the empty sentinel is *no* elements, distinct from one unnamed one.

    Returning `()` rather than `("",)` is the whole point: it lets a caller distinguish
    "this instrument has no catalogued sector" from "this instrument has one sector",
    which a naive `nunique` over the raw strings cannot do.
    """
    if not isinstance(raw, str) or not raw.startswith("{") or not raw.endswith("}"):
        return ()
    inner = raw[1:-1]
    if not inner:
        return ()
    # Split on commas that are not inside double quotes, then unquote.
    parts = re.findall(r'"[^"]*"|[^,]+', inner)
    out = [p.strip().strip('"').strip() for p in parts]
    return tuple(p for p in out if p)


def load_trades(path: str | Path) -> tuple[pd.DataFrame, LoadReport]:
    """Load executed trades, dropping rows whose timestamp will not parse.

    The drop is *counted* and returned rather than swallowed: one malformed row in the
    real file is expected, and a test asserts that number. A loader that silently drops a
    growing number of rows is indistinguishable from one that drops one.
    """
    df = pd.read_csv(path, index_col=0)
    rows_in = len(df)
    df["execution_time"] = pd.to_datetime(
        df["execution_time"], format=TRADE_TIME_FORMAT, errors="coerce"
    )
    unparseable = int(df["execution_time"].isna().sum())
    df = df[df["execution_time"].notna()].copy()
    df["volume"] = df["execution_size"] * df["execution_price"]
    return df, LoadReport(rows_in, len(df), unparseable)


def load_instruments(path: str | Path) -> pd.DataFrame:
    """Load the instrument catalog with its array fields parsed.

    Adds `sectors` / `countries` / `indices` as tuples and `n_*` counts beside them. The
    raw string columns are kept so a caller can see the sentinel for what it is.
    """
    df = pd.read_csv(path)
    for raw_col, parsed_col in (
        ("sector_name", "sectors"),
        ("country_name", "countries"),
        ("index_name", "indices"),
    ):
        df[parsed_col] = df[raw_col].map(parse_brace_array)
    return df


def load_prices(path: str | Path) -> pd.DataFrame:
    """Load the end-of-day price panel. See the module docstring on the date format."""
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], format=PRICE_DATE_FORMAT, errors="coerce")
    return df
