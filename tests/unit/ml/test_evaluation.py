"""Step 7 — metrics, calibration, and the cost-based decision rule.

Three claims are load-bearing here and each gets a test that could fail:

1. PR-AUC is the headline under imbalance, and it is a *different* number from
   ROC-AUC — demonstrated on a frame where ROC looks good and precision is poor.
2. Calibration improves the Brier score on a deliberately distorted model. The
   distortion is applied by hand so the improvement is attributable.
3. `choose_threshold` is pure and its optimum matches one computed by hand from
   a cost matrix, not merely "some threshold that looks reasonable".
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.datasets import make_blobs, make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import train_test_split

from ml.evaluation.calibration import (
    assess_calibration,
    calibrate_classifier,
    expected_calibration_error,
    recommend_method,
    reliability_curve,
)
from ml.evaluation.metrics import (
    classification_metrics,
    clustering_metrics,
    pr_curve,
    precision_at_k,
    regression_metrics,
    roc_curve_points,
)
from ml.evaluation.threshold import (
    choose_threshold,
    choose_threshold_out_of_fold,
    expected_cost,
    threshold_for_capacity,
)

RANDOM_STATE = 42


@pytest.fixture
def imbalanced_predictions():
    """A 95/5 frame with a model that ranks decently but is not sharp.

    Constructed so ROC-AUC flatters and average precision does not — the whole
    argument for leading with PR-AUC.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    n = 1000
    y_true = (rng.random(n) < 0.05).astype(int)
    # Positives score higher on average, but the distributions overlap heavily.
    y_prob = np.clip(
        np.where(y_true == 1, rng.normal(0.55, 0.2, n), rng.normal(0.30, 0.2, n)),
        0.001,
        0.999,
    )
    return y_true, y_prob


# ── metrics ──────────────────────────────────────────────────────────────────


def test_pr_auc_is_the_headline_and_is_lower_than_roc_auc(imbalanced_predictions):
    """The claim in the module docstring, stated as an assertion.

    ROC-AUC divides false positives by the majority-class count, so it stays
    high while the precision an operator experiences is poor. If these two ever
    converge on a 95/5 frame, the fixture stopped being imbalanced.
    """
    y_true, y_prob = imbalanced_predictions
    metrics = classification_metrics(y_true, (y_prob >= 0.5).astype(int), y_prob)

    name, value = metrics.headline(imbalanced=True)
    assert name == "average_precision"
    assert value == metrics.average_precision

    assert metrics.roc_auc > metrics.average_precision, (
        "on a 95/5 frame ROC-AUC should flatter relative to PR-AUC; "
        f"got roc_auc={metrics.roc_auc:.3f} ap={metrics.average_precision:.3f}"
    )
    assert metrics.prevalence == pytest.approx(np.mean(y_true))


def test_headline_falls_back_to_roc_when_not_imbalanced(imbalanced_predictions):
    y_true, y_prob = imbalanced_predictions
    metrics = classification_metrics(y_true, (y_prob >= 0.5).astype(int), y_prob)
    name, _ = metrics.headline(imbalanced=False)
    assert name == "roc_auc"


def test_probability_metrics_are_none_without_probabilities(imbalanced_predictions):
    """Missing must not look like zero — a report that prints 0.00 for a metric
    that was never computed is worse than one that prints nothing."""
    y_true, y_prob = imbalanced_predictions
    metrics = classification_metrics(y_true, (y_prob >= 0.5).astype(int))

    assert metrics.average_precision is None
    assert metrics.roc_auc is None
    assert metrics.brier is None
    assert metrics.accuracy > 0


def test_precision_at_k_is_the_fixed_capacity_number(imbalanced_predictions):
    """Top-50 precision must beat the base rate for a model that ranks at all,
    and must beat top-500 precision, since the ranking degrades as k grows."""
    y_true, y_prob = imbalanced_predictions
    at_50 = precision_at_k(y_true, y_prob, 50)
    at_500 = precision_at_k(y_true, y_prob, 500)

    assert at_50 > np.mean(y_true), "a ranking model should beat the base rate at the top"
    assert at_50 >= at_500


