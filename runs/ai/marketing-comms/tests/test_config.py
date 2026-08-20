"""The deploy-hardening knobs: read from the environment, validated at load.

A budget knob with a typo in it must fail startup, not silently skip the loop
it was supposed to bound — the negative case is the load-bearing one.
"""

from __future__ import annotations

import pytest

from config import ConfigError, Settings


def test_hardening_knobs_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("GALACTUS_MAX_PDF_PAGES", "7")
    monkeypatch.setenv("GALACTUS_RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("GALACTUS_MAX_CONCURRENT_JOBS", "2")
    monkeypatch.setenv("GALACTUS_RETENTION_DAYS", "14")

    settings = Settings.load(use_dotenv=False)

    assert settings.max_pdf_pages == 7
    assert settings.rate_limit_per_minute == 3
    assert settings.max_concurrent_jobs == 2
    assert settings.retention_days == 14


def test_zero_disables_the_optional_guards(monkeypatch):
    monkeypatch.setenv("GALACTUS_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("GALACTUS_RETENTION_DAYS", "0")

    settings = Settings.load(use_dotenv=False)

    assert settings.rate_limit_per_minute == 0
    assert settings.retention_days == 0


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GALACTUS_MAX_PDF_PAGES", "0"),
        ("GALACTUS_MAX_PDF_PAGES", "-1"),
        ("GALACTUS_RATE_LIMIT_PER_MINUTE", "-1"),
        ("GALACTUS_MAX_CONCURRENT_JOBS", "0"),
        ("GALACTUS_RETENTION_DAYS", "-1"),
    ],
)
def test_invalid_budget_knobs_fail_at_load(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ConfigError):
        Settings.load(use_dotenv=False)


@pytest.mark.parametrize(
    "name",
    [
        "GALACTUS_MAX_PDF_PAGES",
        "GALACTUS_RATE_LIMIT_PER_MINUTE",
        "GALACTUS_MAX_CONCURRENT_JOBS",
        "GALACTUS_RETENTION_DAYS",
    ],
)
def test_non_integer_budget_knobs_fail_at_load(monkeypatch, name):
    monkeypatch.setenv(name, "many")

    with pytest.raises(ConfigError):
        Settings.load(use_dotenv=False)
