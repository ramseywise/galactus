"""Runtime knobs for the ML stages — one place, overridable by env.

Every value here was previously a module-level constant duplicated across the
tree (`RANDOM_STATE = 42` appeared in five modules, `BASELINE_TOLERANCE` and
`DEFAULT_ISOTONIC_MIN_SAMPLES` in one each). A constant in a module is not
swappable: changing the seed for one run meant editing source. Same
`BaseSettings` + `SettingsConfigDict(env_file=".env")` convention as the AI
side's `observability/settings.py` and `integrations/settings.py`.

`model_version` plus `artifact_dir` is the versioned-artifact seam — a run writes
to `{artifact_dir}/{model_version}/` so two runs do not overwrite each other.

The stage modules keep their existing constants as defaults so nothing that
imports them breaks; those constants now read from here, and a caller that wants
a different value sets the env var or passes the argument explicitly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """Env-overridable settings for the ML stages. Prefix `ML_` so these never
    collide with the AI side's settings in a project that renders both."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ML_",
        extra="ignore",
        protected_namespaces=(),
    )

    # ── reproducibility ──────────────────────────────────────────────────────
    random_seed: int = 42
    """Threaded into every estimator factory and every splitter."""

    # ── splitting ────────────────────────────────────────────────────────────
    n_splits: int = 5

    # ── model selection ──────────────────────────────────────────────────────
    model_registry_include: tuple[str, ...] = ()
    """Candidate allow-list. Empty means every available spec for the
    (family, output) pair. Baselines are appended regardless."""

    # ── sampling ─────────────────────────────────────────────────────────────
    sampling: Literal["none", "undersample", "oversample", "smote"] = "none"

    # ── calibration + thresholding ───────────────────────────────────────────
    calibration_method: Literal["auto", "sigmoid", "isotonic"] = "auto"
    """"auto" picks isotonic at or above isotonic_min_samples, else sigmoid."""
    isotonic_min_samples: int = 1000
    """Isotonic needs data to not overfit the reliability curve."""
    cost_fp: float = 1.0
    cost_fn: float = 1.0
    """Business inputs, not model outputs — which is why they live in config and
    are consumed only by calibration/, never by training/ (naming.md §3 rule 2)."""

    # ── evaluation ───────────────────────────────────────────────────────────
    baseline_tolerance: float = 0.01
    """A margin below this is reported as a tie, not a win. A strict `>` once
    reported a 0.0002 margin as beating the baseline."""

    # ── artifacts ────────────────────────────────────────────────────────────
    artifact_dir: Path = Path("data/models")
    """Gitignored. Under data/ because artifacts are never code (naming.md §2)."""
    model_version: str = "v0"

    @property
    def version_dir(self) -> Path:
        """Where this run's artifacts belong."""
        return self.artifact_dir / self.model_version

    def resolve_calibration(self, n_samples: int) -> Literal["sigmoid", "isotonic"]:
        """Concrete calibration method for a sample size, resolving "auto"."""
        if self.calibration_method != "auto":
            return self.calibration_method
        return "isotonic" if n_samples >= self.isotonic_min_samples else "sigmoid"


settings = MLSettings()
