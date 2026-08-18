"""Step 3 — derived-frame hashing, the acceptance test's load-bearing piece.

The claim under test: "which frame was the baseline scored on" is answerable
because the hash covers the frame AS FITTED. A dropped column (the Step 15
case), a column reorder, or a dtype change must all change the hash; the same
frame must hash identically across process boundaries, not just within one
Python session's hash-seed; and nothing returned can carry a cell value.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from experiments.fingerprint import fingerprint_frame, validate_class_balance
from experiments.record import DataIdentity


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0], "c": ["x", "y", "z"]})


def test_dropped_column_changes_hash() -> None:
    full = _frame()
    dropped = full.drop(columns=["c"])

    full_identity = fingerprint_frame(full)
    dropped_identity = fingerprint_frame(dropped)

    assert full_identity.frame_hash != dropped_identity.frame_hash


def test_reordering_columns_changes_hash() -> None:
    original = _frame()
    reordered = original[["b", "a", "c"]]

    original_identity = fingerprint_frame(original)
    reordered_identity = fingerprint_frame(reordered)

    assert original_identity.frame_hash != reordered_identity.frame_hash


def test_same_frame_hashes_identically_across_processes() -> None:
    script = textwrap.dedent(
        """
        import pandas as pd
        from experiments.fingerprint import fingerprint_frame

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0], "c": ["x", "y", "z"]})
        print(fingerprint_frame(df).frame_hash)
        """
    )
    # pytest's [tool.pytest.ini_options] pythonpath only reaches pytest's own
    # collection, not a bare subprocess interpreter — pass it through PYTHONPATH
    # explicitly so the child can `import experiments`. `experiments`' own
    # parent directory (py_project_root, e.g. "backend") is already on
    # sys.path in this process because pytest resolved it the same way;
    # reuse that resolution instead of re-deriving the path convention here.
    # fingerprint_frame.__globals__["__file__"] is
    # .../<py_project_root>/experiments/fingerprint.py, so its
    # grandparent is <py_project_root>.
    module_file = Path(fingerprint_frame.__globals__["__file__"]).resolve()
    experiments_parent = str(module_file.parents[1])
    env = {**os.environ, "PYTHONPATH": experiments_parent}

    first = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env
    ).stdout.strip()
    second = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env
    ).stdout.strip()

    assert first == second
    assert first == fingerprint_frame(_frame()).frame_hash


def test_data_identity_exposes_no_cell_value() -> None:
    identity = fingerprint_frame(_frame())

    # The dataclass's field set is closed: a digest, counts, column names, and
    # an optional source-hash sentinel — no field shaped to hold row data.
    fields = {"frame_hash", "n_rows", "n_cols", "columns", "source_hash"}
    assert set(DataIdentity.__dataclass_fields__) == fields

    # frame_hash is a fixed-length hex digest (sha256 -> 64 hex chars), which
    # by construction cannot contain a decoded cell value — it is opaque
    # digest output, not a serialization of the frame.
    assert len(identity.frame_hash) == 64
    assert all(c in "0123456789abcdef" for c in identity.frame_hash)

    # columns carries names only, never row content.
    assert identity.columns == ("a", "b", "c")
    assert identity.n_rows == 3
    assert identity.n_cols == 3


def test_class_balance_non_primitive_key_raises() -> None:
    with pytest.raises(ValueError, match="class_balance"):
        validate_class_balance({("tuple", "key"): 0.5})


def test_class_balance_primitive_keys_pass() -> None:
    validate_class_balance({0: 0.6, 1: 0.4})
    validate_class_balance({"approved": 0.6, "denied": 0.4})
