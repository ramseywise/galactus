"""Unit tests for `frame.py` — label, survivorship drop, group key, column drops.

Toolkit-free: everything here runs in galactus's own venv with no `ML_PACKAGE_ROOT`.
Frames are hand-built minima, one concern per test.
"""

from __future__ import annotations

import pandas as pd
import pytest

from frame import (
    GROUP_COL,
    GROUP_SOURCE_COLUMNS,
    LABEL_SOURCE_COLUMNS,
    TARGET,
    load_frame,
    prepare_frame,
)


def _raw_frame(statuses: list[str]) -> pd.DataFrame:
    """A minimal extract-shaped frame: one row per status, group-key sources present."""
    n = len(statuses)
    return pd.DataFrame(
        {
            "loan_status": statuses,
            "emp_title": [f"  Engineer {i} " for i in range(n)],
            "zip_code": [f"100{i:02d}" for i in range(n)],
            "annual_inc": [50000.0 + i for i in range(n)],
            "loan_amnt": [1000.0 * (i + 1) for i in range(n)],
        }
    )


def test_label_construction_both_status_sets():
    df = prepare_frame(_raw_frame(["Charged Off", "Default", "Fully Paid"]))
    assert list(df[TARGET]) == [1, 1, 0]


def test_unresolved_rows_dropped():
    statuses = ["Charged Off", "Current", "Late (31-120 days)", "In Grace Period", "Fully Paid"]
    df = prepare_frame(_raw_frame(statuses))
    # Only the two resolved rows survive the survivorship filter.
    assert len(df) == 2
    assert list(df[TARGET]) == [1, 0]


def test_group_key_composition():
    raw = _raw_frame(["Fully Paid"])
    df = prepare_frame(raw)
    # emp_title stripped + lowercased, joined with zip and income on "|".
    assert df[GROUP_COL].iloc[0] == "engineer 0|10000|50000.0"


def test_group_key_missing_values_use_sentinels():
    raw = _raw_frame(["Fully Paid"])
    raw.loc[0, "emp_title"] = None
    raw.loc[0, "zip_code"] = None
    raw.loc[0, "annual_inc"] = None
    df = prepare_frame(raw)
    # The emp_title sentinel passes through `.str.lower()`, so it comes out "<na>" —
    # asserted as-is: the key only needs to be deterministic, not pretty.
    assert df[GROUP_COL].iloc[0] == "<na>|<NA>|-1.0"


def test_drop_list_tolerates_absent_columns():
    # The raw frame carries only one of the 40+ leakage columns; the rest being absent
    # must not raise, and the present one must go.
    raw = _raw_frame(["Charged Off", "Fully Paid"])
    raw["recoveries"] = [120.0, 0.0]
    raw["id"] = [1, 2]
    df = prepare_frame(raw)
    assert "recoveries" not in df.columns
    assert "id" not in df.columns


def test_label_and_group_sources_never_survive():
    df = prepare_frame(_raw_frame(["Charged Off", "Fully Paid"]))
    for col in LABEL_SOURCE_COLUMNS + GROUP_SOURCE_COLUMNS:
        assert col not in df.columns
    # The constructed columns are present; the untouched feature survives.
    assert TARGET in df.columns
    assert GROUP_COL in df.columns
    assert "loan_amnt" in df.columns


def test_load_frame_missing_file_exits_with_sentence(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        load_frame(tmp_path / "nope.csv")
    assert "no data at" in str(exc_info.value)