def test_precision_at_k_clamps_above_the_row_count(imbalanced_predictions):
    y_true, y_prob = imbalanced_predictions
    assert precision_at_k(y_true, y_prob, 10_000) == pytest.approx(np.mean(y_true))


def test_precision_at_k_rejects_non_positive_k(imbalanced_predictions):
    y_true, y_prob = imbalanced_predictions
    with pytest.raises(ValueError, match="positive"):
        precision_at_k(y_true, y_prob, 0)


def test_pr_curve_baseline_is_prevalence_and_roc_baseline_is_half(imbalanced_predictions):
    """The no-skill reference differs between the two curves; a report that drew
    0.5 on a PR chart would be drawing a line no model is measured against."""
    y_true, y_prob = imbalanced_predictions

    pr = pr_curve(y_true, y_prob)
    roc = roc_curve_points(y_true, y_prob)

    assert pr.baseline == pytest.approx(np.mean(y_true))
    assert roc.baseline == 0.5
    assert len(pr.x) == len(pr.y) and len(pr.x) > 1
    assert len(roc.x) == len(roc.y) and len(roc.x) > 1


def test_multiclass_metrics_include_per_class_breakdown():
    x, y = make_classification(
        n_samples=300,
        n_features=8,
        n_informative=5,
        n_classes=3,
        random_state=RANDOM_STATE,
    )
    model = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE).fit(x, y)
    metrics = classification_metrics(y, model.predict(x), model.predict_proba(x))

    assert set(metrics.per_class) == {"0", "1", "2"}
    assert metrics.roc_auc is not None, "multiclass ROC-AUC is one-vs-rest macro"
    assert metrics.average_precision is None, "average precision is binary-only here"
    assert len(metrics.confusion) == 3


def test_regression_mape_is_none_when_a_true_value_is_zero():
    """Dividing by zero would produce an infinity that poisons the mean silently."""
    with_zero = regression_metrics([0.0, 1.0, 2.0], [0.1, 1.1, 1.9])
    without_zero = regression_metrics([1.0, 2.0, 3.0], [1.1, 1.9, 3.2])

    assert with_zero.mape is None
    assert without_zero.mape is not None and without_zero.mape > 0
    assert with_zero.rmse > 0


def test_clustering_metrics_exclude_dbscan_noise_from_scores():
    """Noise rows belong to no cluster, so scoring them is meaningless — but the
    count must survive, because "most of the frame was noise" is the diagnostic."""
    x, y = make_blobs(n_samples=150, centers=3, random_state=RANDOM_STATE)
    labels = y.copy()
    labels[:20] = -1  # mark 20 rows as noise, the DBSCAN convention

    metrics = clustering_metrics(x, labels)

    assert metrics.n_noise == 20
    assert metrics.n_clusters == 3, "noise is not a cluster"
    assert "-1" not in metrics.cluster_sizes
    assert metrics.silhouette is not None and metrics.silhouette > 0


def test_clustering_metrics_degrade_to_none_with_a_single_cluster():
    x, _ = make_blobs(n_samples=50, centers=1, random_state=RANDOM_STATE)
    metrics = clustering_metrics(x, np.zeros(50, dtype=int))

    assert metrics.n_clusters == 1
    assert metrics.silhouette is None, "silhouette is undefined for one cluster"


# ── calibration ──────────────────────────────────────────────────────────────


