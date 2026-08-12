"""Coefficient-significance bar charts for logistic regression models.

Adapted from a real production study's plotting code — genericized (dropped a
hardcoded "menstrual cycle phase" 2x3 subplot layout in favor of a plain N-model
grid). Functions return the Figure instead of calling plt.show(), so callers
can save, display, or embed them (e.g. in evals/reports/ style HTML output).
"""

from __future__ import annotations

import math

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle


def _plot_side(ax, coef_df: pd.DataFrame, title: str, color: str) -> None:
    """Draw one horizontal bar chart of coefficients on `ax`, shaded by
    significance (full opacity if p < 0.05, faded otherwise)."""
    features = coef_df.index.tolist()
    coefs = coef_df["coef"].tolist()
    p_values = coef_df["p"].tolist()
    y_pos = range(len(features))

    alphas = [1.0 if p < 0.05 else 0.3 for p in p_values]
    rgba_colors = [mcolors.to_rgba(color, alpha) for alpha in alphas]
    ax.barh(y_pos, coefs, align="center", color=rgba_colors)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(features)
    ax.invert_yaxis()  # labels read top-to-bottom
    ax.set_xlabel("Coefficient size")
    ax.set_title(title)

    for i, p in enumerate(p_values):
        if p < 0.05:
            ax.text(coefs[i], i, "*", ha="left" if coefs[i] > 0 else "right", va="center")


def plot_feature_importance(neg_coef_df: pd.DataFrame, pos_coef_df: pd.DataFrame) -> Figure:
    """Side-by-side bar charts of negative vs. positive coefficients, shaded by
    statistical significance. `neg_coef_df`/`pos_coef_df` come from
    `logit.split_by_direction()`."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    _plot_side(ax1, neg_coef_df, "Negative Coefficients", "green")
    _plot_side(ax2, pos_coef_df, "Positive Coefficients", "red")

    fig.suptitle("Feature Importance with Significance", fontsize=14)
    fig.legend(
        handles=[
            Rectangle((0, 0), 1, 1, fc=mcolors.to_rgba("red", 0.3)),
            Rectangle((0, 0), 1, 1, fc=mcolors.to_rgba("red", 1.0)),
            Rectangle((0, 0), 1, 1, fc=mcolors.to_rgba("green", 0.3)),
            Rectangle((0, 0), 1, 1, fc=mcolors.to_rgba("green", 1.0)),
        ],
        labels=[
            "Not significant",
            "Significant (p<0.05)",
            "Not significant",
            "Significant (p<0.05)",
        ],
        loc="lower center",
        ncol=2,
        bbox_to_anchor=(0.5, -0.1),
    )
    fig.tight_layout()
    return fig


def model_comparison_table(models: list, labels: list[str]) -> pd.DataFrame:
    """One row per model: pseudo R-squared, log-likelihood, AIC, and the
    selected feature set — useful for comparing RFE runs across subgroups/folds."""
    rows = []
    for model, label in zip(models, labels, strict=False):
        rows.append(
            {
                "label": label,
                "pseudo_r_squared": model.prsquared,
                "log_likelihood": model.llf,
                "aic": model.aic,
                "selected_features": ", ".join(model.model.exog_names[1:]),
            }
        )
    return pd.DataFrame(rows)


def plot_feature_importance_grid(models: list, titles: list[str]) -> Figure:
    """Feature-importance bar chart per model, arranged in a grid sized to fit
    however many models are passed (not hardcoded to any specific count)."""
    n = len(models)
    ncols = min(3, n)
    nrows = math.ceil(n / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows), squeeze=False)
    axs_flat = axs.flatten()

    for i, (model, title) in enumerate(zip(models, titles, strict=False)):
        coef = model.params[1:]
        p_values = model.pvalues[1:]
        features = model.model.exog_names[1:]
        order = sorted(range(len(coef)), key=lambda idx: abs(coef[idx]))

        sorted_features = [features[idx] for idx in order]
        sorted_coef = [coef[idx] for idx in order]
        sorted_p = [p_values[idx] for idx in order]
        colors = ["red" if c > 0 else "green" for c in sorted_coef]
        alphas = [1.0 if p < 0.05 else 0.3 for p in sorted_p]
        rgba_colors = [mcolors.to_rgba(c, a) for c, a in zip(colors, alphas, strict=False)]

        ax = axs_flat[i]
        ax.barh(range(len(sorted_features)), sorted_coef, color=rgba_colors)
        ax.set_yticks(range(len(sorted_features)))
        ax.set_yticklabels(sorted_features)
        ax.set_xlabel("Coefficient size")
        ax.set_title(title)

    for j in range(n, len(axs_flat)):
        axs_flat[j].axis("off")

    fig.suptitle("Feature Importance Across Models", fontsize=14)
    fig.tight_layout()
    return fig
