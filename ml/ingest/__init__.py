"""Ingest stage — the data contract, checked before anything is assumed.

First in the stage order (naming.md §3). Owns schema checks, dtype assertions,
null policy, and row-count gates; owns no transformation. Nothing here imputes,
encodes, or coerces — a stage that repairs its input cannot report whether the
input was valid.
"""

from __future__ import annotations

from ml.ingest.contract import (
    ContractCheck,
    DataContractError,
    check_contract,
    infer_contract,
)

__all__ = [
    "ContractCheck",
    "DataContractError",
    "check_contract",
    "infer_contract",
]
