"""Data-contract checking — the first stage, and the only one that looks at a
frame before anything has been assumed about it.

The job is narrow on purpose: assert that the frame matches its declared
`DataContract` and say precisely how it does not. No imputation, no encoding, no
type coercion beyond checking that coercion is possible — those belong to
`transform/`, fitted inside a fold. A stage that both validates and repairs
cannot tell you whether the input was ever valid.

Failing loudly here is the point. The alternative — a missing column surfacing
as a `KeyError` sixty lines into a training run, or a silently all-null column
producing a model that scores at chance — is the failure this stage exists to
convert into one legible message.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ml.schemas import ColumnContract, DataContract


class DataContractError(ValueError):
    """Raised when a frame violates its declared contract."""


@dataclass
class ContractCheck:
    """The result of checking a frame against its contract.

    Carries every violation rather than raising on the first, so one run surfaces
    the whole problem instead of one symptom per re-run.
    """

    missing_columns: list[str] = field(default_factory=list)
    wrong_dtype: dict[str, str] = field(default_factory=dict)
    """column -> "expected X, got Y"."""
    null_violations: dict[str, str] = field(default_factory=dict)
    """column -> "N% null exceeds max M%"."""
    unexpected_columns: list[str] = field(default_factory=list)
    """Present in the frame, absent from the contract. Advisory, not a failure:
    an extra column is usually a wider extract, not a broken one."""
    row_count: int = 0
    row_count_ok: bool = True

    @property
    def ok(self) -> bool:
        """Unexpected columns deliberately do not fail the check."""
        return not (
            self.missing_columns
            or self.wrong_dtype
            or self.null_violations
            or not self.row_count_ok
        )

    def raise_if_failed(self) -> ContractCheck:
        """Raise `DataContractError` naming every violation. Returns self when
        the check passed, so it chains: `check_contract(df, c).raise_if_failed()`."""
        if self.ok:
            return self
        problems: list[str] = []
        if self.missing_columns:
            problems.append(f"missing columns: {sorted(self.missing_columns)}")
        if not self.row_count_ok:
            problems.append(f"row count {self.row_count} below the declared minimum")
        for col, detail in sorted(self.wrong_dtype.items()):
            problems.append(f"{col}: {detail}")
        for col, detail in sorted(self.null_violations.items()):
            problems.append(f"{col}: {detail}")
        raise DataContractError("; ".join(problems))


def _dtype_is_compatible(series: pd.Series, expected: str) -> bool:
    """Whether the series already is, or is losslessly coercible to, `expected`.

    Coercible-not-coerced: a numeric column read as `object` because the CSV had
    a stray space is a contract *pass* whose repair belongs to `transform/`.
    """
    if str(series.dtype) == expected:
        return True
    try:
        series.astype(expected)
    except (ValueError, TypeError):
        return False
    return True


def check_contract(frame: pd.DataFrame, contract: DataContract) -> ContractCheck:
    """Check `frame` against `contract`, collecting every violation."""
    result = ContractCheck(row_count=len(frame))
    result.row_count_ok = len(frame) >= contract.min_rows

    declared = {c.name for c in contract.columns}
    result.unexpected_columns = sorted(set(frame.columns) - declared)

    for column in contract.columns:
        if column.name not in frame.columns:
            result.missing_columns.append(column.name)
            continue
        series = frame[column.name]
        if not _dtype_is_compatible(series, column.dtype):
            result.wrong_dtype[column.name] = f"expected {column.dtype}, got {series.dtype}"
        _check_nulls(series, column, result)

    return result


def _check_nulls(series: pd.Series, column: ColumnContract, result: ContractCheck) -> None:
    """Record a null-policy violation for one column, if any."""
    null_fraction = float(series.isna().mean()) if len(series) else 0.0
    if not column.nullable and null_fraction > 0:
        result.null_violations[column.name] = (
            f"declared non-nullable but {null_fraction:.1%} of rows are null"
        )
    elif null_fraction > column.max_null_fraction:
        result.null_violations[column.name] = (
            f"{null_fraction:.1%} null exceeds the declared maximum {column.max_null_fraction:.1%}"
        )


def infer_contract(
    frame: pd.DataFrame,
    target: str | None = None,
    max_null_fraction: float = 1.0,
) -> DataContract:
    """Derive a contract from a frame you already trust — the starting point you
    then tighten by hand.

    This is a scaffold, not a validation: a contract inferred from the data can
    only ever say "the data is what it is". Its value is as an editable first
    draft, and the null policy defaults permissive so that tightening it is a
    deliberate act.
    """
    columns = tuple(
        ColumnContract(
            name=str(name),
            dtype=str(frame[name].dtype),
            nullable=bool(frame[name].isna().any()),
            max_null_fraction=max_null_fraction,
        )
        for name in frame.columns
    )
    return DataContract(columns=columns, target=target, min_rows=max(1, len(frame) // 10))
