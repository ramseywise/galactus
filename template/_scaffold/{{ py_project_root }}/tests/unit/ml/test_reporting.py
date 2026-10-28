"""Step 8 — the HTML reporting arm.

The load-bearing test in this file is the external-reference one. Everything
else checks that panels render; that one checks the property the module exists
for, and it is asserted by regex over the actual output rather than by trusting
that nobody added a CDN link.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import load_breast_cancer, make_blobs, make_regression

from ml.evaluation.metrics import CurvePoints
from ml.reporting import (
    bar_svg,
    confusion_svg,
    curve_svg,
    reliability_svg,
    render_report,
    write_report,
)
from ml.selection.registry import RANDOM_STATE
from ml.workflows import run_classification, run_clustering, run_prediction

# Any src=/href= pointing at a scheme or a protocol-relative URL. Catches
# http://, https://, //cdn..., and data-less external references alike.
EXTERNAL_REF = re.compile(r'(?:src|href)\s*=\s*["\'](?:https?:)?//', re.IGNORECASE)

# A real <link> element, not the substring — the inlined stylesheet's own comment
# says the words "<link href>" while explaining why it must never be one.
LINK_TAG = re.compile(r"""<link\b[^>]*\b(?:href|rel)\s*=\s*["']""", re.IGNORECASE)
SCRIPT_TAG = re.compile(r"""<script\b[^>]*>""", re.IGNORECASE)


@pytest.fixture(scope="module")
def cancer_frame() -> pd.DataFrame:
    bundle = load_breast_cancer(as_frame=True)
    frame = bundle.frame.copy()
    return frame.rename(columns={"target": "malignant"})


@pytest.fixture(scope="module")
def cancer_result(cancer_frame: pd.DataFrame):
    return run_classification(
        cancer_frame,
        target="malignant",
        models=["logistic", "random_forest"],
        cost_fp=1.0,
        cost_fn=10.0,
        seed=RANDOM_STATE,
    )


@pytest.fixture(scope="module")
def cluster_result() -> object:
    x, _ = make_blobs(n_samples=240, centers=3, n_features=4, random_state=RANDOM_STATE)
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(x.shape[1])])
    return run_clustering(frame, models=["kmeans"], n_clusters=3, seed=RANDOM_STATE)


@pytest.fixture(scope="module")
def regression_result() -> object:
    x, y = make_regression(n_samples=300, n_features=5, noise=8.0, random_state=RANDOM_STATE)
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(x.shape[1])])
    frame["y"] = y
    return run_prediction(frame, target="y", models=["linear"], seed=RANDOM_STATE)


# --------------------------------------------------------------------------- #
# The Done-when: one file, zero external references, SVG paths.
# --------------------------------------------------------------------------- #


def test_report_has_zero_external_references(cancer_result):
    """The property the module exists for, asserted rather than assumed."""
    html = render_report(cancer_result, title="Breast cancer")
    assert not EXTERNAL_REF.search(html), EXTERNAL_REF.search(html).group(0)
    assert not SCRIPT_TAG.search(html), "a report must not depend on script execution"
    assert not LINK_TAG.search(html), "stylesheets must be inlined, never linked"


def test_the_guards_would_actually_catch_an_external_reference():
    """The guards' own failure paths — a detector that never fires proves nothing."""
    assert EXTERNAL_REF.search('<link href="https://cdn.example.com/x.css" />')
    assert EXTERNAL_REF.search("<img src='//cdn.example.com/a.png'>")
    assert not EXTERNAL_REF.search('<a href="#section">local</a>')

    assert LINK_TAG.search('<link rel="stylesheet" href="style.css">')
    assert not LINK_TAG.search("a &lt;link href&gt; would break the file")

    assert SCRIPT_TAG.search('<script src="app.js"></script>')
    assert SCRIPT_TAG.search("<script>alert(1)</script>")


def test_report_is_a_single_self_contained_file(cancer_result, tmp_path):
    out = write_report(cancer_result, tmp_path / "report.html", title="Breast cancer")
    assert out.exists()
    assert list(tmp_path.iterdir()) == [out], "no sidecar assets may be written"
    assert out.stat().st_size > 5_000


