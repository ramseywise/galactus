"""Serving edge for the ML side — consumes a `ThresholdPolicy`, returns decisions.

Holds no business logic and fits nothing (naming.md §1 rule 1). The transport
layer wraps `ScoringService`; deployment is a later phase.
"""

from __future__ import annotations

from ml.api.predict import Decision, ScoringService, artifact_path

__all__ = ["Decision", "ScoringService", "artifact_path"]
