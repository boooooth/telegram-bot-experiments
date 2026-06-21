"""Shared test fixtures for config tests.

Ensures the three config env vars never leak from the real environment into a
test. Tests opt in to specific values via the `set_env` helper (which uses
pytest's monkeypatch so changes are auto-reverted after each test).
"""

import pytest

CONFIG_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "LLM_API_KEY", "LLM_MODEL")


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all three config env vars so each test starts from a blank slate."""
    for var in CONFIG_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture
def set_env(clean_env):
    """Return a setter that sets a config env var for the duration of one test."""

    def _set(name: str, value: str) -> None:
        clean_env.setenv(name, value)

    return _set
