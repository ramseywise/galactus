"""Ingest stage — the data contract.

The claim under test: a violation is reported precisely and *completely*, in one
pass. Reporting only the first problem turns one broken extract into a sequence of
re-runs, which is why `check_contract` collects rather than raises.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.ingest import DataContractError, check_contract, infer_contract
from ml.schemas import ColumnContract, DataContract


@pytest.fixture
def frame():
    return pd.DataFrame(
        {
            "age": [30.0, 40.0, 50.0, 60.0],
            "segment": ["a", "b", "a", "b"],
            "target": [0, 1, 0, 1],
        }
    )


@pytest.fixture
def contract():
    return DataContract(
        columns=(
            ColumnContract(name="age", dtype="float64", nullable=False),
            ColumnContract(name="segment", dtype="object"),
            ColumnContract(name="target", dtype="int64", nullable=False),
        ),
        target="target",
        min_rows=2,
    )


def test_a_conforming_frame_passes(frame, contract):
    check = check_contract(frame, contract)
    assert check.ok
    assert check.raise_if_failed() is check, "a passing check should chain"


def test_every_violation_is_reported_in_one_pass(frame, contract):
    """Three distinct problems, one message — not three re-runs."""
    broken = frame.drop(columns=["segment"]).copy()
    broken.loc[0, "age"] = np.nan
    broken = broken.iloc[:1]

    check = check_contract(broken, contract)

    assert not check.ok
    assert "segment" in check.missing_columns
    assert "age" in check.null_violations
    assert not check.row_count_ok

    with pytest.raises(DataContractError) as excinfo:
        check.raise_if_failed()
    message = str(excinfo.value)
    assert "segment" in message and "age" in message and "row count" in message


def test_an_unexpected_column_is_advisory_not_a_failure(frame, contract):
    """A wider extract is usually a new column upstream, not a broken feed."""
    wider = frame.assign(extra=1)

    check = check_contract(wider, contract)

    assert check.ok, "an extra column must not fail the contract"
    assert check.unexpected_columns == ["extra"]


def test_a_coercible_dtype_passes_and_repair_is_left_to_transform(contract):
    """Numbers read as strings are a contract pass, deliberately.

    Coercing here would make ingest a repair stage and destroy its ability to
    report whether the input was ever valid.
    """
    stringly = pd.DataFrame(
        {"age": ["30", "40", "50"], "segment": ["a", "b", "a"], "target": [0, 1, 0]}
    )

    check = check_contract(stringly, contract)

    assert "age" not in check.wrong_dtype
    assert check.ok


def test_a_non_coercible_dtype_fails(contract):
    unparseable = pd.DataFrame(
        {"age": ["thirty", "forty"], "segment": ["a", "b"], "target": [0, 1]}
    )

    check = check_contract(unparseable, contract)

    assert "age" in check.wrong_dtype
    assert "expected float64" in check.wrong_dtype["age"]


def test_null_fraction_gate_fires_above_its_threshold():
    contract = DataContract(
        columns=(ColumnContract(name="x", dtype="float64", max_null_fraction=0.25),)
    )
    mostly_null = pd.DataFrame({"x": [1.0, np.nan, np.nan, np.nan]})

    check = check_contract(mostly_null, contract)

    assert "x" in check.null_violations
    assert "75.0%" in check.null_violations["x"]


def test_declaring_a_target_that_is_not_a_column_is_rejected():
    """Caught by the schema itself, before any frame is involved."""
    with pytest.raises(ValueError, match="not among the declared columns"):
        DataContract(
            columns=(ColumnContract(name="x", dtype="float64"),),
            target="does_not_exist",
        )


def test_inferred_contract_round_trips(frame):
    """An inferred contract must pass against the frame it came from — it is a
    starting draft, and a draft that fails its own source is useless."""
    inferred = infer_contract(frame, target="target")

    assert check_contract(frame, inferred).ok
    assert inferred.target == "target"
    assert {c.name for c in inferred.columns} == set(frame.columns)