def test_report_inlines_the_stylesheet(cancer_result):
    html = render_report(cancer_result)
    assert "<style>" in html
    assert "--accent" in html, "theme custom properties must reach the document"
    assert "prefers-color-scheme: dark" in html, "the report must be theme-aware"


def test_curves_are_svg_paths_not_images(cancer_result):
    html = render_report(cancer_result)
    assert "<svg" in html
    assert re.search(r'<path d="M[\d.]+,[\d.]+', html), "curves must be SVG path data"
    assert "base64" not in html, "a rasterised chart is not a path"


def test_write_report_creates_missing_parents(cancer_result, tmp_path):
    out = write_report(cancer_result, tmp_path / "deep" / "nested" / "r.html")
    assert out.exists()


def test_write_report_overwrites(cancer_result, tmp_path):
    path = tmp_path / "r.html"
    path.write_text("stale", encoding="utf-8")
    write_report(cancer_result, path)
    assert path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


# --------------------------------------------------------------------------- #
# Panels
# --------------------------------------------------------------------------- #


def test_every_fitted_model_appears_in_the_comparison_table(cancer_result):
    html = render_report(cancer_result)
    for model in cancer_result.models:
        assert model.name in html
    assert "Model comparison" in html
    assert ">baseline<" in html, "the baseline must be labelled as such"


def test_verdict_names_the_best_model(cancer_result):
    html = render_report(cancer_result)
    assert "Verdict" in html
    assert cancer_result.best.name in html


def test_verdict_says_so_when_the_baseline_wins(cancer_result):
    """On breast_cancer the baseline is the best model — the report must not hide it."""
    assert cancer_result.best is cancer_result.baseline
    html = render_report(cancer_result)
    assert "ship the simple one" in html


def test_threshold_panel_appears_only_with_costs(cancer_result, cancer_frame):
    assert "Decision threshold" in render_report(cancer_result)

    no_costs = run_classification(
        cancer_frame, target="malignant", models=["logistic"], seed=RANDOM_STATE
    )
    assert "Decision threshold" not in render_report(no_costs)


def test_calibration_panel_reports_both_directions(cancer_result):
    html = render_report(cancer_result)
    assert "Calibration" in html
    assert "Brier" in html
    # Whichever way it went, the report must state it rather than imply success.
    assert ("Calibration improved" in html) or ("did not improve" in html)


def test_data_quality_panel_always_renders(cancer_result):
    html = render_report(cancer_result)
    assert "Data quality" in html


def test_data_quality_flags_undeclared_structure(cancer_result):
    """A random split on unstructured data is a warning, not a silence."""
    html = render_report(cancer_result)
    assert "No group or time structure was declared" in html


def test_data_quality_flags_severe_imbalance():
    rng = np.random.default_rng(RANDOM_STATE)
    n = 600
    frame = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)})
    frame["label"] = (rng.random(n) < 0.04).astype(int)
    result = run_classification(frame, target="label", models=["logistic"], seed=RANDOM_STATE)
    html = render_report(result)
    assert "Read PR-AUC, not ROC-AUC" in html


def test_skipped_models_are_disclosed(cancer_result):
    """A model that failed must be visible, not silently absent from the table."""
    cancer_result.skipped["fake_model"] = "ImportError: not installed"
    try:
        html = render_report(cancer_result)
        assert "Not run" in html
        assert "fake_model" in html
    finally:
        cancer_result.skipped.pop("fake_model")


def test_feature_importance_renders_for_a_linear_model(cancer_result):
    html = render_report(cancer_result)
    assert "Feature importance" in html


def test_metadata_reports_the_seed(cancer_result):
    html = render_report(cancer_result)
    assert f">{cancer_result.seed}<" in html


# --------------------------------------------------------------------------- #
# The other two families
# --------------------------------------------------------------------------- #