def test_calibration_improves_brier_on_a_deliberately_miscalibrated_model():
    """The Done-when for calibration, made attributable.

    A shallow random forest on this frame ranks acceptably but produces
    probabilities pushed toward the middle. Wrapping it in
    `CalibratedClassifierCV` must reduce the Brier score measurably — if it does
    not, calibration is decoration and the workflow should not default to it.
    """
    x, y = make_classification(
        n_samples=2000,
        n_features=20,
        n_informative=6,
        weights=[0.85, 0.15],
        random_state=RANDOM_STATE,
    )
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.3, stratify=y, random_state=RANDOM_STATE
    )

    base = RandomForestClassifier(n_estimators=25, max_depth=4, random_state=RANDOM_STATE)
    raw = base.fit(x_train, y_train).predict_proba(x_test)[:, 1]

    calibrated = calibrate_classifier(
        RandomForestClassifier(n_estimators=25, max_depth=4, random_state=RANDOM_STATE),
        method="isotonic",
        cv=5,
    ).fit(x_train, y_train)
    adjusted = calibrated.predict_proba(x_test)[:, 1]

    report = assess_calibration(y_test, raw, adjusted, method="isotonic")

    assert report.improved, (
        f"calibration did not improve Brier: {report.brier_before:.4f} -> {report.brier_after:.4f}"
    )
    assert report.brier_delta < 0
    assert report.brier_after == pytest.approx(brier_score_loss(y_test, adjusted))


def test_calibration_report_is_honest_when_calibration_hurts():
    """`improved` must be able to say no. A flag that is always True carries no
    information, so the false branch needs exercising."""
    y_true = np.array([0, 0, 1, 1] * 25)
    good = np.where(y_true == 1, 0.9, 0.1)
    ruined = np.where(y_true == 1, 0.55, 0.45)  # same ranking, worse probabilities

    report = assess_calibration(y_true, good, ruined, method="sigmoid")

    assert not report.improved
    assert report.brier_delta > 0


def test_expected_calibration_error_is_zero_for_a_perfect_model():
    """A model whose predicted rate matches the observed rate in every bin has
    nothing left to correct."""
    y_true = np.array([1] * 50 + [0] * 50)
    perfect = np.array([1.0] * 50 + [0.0] * 50)
    assert expected_calibration_error(y_true, perfect, n_bins=10) == pytest.approx(0.0)


def test_expected_calibration_error_catches_systematic_overconfidence():
    """20% of these actually pay; the model says 90%. ECE must be large."""
    rng = np.random.default_rng(RANDOM_STATE)
    y_true = (rng.random(500) < 0.2).astype(int)
    overconfident = np.full(500, 0.9)

    error = expected_calibration_error(y_true, overconfident, n_bins=10)
    assert error > 0.6, f"expected a large gap for 0.9-vs-0.2, got {error:.3f}"


def test_reliability_curve_drops_empty_bins():
    """Plotting an empty bin at zero draws a line to the origin that no data
    supports — the curve must only contain populated bins."""
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.05, 0.05, 0.95, 0.95])  # only two of ten bins populated

    curve = reliability_curve(y_true, y_prob, n_bins=10)

    assert len(curve.x) == 2
    assert len(curve.x) == len(curve.y)
    assert curve.y == [0.0, 1.0]


def test_probability_of_one_lands_in_the_final_bin():
    """p == 1.0 is a legal probability; digitize would otherwise index past the
    last bin and either raise or silently wrap."""
    curve = reliability_curve(np.array([1, 1]), np.array([1.0, 1.0]), n_bins=10)
    assert len(curve.x) == 1
    assert curve.x[0] == pytest.approx(1.0)


def test_recommend_method_prefers_sigmoid_on_small_validation_sets():
    assert recommend_method(200) == "sigmoid"
    assert recommend_method(5000) == "isotonic"


def test_unknown_calibration_method_raises():
    with pytest.raises(ValueError, match="unknown calibration method"):
        calibrate_classifier(LogisticRegression(), method="platt")


# ── the decision rule ────────────────────────────────────────────────────────


