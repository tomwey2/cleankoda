"""Tests for EnvironmentSettings configuration parsing."""

import pytest

from app.core.environment_settings import EnvironmentSettings


@pytest.fixture()
def minimal_env(monkeypatch):
    """Provide the required environment variables for EnvironmentSettings."""

    base_env = {
        "ENCRYPTION_KEY": "test-key",
        "WORKSPACE": "/tmp/workspace",
    }
    with monkeypatch.context() as mpatch:
        for key, value in base_env.items():
            mpatch.setenv(key, value)
        yield mpatch


def test_from_env_uses_default_llm_timeout(minimal_env):
    """Default LLM timeout should be 180 seconds when not overridden."""

    settings = EnvironmentSettings.from_env()

    assert settings.llm_request_timeout_seconds == 180.0


def test_from_env_reads_custom_llm_timeout(minimal_env):
    """LLM timeout should honor the LLM_REQUEST_TIMEOUT_SECONDS env value."""

    minimal_env.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "45")

    settings = EnvironmentSettings.from_env()

    assert settings.llm_request_timeout_seconds == 45.0


def test_from_env_raises_on_invalid_timeout_value(minimal_env):
    """Invalid LLM_REQUEST_TIMEOUT_SECONDS should raise clear ValueError."""

    minimal_env.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "invalid")

    with pytest.raises(ValueError, match="Invalid LLM_REQUEST_TIMEOUT_SECONDS value"):
        EnvironmentSettings.from_env()


def test_from_env_raises_on_invalid_rate_limit_value(minimal_env):
    """Invalid LLM_CALLS_PER_SECOND should raise clear ValueError."""

    minimal_env.setenv("LLM_CALLS_PER_SECOND", "not_a_number")

    with pytest.raises(ValueError, match="Invalid LLM_CALLS_PER_SECOND value"):
        EnvironmentSettings.from_env()