def test_clustering_result_renders(cluster_result, tmp_path):
    out = write_report(cluster_result, tmp_path / "c.html", title="Segments")
    html = out.read_text(encoding="utf-8")
    assert not EXTERNAL_REF.search(html)
    assert "unsupervised" in html
    assert "Silhouette" in html


def test_regression_result_renders(regression_result, tmp_path):
    out = write_report(regression_result, tmp_path / "p.html", title="Prediction")
    html = out.read_text(encoding="utf-8")
    assert not EXTERNAL_REF.search(html)
    assert "RMSE" in html
    assert "R²" in html


def test_empty_run_does_not_crash_the_report(cancer_result):
    """A run where every model failed still has to produce a readable page."""
    saved = cancer_result.models
    cancer_result.models = []
    try:
        html = render_report(cancer_result)
        assert "No model was fitted successfully" in html
        assert not EXTERNAL_REF.search(html)
    finally:
        cancer_result.models = saved


# --------------------------------------------------------------------------- #
# Chart primitives
# --------------------------------------------------------------------------- #


def test_curve_svg_draws_a_baseline_when_one_is_given():
    curve = CurvePoints(
        x=[0.0, 0.5, 1.0],
        y=[1.0, 0.6, 0.1],
        label="PR",
        x_label="recall",
        y_label="precision",
        baseline=0.05,
    )
    svg = curve_svg(curve)
    assert "chart-baseline" in svg
    assert svg.startswith("<svg")


def test_curve_svg_omits_the_baseline_when_there_is_none():
    curve = CurvePoints(x=[0.0, 1.0], y=[0.0, 1.0], label="ROC", x_label="fpr", y_label="tpr")
    assert "chart-baseline" not in curve_svg(curve)


def test_curve_svg_survives_an_empty_curve():
    empty = CurvePoints(x=[], y=[], label="none", x_label="x", y_label="y")
    svg = curve_svg(empty)
    assert "<svg" in svg
    assert "no points" in svg


def test_confusion_svg_scales_per_row_so_the_minority_stays_visible():
    """A global colour scale renders the minority row invisible — check it does not."""
    svg = confusion_svg([[9000, 10], [3, 7]], ["negative", "positive"])
    opacities = [float(v) for v in re.findall(r'fill-opacity="([\d.]+)"', svg)]
    assert len(opacities) == 4
    # The minority row's own maximum must reach full opacity, not 7/9000 of it.
    assert max(opacities[2:]) > 0.8


def test_confusion_svg_labels_both_axes():
    svg = confusion_svg([[1, 2], [3, 4]], ["no", "yes"])
    assert "predicted" in svg
    assert svg.count(">no<") >= 2


def test_bar_svg_caps_at_twelve_rows():
    labels = [f"feature_{i}" for i in range(30)]
    values = list(range(30, 0, -1))
    svg = bar_svg(labels, values, title="Importance")
    assert svg.count("chart-bar") == 12


def test_bar_svg_handles_an_empty_series():
    assert "nothing to chart" in bar_svg([], [], title="Importance")


def test_reliability_svg_draws_two_curves_when_given_two():
    before = CurvePoints(
        x=[0.1, 0.5, 0.9],
        y=[0.3, 0.5, 0.7],
        label="before",
        x_label="predicted",
        y_label="observed",
    )
    after = CurvePoints(
        x=[0.1, 0.5, 0.9],
        y=[0.11, 0.49, 0.88],
        label="after",
        x_label="predicted",
        y_label="observed",
    )
    svg = reliability_svg(before, after)
    assert "chart-line-muted" in svg
    assert 'class="chart-line"' in svg


def test_reliability_svg_draws_one_curve_when_calibration_was_not_applied():
    before = CurvePoints(
        x=[0.2, 0.8], y=[0.3, 0.7], label="before", x_label="predicted", y_label="observed"
    )
    svg = reliability_svg(before, None)
    assert "chart-line-muted" in svg


def test_all_svg_output_escapes_untrusted_text():
    """Column names come from a partner's CSV — they are not trusted markup."""
    svg = bar_svg(["<script>x</script>"], [1.0], title="Importance")
    assert "<script>" not in svg
    assert "&lt;" in svg
