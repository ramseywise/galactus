from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.datasets import make_blobs

from ml.clustering.gmm import (
    build_cluster_features,
    filter_by_cluster_overlap,
    fit_gmm,
    predict_cluster_probs,
)


def _blob_df(n_samples: int = 300, centers: int = 4, seed: int = 0) -> pd.DataFrame:
    x, labels = make_blobs(n_samples=n_samples, centers=centers, n_features=2, random_state=seed)
    df = pd.DataFrame(x, columns=["feat_a", "feat_b"])
    df["region"] = np.where(labels % 2 == 0, "north", "south")
    df["_true_label"] = labels
    return df


def test_fit_gmm_produces_valid_probability_rows():
    df = _blob_df()
    gmm, scaler = fit_gmm(
        df,
        continuous_features=["feat_a", "feat_b"],
        categorical_features={"region": ["north", "south"]},
        n_components=4,
    )
    features, _ = build_cluster_features(
        df,
        ["feat_a", "feat_b"],
        {"region": ["north", "south"]},
        scaler,
        fit_scaler=False,
    )
    probs = predict_cluster_probs(features, gmm)
    assert probs.shape == (len(df), 4)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-6)


def test_gmm_recovers_real_cluster_structure():
    # Well-separated blobs should each land predominantly in one GMM component —
    # a real check that the fit actually captured the underlying structure,
    # not just that it runs without error.
    df = _blob_df(n_samples=400, centers=4, seed=1)
    gmm, scaler = fit_gmm(df, continuous_features=["feat_a", "feat_b"], n_components=4)
    features, _ = build_cluster_features(df, ["feat_a", "feat_b"], {}, scaler, fit_scaler=False)
    probs = predict_cluster_probs(features, gmm)
    dominant = np.argmax(probs, axis=1)

    # For each true blob label, the assigned GMM components should be highly
    # concentrated (one component should dominate that label's rows).
    for true_label in df["_true_label"].unique():
        mask = df["_true_label"] == true_label
        assigned = dominant[mask.to_numpy()]
        most_common_share = np.bincount(assigned).max() / len(assigned)
        assert most_common_share > 0.8


def test_filter_by_cluster_overlap_returns_relevant_subset():
    df = _blob_df(n_samples=400, centers=4, seed=2)
    gmm, scaler = fit_gmm(df, continuous_features=["feat_a", "feat_b"], n_components=4)
    features, _ = build_cluster_features(df, ["feat_a", "feat_b"], {}, scaler, fit_scaler=False)
    all_probs = predict_cluster_probs(features, gmm)

    # Use the first row's own cluster distribution as the "query".
    query_probs = all_probs[0]
    filtered = filter_by_cluster_overlap(
        df,
        query_probs,
        gmm,
        scaler,
        continuous_features=["feat_a", "feat_b"],
        min_prob=0.05,
    )
    assert "cluster_id" in filtered.columns
    assert "cluster_prob" in filtered.columns
    assert len(filtered) > 0
    assert len(filtered) <= len(df)
