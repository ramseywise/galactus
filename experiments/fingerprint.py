"""Derived-frame hashing — the load-bearing piece of the acceptance test.

`fingerprint_frame(df)` identifies the frame **as fitted**, after every
derivation drop, not the source file it came from. A hash of the source CSV
would have been byte-identical across both Step 15 runs — the baseline
diverged downstream of the file, in a drop pipeline that removed a column
between one run and the next — and so a source hash would have caught
nothing. The digest below covers the matrix that was actually fitted.

Nothing returned here can carry a row, an index, or a value: only a digest,
counts, and column *names*. `reporting/html.py` already establishes column
names as safe to record ("Metrics, counts, and column names are the whole
vocabulary") — this module holds to the same line.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from experiments.record import DataIdentity


def _column_digest_input(df: pd.DataFrame) -> bytes:
    """Bytes that determine the hash: dtypes, column order, and content —
    never a value rendered into a report or log, only fed to a digest."""
    parts: list[bytes] = []
    for column in df.columns:
        series = df[column]
        parts.append(str(column).encode("utf-8"))
        parts.append(str(series.dtype).encode("utf-8"))
        # pandas' own hashing is vectorised and dtype-aware; combining it into
        # one order-stable digest is far cheaper than a python-level content
        # hash and still sensitive to every value, dtype, and row order.
        parts.append(
            hashlib.sha256(
                pd.util.hash_pandas_object(series, index=False).to_numpy().tobytes()
            ).digest()
        )
    return b"|".join(parts)


def fingerprint_frame(df: pd.DataFrame) -> DataIdentity:
    """Identify the frame as fitted, after derivation drops.

    A hash of the SOURCE file would have been byte-identical across both
    Step 15 runs and caught nothing — the baseline diverged downstream of
    the file, in derivation. So the digest covers this matrix, not its
    origin.

    Returns a digest, counts, and column names. Never a row, index, or
    value. Order-stable (row order and column order both feed the digest,
    since reordering either is itself a derivation change) and
    dtype-sensitive (a column cast from int to float changes the hash even
    if the printed values look the same).
    """
    digest = hashlib.sha256(_column_digest_input(df)).hexdigest()
    return DataIdentity(
        frame_hash=digest,
        n_rows=len(df),
        n_cols=len(df.columns),
        columns=tuple(str(c) for c in df.columns),
    )


def validate_class_balance(class_balance: dict[object, float]) -> None:
    """Reject a `class_balance` mapping whose keys are not primitive scalars.

    The F5 edge case: `class_balance: dict[Any, float]` is safe when its
    keys are ordinary class labels (0/1, "approved"/"denied"), but a
    multiclass target whose labels are themselves identifiers would leak
    through the keys even though every value is an aggregate proportion.
    Enforced here, at write time, rather than left as a documentation-only
    constraint — the constraint needs to be checked where it can fail.
    """
    allowed_key_types = (str, int, bool, float)
    for key in class_balance:
        if not isinstance(key, allowed_key_types):
            raise ValueError(
                f"class_balance key {key!r} (type {type(key).__name__}) is not "
                "a primitive scalar. Aggregates only: a class_balance key must "
                "be a class label (str/int/bool/float), never an object that "
                "could itself be or contain an identifier."
            )