def test_choose_threshold_matches_a_hand_computed_optimum():
    """The Done-when for the decision rule, on a frame small enough to verify by
    hand.

    Six rows, scores 0.1 … 0.6, positives at 0.4 and 0.6.
    cost_fp = 1, cost_fn = 10. Enumerating the candidate thresholds:

        t=0.1 -> flags all 6: FP=4, FN=0 -> cost 4
        t=0.2 -> flags 5:     FP=3, FN=0 -> cost 3
        t=0.3 -> flags 4:     FP=2, FN=0 -> cost 2
        t=0.4 -> flags 3:     FP=1, FN=0 -> cost 1   <- minimum
        t=0.5 -> flags 2:     FP=1, FN=1 -> cost 11
        t=0.6 -> flags 1:     FP=0, FN=1 -> cost 10

    The optimum is 0.4 at a cost of 1, and the 0.5 convention would have cost 11.
    """
    y_prob = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    y_true = np.array([0, 0, 0, 1, 0, 1])

    result = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=10.0)

    assert result.threshold == pytest.approx(0.4)
    assert result.expected_cost == pytest.approx(1.0)
    assert result.cost_at_default == pytest.approx(11.0)
    assert result.savings_vs_default == pytest.approx(10.0)
    assert (result.true_positives, result.false_positives) == (2, 1)
    assert (result.false_negatives, result.true_negatives) == (0, 3)
    assert result.n_flagged == 3
    assert result.cost_ratio == pytest.approx(10.0)


def test_choose_threshold_is_pure():
    """Same inputs, same result — twice, and with the inputs unmodified after.

    Purity is what makes the chosen operating point auditable: a threshold that
    depends on call order or mutates its arguments cannot be reproduced from the
    record.
    """
    y_prob = np.array([0.1, 0.35, 0.4, 0.62, 0.8, 0.9])
    y_true = np.array([0, 0, 1, 0, 1, 1])
    prob_copy, true_copy = y_prob.copy(), y_true.copy()

    first = choose_threshold(y_true, y_prob, cost_fp=2.0, cost_fn=5.0)
    second = choose_threshold(y_true, y_prob, cost_fp=2.0, cost_fn=5.0)

    assert first == second
    np.testing.assert_array_equal(y_prob, prob_copy)
    np.testing.assert_array_equal(y_true, true_copy)


def test_asymmetric_costs_move_the_threshold_in_the_right_direction(imbalanced_predictions):
    """An expensive false negative must lower the threshold — flagging more —
    and an expensive false positive must raise it. If the ordering ever inverts,
    the cost matrix is being applied backwards."""
    y_true, y_prob = imbalanced_predictions

    fn_expensive = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=50.0)
    fp_expensive = choose_threshold(y_true, y_prob, cost_fp=50.0, cost_fn=1.0)

    assert fn_expensive.threshold < fp_expensive.threshold
    assert fn_expensive.n_flagged > fp_expensive.n_flagged
    assert fn_expensive.recall > fp_expensive.recall


def test_choose_threshold_never_loses_to_the_default(imbalanced_predictions):
    """The minimiser searches every distinct operating point the data admits, and
    0.5 sits inside that space — so the chosen cost can tie the default but can
    never exceed it."""
    y_true, y_prob = imbalanced_predictions
    result = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=8.0)

    assert result.expected_cost <= result.cost_at_default


def test_expected_cost_agrees_with_the_chosen_optimum(imbalanced_predictions):
    """The reported cost must be the cost of the reported threshold — the two
    are computed by different code paths and must not drift apart."""
    y_true, y_prob = imbalanced_predictions
    result = choose_threshold(y_true, y_prob, cost_fp=3.0, cost_fn=7.0)

    recomputed = expected_cost(y_true, y_prob, result.threshold, cost_fp=3.0, cost_fn=7.0)
    assert recomputed == pytest.approx(result.expected_cost)


def test_sweep_covers_every_distinct_score(imbalanced_predictions):
    """The candidate grid is the set of observed scores — exact, not sampled."""
    y_true, y_prob = imbalanced_predictions
    result = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=4.0)

    assert len(result.sweep) == len(np.unique(y_prob))
    assert min(cost for _, cost in result.sweep) == pytest.approx(result.expected_cost)


def test_ties_break_toward_the_lower_threshold():
    """A genuine tie must resolve downward — flagging more — rather than by
    grid-iteration accident.

    Scores 0.4 (positive), 0.6 (negative), 0.7 (positive), symmetric costs:

        t=0.4 -> flags all three: FP=1 (the 0.6), FN=0        -> cost 1
        t=0.6 -> flags 0.6, 0.7:  FP=1,           FN=1 (0.4)  -> cost 2
        t=0.7 -> flags 0.7:       FP=0,           FN=1 (0.4)  -> cost 1

    t=0.4 and t=0.7 tie at 1. The lower one wins.
    """
    y_prob = np.array([0.4, 0.6, 0.7])
    y_true = np.array([1, 0, 1])

    result = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=1.0)

    assert result.expected_cost == pytest.approx(1.0)
    assert result.threshold == pytest.approx(0.4), "a tie must resolve to the lower threshold"
    assert result.n_flagged == 3


