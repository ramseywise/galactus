"""The k sweep, with baselines computed in the same call as the score.

The baseline is not a separate step a tired author can skip. `evaluate` computes the
silhouette and both comparators together and returns them in one record, so there is no
code path that produces a score without the number it has to beat. A model that beats
nothing has not been shown to work, and a baseline computed after a good score exists is
a baseline chosen to be beaten.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score

#: Silhouette on tens of thousands of points is O(n^2) in memory; sample it. Fixed seed so
#: the number is reproducible rather than merely plausible.
SILHOUETTE_SAMPLE = 5000
RANDOM_STATE = 0

#: Above this, treat the result as a suspected leak rather than a triumph. A clustering
#: this clean on real behavioural data usually means a column restated the answer.
IMPLAUSIBLE_SILHOUETTE = 0.70


@dataclass(frozen=True)
class Result:
    k: int
    silhouette: float
    davies_bouldin: float
    inertia: float
    sizes: tuple[int, ...]
    baseline_random: float
    baseline_k2: float
    labels: np.ndarray = field(repr=False)

    @property
    def beats_baselines(self) -> bool:
        return self.silhouette > self.baseline_random and self.silhouette > self.baseline_k2

    @property
    def implausible(self) -> bool:
        return self.silhouette > IMPLAUSIBLE_SILHOUETTE


def _silhouette(matrix: np.ndarray, labels: np.ndarray) -> float:
    if len(set(labels)) < 2:
        return float("nan")
    return float(
        silhouette_score(
            matrix,
            labels,
            sample_size=min(SILHOUETTE_SAMPLE, len(matrix)),
            random_state=RANDOM_STATE,
        )
    )


def random_baseline(matrix: np.ndarray, k: int) -> float:
    """Silhouette of a random partition at the same k — the 'no structure' floor."""
    rng = np.random.default_rng(RANDOM_STATE)
    return _silhouette(matrix, rng.integers(0, k, size=len(matrix)))


def k2_baseline(matrix: np.ndarray) -> float:
    """Silhouette of the trivial two-way split — the cheapest real alternative."""
    labels = KMeans(n_clusters=2, n_init=10, random_state=RANDOM_STATE).fit_predict(matrix)
    return _silhouette(matrix, labels)


def evaluate(matrix: np.ndarray, k: int, baseline_k2: float | None = None) -> Result:
    """Fit at one k and score it against both baselines, in one call."""
    model = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(matrix)
    labels = model.labels_
    sizes = tuple(int((labels == i).sum()) for i in range(k))
    return Result(
        k=k,
        silhouette=_silhouette(matrix, labels),
        davies_bouldin=float(davies_bouldin_score(matrix, labels)),
        inertia=float(model.inertia_),
        sizes=sizes,
        baseline_random=random_baseline(matrix, k),
        baseline_k2=k2_baseline(matrix) if baseline_k2 is None else baseline_k2,
        labels=labels,
    )


def sweep(matrix: np.ndarray, k_range=range(2, 11)) -> list[Result]:
    """Evaluate every k in the range. The whole sweep is reported, not just the winner."""
    shared_k2 = k2_baseline(matrix)
    return [evaluate(matrix, k, baseline_k2=shared_k2) for k in k_range]


def best(results: list[Result]) -> Result:
    """Highest silhouette among results that beat both baselines; else highest overall.

    Falling back rather than raising is deliberate: "nothing beat the baseline" is a real
    finding the report must be able to state, not an error that stops the run.
    """
    qualified = [r for r in results if r.beats_baselines]
    return max(qualified or results, key=lambda r: r.silhouette)
