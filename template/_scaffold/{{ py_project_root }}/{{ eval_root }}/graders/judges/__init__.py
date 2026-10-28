"""LLM-as-judge graders — one module per interaction metric, sharing base.LLMJudge.

Judges return a score plus written reasoning for each interaction; they run
only when ANTHROPIC_API_KEY is set and degrade to None (heuristic-only run)
otherwise. Wired into pipelines via graders/metrics_registry.py.
"""
