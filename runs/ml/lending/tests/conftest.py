"""Path setup for the lending run's tests.

`src/` modules import as top-level names (`from frame import prepare_frame`), the same
pattern as `runs/ml/fraud/tests/conftest.py` — but *appended*, not front-inserted:
fraud's tests import their harness as `from run import summarise`, and putting this
directory in front of theirs would shadow that module with lending's `run.py` (which
exits at import when the toolkit is absent). Lending's module names are otherwise
unique across the suite (`frame`, `splits`, `summary`, `guards`, `synthetic`,
`run_record`); lending's own `run` is imported by explicit file path where a test
needs it, never by bare name. No real row enters a test file — fixtures are hand-built
or seeded-synthetic frames, never the gitignored extract.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_POC = Path(__file__).resolve().parents[1]
sys.path.append(str(_POC / "src"))

from frame import SEED  # noqa: E402 — resolvable only after the path append above


@pytest.fixture
def clean_frame():
    """The clean synthetic twin at the run's own seed — raw, pre-`prepare_frame`."""
    import synthetic

    return synthetic.clean_frame(SEED)


@pytest.fixture
def planted_leak_frame():
    """The planted-leak twin at the same seed — identical except the two plants."""
    import synthetic

    return synthetic.planted_leak_frame(SEED)