def test_threshold_marks_itself_in_sample_by_default(imbalanced_predictions):
    """The threshold is fitted to the rows it is then scored on, so precision and
    recall are optimistic. The result has to say so — a caller should not have to
    know to add the caveat, which is exactly what went unsaid before."""
    y_true, y_prob = imbalanced_predictions
    result = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=6.0)

    assert result.in_sample is True
    assert result.selection_caveat is not None
    assert "optimistic" in result.selection_caveat


def test_an_out_of_sample_threshold_carries_no_caveat(imbalanced_predictions):
    """When the caller has genuinely held rows out, the numbers are honest and
    the caveat would be wrong."""
    y_true, y_prob = imbalanced_predictions
    result = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=6.0, in_sample=False)

    assert result.in_sample is False
    assert result.selection_caveat is None


def test_the_in_sample_flag_does_not_change_the_chosen_threshold(imbalanced_predictions):
    """The flag is a statement about provenance, not an input to the arithmetic —
    it must not move the optimum."""
    y_true, y_prob = imbalanced_predictions
    marked = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=6.0, in_sample=True)
    unmarked = choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=6.0, in_sample=False)

    assert marked.threshold == unmarked.threshold
    assert marked.expected_cost == unmarked.expected_cost


def test_zero_cost_raises():
    """A free error class degenerates the optimum to flag-everything or
    flag-nothing — a result that looks like a decision but is an input artefact.
    """
    y_prob = np.array([0.2, 0.8])
    y_true = np.array([0, 1])

    with pytest.raises(ValueError, match="costs must be positive"):
        choose_threshold(y_true, y_prob, cost_fp=0.0, cost_fn=5.0)
    with pytest.raises(ValueError, match="costs must be positive"):
        choose_threshold(y_true, y_prob, cost_fp=5.0, cost_fn=-1.0)


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError, match="must match"):
        choose_threshold(np.array([0, 1, 1]), np.array([0.2, 0.8]), cost_fp=1.0, cost_fn=1.0)


def test_empty_predictions_raise():
    with pytest.raises(ValueError, match="empty"):
        choose_threshold(np.array([]), np.array([]), cost_fp=1.0, cost_fn=1.0)


def _two_folds():
    """Four rows, two folds, arranged so each fold's selection is hand-checkable.

    Fold A test rows: probs (0.2, y=0), (0.9, y=1). Fold B: (0.4, y=0), (0.8, y=1).
    With symmetric unit costs:
      - selecting on B for A: grid {0.4, 0.8} — t=0.8 is cost 0, so t_A = 0.8;
        applied to A: 0.9 flagged (TP), 0.2 not (TN) — cost 0.
      - selecting on A for B: grid {0.2, 0.9} — t=0.9 is cost 0, so t_B = 0.9;
        applied to B: 0.8 not flagged (FN) — cost = cost_fn.
    """
    y_true = np.array([0, 1, 0, 1])
    y_prob = np.array([0.2, 0.9, 0.4, 0.8])
    folds = [
        (np.array([2, 3]), np.array([0, 1])),
        (np.array([0, 1]), np.array([2, 3])),
    ]
    return y_true, y_prob, folds


