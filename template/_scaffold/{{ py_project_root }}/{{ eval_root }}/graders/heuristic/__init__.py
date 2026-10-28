"""Deterministic (free, offline) graders — one module per interaction metric.

Each module exposes ``grade(interaction) -> GraderResult | None`` (None when
the record carries no ground truth for that metric). Wired into pipelines via
graders/metrics_registry.py — add new metrics there, not by importing these
modules directly.
"""
