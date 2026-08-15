"""Soft clustering via Gaussian Mixture Models — probabilistic cluster
membership instead of hard k-means assignment, useful for candidate
filtering/retrieval ("give me items that plausibly belong to any cluster this
query is also plausibly in", not just "same nearest centroid").

Adapted from a real production recommendation system's clustering module —
genericized (dropped hardcoded "audio feature"/Spotify-specific column lists in
favor of constructor-supplied continuous/categorical feature lists, same
pattern as `ml.model_comparison.compare.TabularPreprocessor`).

Usage:
    gmm, scaler = fit_gmm(corpus_df, continuous_features=[...], categorical_features={...})
    query_probs = predict_cluster_probs(query_features, gmm)
    filtered = filter_by_cluster_overlap(corpus_df, query_probs, gmm, scaler, ...)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import MinMaxScaler


def _one_hot_encode(df: pd.DataFrame, col: str, categories: list[str]) -> np.ndarray:
    """One-hot encode `col` against a fixed, ordered category list — fixed
    (not learned from data) so the resulting feature matrix has a stable shape
    across fit and future transform calls, even if a category is absent from
    a given batch."""
    cat_index = {cat: idx for idx, cat in enumerate(categories)}
    out = np.zeros((len(df), len(categories)), dtype=np.float64)
    for row_idx, val in enumerate(df[col].tolist()):
        if val in cat_index:
            out[row_idx, cat_index[val]] = 1.0
    return out


def build_cluster_features(
    df: pd.DataFrame,
    continuous_features: list[str],
    categorical_features: dict[str, list[str]],
    scaler: MinMaxScaler,
    fit_scaler: bool = False,
) -> tuple[np.ndarray, MinMaxScaler]:
    """Extract, one-hot encode, and scale features for GMM clustering.

    `categorical_features` maps column name -> its fixed, ordered category
    list (e.g. {"region": ["us", "eu", "apac"]}).
    """
    parts = [df[continuous_features].to_numpy(dtype=np.float64)]
    for col, categories in categorical_features.items():
        parts.append(_one_hot_encode(df, col, categories))
    features = np.concatenate(parts, axis=1)

    scaled = scaler.fit_transform(features) if fit_scaler else scaler.transform(features)
    return scaled, scaler


def fit_gmm(
    corpus: pd.DataFrame,
    continuous_features: list[str],
    categorical_features: dict[str, list[str]] | None = None,
    n_components: int = 8,
    random_state: int = 42,
) -> tuple[GaussianMixture, MinMaxScaler]:
    """Fit a MinMaxScaler then a GaussianMixture on the corpus. Returns
    (fitted_gmm, fitted_scaler) — both needed to score new points later."""
    categorical_features = categorical_features or {}
    scaler = MinMaxScaler()
    features, scaler = build_cluster_features(
        corpus, continuous_features, categorical_features, scaler, fit_scaler=True
    )

    gmm = GaussianMixture(
        n_components=n_components, random_state=random_state, covariance_type="full"
    )
    gmm.fit(features)
    return gmm, scaler


def predict_cluster_probs(features: np.ndarray, gmm: GaussianMixture) -> np.ndarray:
    """Soft cluster membership probabilities for each row — shape
    (n_rows, n_components), each row summing to 1."""
    return gmm.predict_proba(features)


def filter_by_cluster_overlap(
    corpus: pd.DataFrame,
    query_probs: np.ndarray,
    gmm: GaussianMixture,
    scaler: MinMaxScaler,
    continuous_features: list[str],
    categorical_features: dict[str, list[str]] | None = None,
    min_prob: float = 0.05,
) -> pd.DataFrame:
    """Return corpus rows whose dominant cluster overlaps the query's cluster
    distribution — a corpus row is included if the query assigns probability
    >= min_prob to that row's own dominant (argmax) cluster.

    Adds `cluster_id` (dominant cluster index) and `cluster_prob` (its
    probability) columns to the returned rows.
    """
    categorical_features = categorical_features or {}
    corpus_features, _ = build_cluster_features(
        corpus, continuous_features, categorical_features, scaler, fit_scaler=False
    )
    corpus_probs = predict_cluster_probs(corpus_features, gmm)

    cluster_ids = np.argmax(corpus_probs, axis=1)
    cluster_probs_max = corpus_probs[np.arange(len(corpus_probs)), cluster_ids]

    relevant_clusters = {int(c) for c in np.where(query_probs >= min_prob)[0]}
    mask = np.array([int(cid) in relevant_clusters for cid in cluster_ids])

    filtered = corpus.loc[mask].copy()
    filtered["cluster_id"] = cluster_ids[mask].astype(int)
    filtered["cluster_prob"] = cluster_probs_max[mask]
    return filtered
