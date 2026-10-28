"""Reporting — a `RunResult` becomes one HTML file with no external references.

The output is the deliverable a nonprofit partner actually receives, so it is
built to survive being emailed, archived, and opened offline years later:
inlined CSS, inline SVG charts, no scripts, no CDN.
"""

from __future__ import annotations

from ml.reporting.charts import bar_svg, confusion_svg, curve_svg, reliability_svg
from ml.reporting.html import render_report, write_report

__all__ = [
    "bar_svg",
    "confusion_svg",
    "curve_svg",
    "reliability_svg",
    "render_report",
    "write_report",
]
