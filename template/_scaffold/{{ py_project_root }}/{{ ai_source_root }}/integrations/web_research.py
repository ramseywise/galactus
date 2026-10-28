"""Web research — autonomous research + report generation via GPT-Researcher.

Verified against ``gpt-researcher==0.15.1``'s real API. For structured,
interactive page-navigation tasks (filling forms, clicking through a funder's
site) rather than open-ended research-and-report generation, browser-use
(https://browser-use.com) is a complementary tool worth adding separately —
not bundled here, since it pulls in its own (and, checked directly, currently
conflicting) LLM/browser dependency tree for what's often only one of the two
needs, not both.

GPT-Researcher reads its own env vars directly (an LLM key plus a search
provider key, e.g. ``OPENAI_API_KEY`` + ``TAVILY_API_KEY`` by default) rather
than through this project's ``IntegrationSettings`` — see GPT-Researcher's own
docs for the full provider matrix; this module doesn't duplicate that
configuration surface.

KNOWN ISSUE (verified 2026-07-14): ``gpt-researcher``'s transitive ``spacy``
dependency has no wheel for Python 3.14 yet, so ``uv sync`` fails on a
3.14 interpreter (confirmed working on 3.12) — pin an older Python via
``.python-version`` if you hit this.
"""

from __future__ import annotations


async def research(query: str, report_type: str = "research_report") -> str:
    """Runs GPT-Researcher end-to-end (web search -> synthesis) and returns the
    generated report as markdown."""
    from gpt_researcher import GPTResearcher

    researcher = GPTResearcher(query=query, report_type=report_type)
    await researcher.conduct_research()
    return await researcher.write_report()
