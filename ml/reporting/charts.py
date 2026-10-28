"""Inline SVG chart primitives.

Every chart here is a string of SVG markup with no external reference — no
matplotlib PNG to write next to the HTML, no CDN script to fetch at open time.
That constraint is the whole point of the module: a report that a nonprofit
partner can be emailed, opened on a plane, and still read in full three years
from now, when whatever CDN it depended on has changed hands.

Colours come from CSS custom properties (`var(--accent)`), not literals, so the
same SVG renders correctly in both themes without being drawn twice.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from ml.evaluation.metrics import CurvePoints

# A fixed viewBox with `preserveAspectRatio` off means the browser scales the
# drawing to whatever width the CSS gives it. Nothing here is in pixels.
WIDTH = 320.0
HEIGHT = 240.0
PAD_LEFT = 44.0
PAD_BOTTOM = 34.0
PAD_TOP = 14.0
PAD_RIGHT = 14.0

PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT
PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM


def _project(
    x: float, y: float, *, x_min: float, x_max: float, y_min: float, y_max: float
) -> tuple[float, float]:
    """Data coordinates to SVG coordinates, with the y axis flipped."""
    x_span = x_max - x_min or 1.0
    y_span = y_max - y_min or 1.0
    px = PAD_LEFT + (x - x_min) / x_span * PLOT_W
    py = PAD_TOP + PLOT_H - (y - y_min) / y_span * PLOT_H
    return round(px, 2), round(py, 2)


def _axes(x_label: str, y_label: str, *, ticks: Sequence[float] = (0.0, 0.5, 1.0)) -> str:
    """The frame, gridlines, and tick labels shared by every unit-square chart."""
    parts = [
        f'<rect x="{PAD_LEFT}" y="{PAD_TOP}" width="{PLOT_W}" height="{PLOT_H}" '
        'class="chart-frame" />'
    ]
    for tick in ticks:
        px, _ = _project(tick, 0.0, x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0)
        _, py = _project(0.0, tick, x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0)
        parts.append(
            f'<line x1="{px}" y1="{PAD_TOP}" x2="{px}" y2="{PAD_TOP + PLOT_H}" '
            'class="chart-grid" />'
        )
        parts.append(
            f'<line x1="{PAD_LEFT}" y1="{py}" x2="{PAD_LEFT + PLOT_W}" y2="{py}" '
            'class="chart-grid" />'
        )
        parts.append(
            f'<text x="{px}" y="{PAD_TOP + PLOT_H + 14}" class="chart-tick" '
            f'text-anchor="middle">{tick:g}</text>'
        )
        parts.append(
            f'<text x="{PAD_LEFT - 6}" y="{py + 3.5}" class="chart-tick" '
            f'text-anchor="end">{tick:g}</text>'
        )
    parts.append(
        f'<text x="{PAD_LEFT + PLOT_W / 2}" y="{HEIGHT - 4}" class="chart-axis" '
        f'text-anchor="middle">{escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="11" y="{PAD_TOP + PLOT_H / 2}" class="chart-axis" text-anchor="middle" '
        f'transform="rotate(-90 11 {PAD_TOP + PLOT_H / 2})">{escape(y_label)}</text>'
    )
    return "".join(parts)


def _svg(body: str, *, title: str) -> str:
    return (
        f'<svg class="chart" viewBox="0 0 {WIDTH:g} {HEIGHT:g}" role="img" '
        f'aria-label="{escape(title)}" xmlns="http://www.w3.org/2000/svg">{body}</svg>'
    )


def curve_svg(curve: CurvePoints, *, title: str | None = None) -> str:
    """One `CurvePoints` as an SVG path, with its no-skill baseline dashed.

    The baseline is drawn because a PR curve without one is unreadable: at 5%
    prevalence, an average precision of 0.30 is a six-fold lift, and at 50%
    prevalence the same number is worse than guessing. The dashed line is what
    makes those two pictures look different.
    """
    if not curve.x or not curve.y:
        return _empty("no points to plot", title=title or curve.label)

    x_min, x_max = min(curve.x), max(curve.x)
    y_min, y_max = min(min(curve.y), 0.0), max(max(curve.y), 1.0)
    x_min, x_max = min(x_min, 0.0), max(x_max, 1.0)

    points = [
        _project(x, y, x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)
        for x, y in zip(curve.x, curve.y, strict=True)
    ]
    path = "M" + " L".join(f"{px},{py}" for px, py in points)

    body = [_axes(curve.x_label, curve.y_label)]
    if curve.baseline is not None:
        _, base_y = _project(
            0.0, curve.baseline, x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max
        )
        body.append(
            f'<line x1="{PAD_LEFT}" y1="{base_y}" x2="{PAD_LEFT + PLOT_W}" y2="{base_y}" '
            'class="chart-baseline" />'
        )
    body.append(f'<path d="{path}" class="chart-line" />')
    return _svg("".join(body), title=title or curve.label)


def reliability_svg(before: CurvePoints, after: CurvePoints | None = None) -> str:
    """A calibration plot: predicted probability against observed frequency.

    The diagonal is perfect calibration. Two curves are drawn when calibration
    was actually applied, because the useful question is not "is it calibrated"
    but "did calibrating it help" — and the answer is sometimes no.
    """
    if not before.x:
        return _empty("no calibration data", title="Reliability")

    body = [_axes(before.x_label, before.y_label)]
    p0 = _project(0.0, 0.0, x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0)
    p1 = _project(1.0, 1.0, x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0)
    body.append(
        f'<line x1="{p0[0]}" y1="{p0[1]}" x2="{p1[0]}" y2="{p1[1]}" class="chart-baseline" />'
    )

    for curve, css in ((before, "chart-line-muted"), (after, "chart-line")):
        if curve is None or not curve.x:
            continue
        points = [
            _project(x, y, x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0)
            for x, y in zip(curve.x, curve.y, strict=True)
        ]
        path = "M" + " L".join(f"{px},{py}" for px, py in points)
        body.append(f'<path d="{path}" class="{css}" />')
        body.append(
            "".join(
                f'<circle cx="{px}" cy="{py}" r="2.5" class="{css}-dot" />' for px, py in points
            )
        )

    return _svg("".join(body), title="Reliability diagram")


def bar_svg(labels: Sequence[str], values: Sequence[float], *, title: str) -> str:
    """A horizontal bar chart — feature importance, class balance, sweeps.

    Horizontal because the labels are column names, and column names are wide.
    """
    if not labels:
        return _empty("nothing to chart", title=title)

    rows = list(zip(labels, values, strict=True))[:12]
    span = max((abs(v) for _, v in rows), default=1.0) or 1.0
    row_h = PLOT_H / len(rows)
    body = []
    for i, (label, value) in enumerate(rows):
        width = max(abs(value) / span * (PLOT_W - 4), 0.5)
        y = PAD_TOP + i * row_h + row_h * 0.18
        height = max(row_h * 0.64, 1.0)
        body.append(
            f'<rect x="{PAD_LEFT}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
            'class="chart-bar" />'
        )
        body.append(
            f'<text x="{PAD_LEFT - 4}" y="{y + height / 2 + 3:.2f}" class="chart-tick" '
            f'text-anchor="end">{escape(_truncate(str(label)))}</text>'
        )
        body.append(
            f'<text x="{PAD_LEFT + width + 4:.2f}" y="{y + height / 2 + 3:.2f}" '
            f'class="chart-tick">{value:.3g}</text>'
        )
    return _svg("".join(body), title=title)


def confusion_svg(matrix: Sequence[Sequence[int]], labels: Sequence[str]) -> str:
    """The confusion matrix as a shaded grid.

    Cell opacity is scaled by row, not by the global maximum. Under imbalance a
    global scale renders the entire minority row invisible — which is precisely
    the row anyone reads a confusion matrix to see.
    """
    if not matrix or not matrix[0]:
        return _empty("no confusion matrix", title="Confusion matrix")

    n = len(matrix)
    cell = min(PLOT_W, PLOT_H) / n
    origin_x = PAD_LEFT
    origin_y = PAD_TOP
    body = []
    for i, row in enumerate(matrix):
        row_max = max(row) or 1
        for j, count in enumerate(row):
            x = origin_x + j * cell
            y = origin_y + i * cell
            opacity = round(0.12 + 0.78 * (count / row_max), 3)
            body.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" '
                f'class="chart-cell" fill-opacity="{opacity}" />'
            )
            body.append(
                f'<text x="{x + cell / 2:.2f}" y="{y + cell / 2 + 4:.2f}" '
                f'class="chart-cell-text" text-anchor="middle">{count}</text>'
            )
    for i, label in enumerate(labels[:n]):
        body.append(
            f'<text x="{origin_x - 5}" y="{origin_y + i * cell + cell / 2 + 3:.2f}" '
            f'class="chart-tick" text-anchor="end">{escape(_truncate(str(label), 9))}</text>'
        )
        body.append(
            f'<text x="{origin_x + i * cell + cell / 2:.2f}" '
            f'y="{origin_y + n * cell + 13:.2f}" class="chart-tick" '
            f'text-anchor="middle">{escape(_truncate(str(label), 9))}</text>'
        )
    body.append(
        f'<text x="{origin_x + (n * cell) / 2:.2f}" y="{HEIGHT - 4}" class="chart-axis" '
        'text-anchor="middle">predicted</text>'
    )
    return _svg("".join(body), title="Confusion matrix")


def _empty(message: str, *, title: str) -> str:
    body = (
        f'<text x="{WIDTH / 2}" y="{HEIGHT / 2}" class="chart-empty" '
        f'text-anchor="middle">{escape(message)}</text>'
    )
    return _svg(body, title=title)


def _truncate(text: str, limit: int = 14) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