def test_out_of_fold_metrics_match_the_hand_computed_evaluation():
    """Each row is scored at a threshold chosen without it, and the pooled
    counts must equal the ones traced by hand — including the FN that the
    in-sample sweep (which reaches cost 0 at t=0.8) would never report."""
    y_true, y_prob, folds = _two_folds()
    result = choose_threshold_out_of_fold(y_true, y_prob, folds, cost_fp=1.0, cost_fn=1.0)

    assert result.fold_thresholds == (0.8, 0.9)
    assert (result.true_positives, result.false_positives) == (1, 0)
    assert (result.false_negatives, result.true_negatives) == (1, 2)
    assert result.expected_cost == pytest.approx(1.0)
    assert result.recall == pytest.approx(0.5)
    assert result.n_flagged == 1
    # The deployable threshold is still the full-data optimum...
    assert result.threshold == pytest.approx(
        choose_threshold(y_true, y_prob, cost_fp=1.0, cost_fn=1.0).threshold
    )
    # ...whose in-sample cost (0) is exactly the optimism the pooled cost corrects.
    assert result.expected_cost > 0.0


def test_out_of_fold_result_needs_no_caveat(imbalanced_predictions):
    """The point of the exercise: metrics measured on rows the sweep never saw
    are honest, so `in_sample` is False and the caveat disappears."""
    y_true, y_prob = imbalanced_predictions
    n = len(y_true)
    idx = np.arange(n)
    folds = [(np.setdiff1d(idx, test), test) for test in np.array_split(idx, 5)]

    result = choose_threshold_out_of_fold(y_true, y_prob, folds, cost_fp=1.0, cost_fn=6.0)

    assert result.in_sample is False
    assert result.selection_caveat is None
    assert len(result.fold_thresholds) == 5
    assert result.true_positives + result.false_positives + result.false_negatives + (
        result.true_negatives
    ) == len(y_true)


def test_out_of_fold_rejects_a_single_fold():
    y_true, y_prob, folds = _two_folds()
    with pytest.raises(ValueError, match="at least 2 folds"):
        choose_threshold_out_of_fold(y_true, y_prob, folds[:1], cost_fp=1.0, cost_fn=1.0)


def test_out_of_fold_rejects_overlapping_folds():
    y_true, y_prob, _ = _two_folds()
    folds = [(np.array([2, 3]), np.array([0, 1])), (np.array([0, 1]), np.array([1, 2, 3]))]
    with pytest.raises(ValueError, match="overlap"):
        choose_threshold_out_of_fold(y_true, y_prob, folds, cost_fp=1.0, cost_fn=1.0)


def test_out_of_fold_rejects_folds_that_skip_rows():
    """A gap would silently drop rows from the reported metrics — the same
    missing-vs-inapplicable collapse this toolkit refuses everywhere else."""
    y_true, y_prob, _ = _two_folds()
    folds = [(np.array([2, 3]), np.array([0, 1])), (np.array([0, 1]), np.array([2]))]
    with pytest.raises(ValueError, match="cover"):
        choose_threshold_out_of_fold(y_true, y_prob, folds, cost_fp=1.0, cost_fn=1.0)


def test_out_of_fold_selection_is_pure():
    y_true, y_prob, folds = _two_folds()
    true_copy, prob_copy = y_true.copy(), y_prob.copy()

    first = choose_threshold_out_of_fold(y_true, y_prob, folds, cost_fp=2.0, cost_fn=5.0)
    second = choose_threshold_out_of_fold(y_true, y_prob, folds, cost_fp=2.0, cost_fn=5.0)

    assert first == second
    np.testing.assert_array_equal(y_true, true_copy)
    np.testing.assert_array_equal(y_prob, prob_copy)


def test_threshold_for_capacity_flags_exactly_the_capacity():
    """The fixed-resource case: the budget is given, the only question is which."""
    y_prob = np.array([0.9, 0.1, 0.7, 0.3, 0.5])

    threshold = threshold_for_capacity(y_prob, capacity=2)
    assert int(np.sum(y_prob >= threshold)) == 2
    assert threshold == pytest.approx(0.7)


def test_threshold_for_capacity_beyond_the_queue_returns_the_minimum():
    y_prob = np.array([0.9, 0.1, 0.7])
    assert threshold_for_capacity(y_prob, capacity=99) == pytest.approx(0.1)


def test_threshold_for_capacity_rejects_non_positive_capacity():
    with pytest.raises(ValueError, match="capacity must be positive"):
        threshold_for_capacity(np.array([0.5]), capacity=0)
