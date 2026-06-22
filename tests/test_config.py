"""Wave 0 unit tests for the fail-fast config loader (bot/config.py).

Locks the Phase 1 boot acceptance criterion: the bot refuses to start when the
Telegram token or LLM key is missing, and LLM_MODEL defaults to
gpt-4o-mini (LLM-01).
"""

import pytest

from bot.config import ConfigError, Settings, load_settings


def test_missing_both_required_vars_raises_naming_both(clean_env):
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    message = str(excinfo.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "LLM_API_KEY" in message


def test_missing_only_openai_key_raises_naming_only_it(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    message = str(excinfo.value)
    assert "LLM_API_KEY" in message
    assert "TELEGRAM_BOT_TOKEN" not in message


def test_model_defaults_to_gpt_4o_mini_when_unset(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("LLM_API_KEY", "sk-key")
    settings = load_settings()
    assert isinstance(settings, Settings)
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.telegram_bot_token == "tg-token"
    assert settings.llm_api_key == "sk-key"


def test_model_env_override_is_respected(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("LLM_API_KEY", "sk-key")
    set_env("LLM_MODEL", "gpt-4o")
    settings = load_settings()
    assert settings.llm_model == "gpt-4o"


def test_blank_token_treated_as_missing(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "   ")
    set_env("LLM_API_KEY", "sk-key")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    assert "TELEGRAM_BOT_TOKEN" in str(excinfo.value)


def test_blank_llm_api_key_treated_as_missing(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("LLM_API_KEY", "   ")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    assert "LLM_API_KEY" in str(excinfo.value)


def test_allowed_user_ids_parsed_correctly(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("LLM_API_KEY", "sk-key")
    set_env("ALLOWED_USER_IDS", "444, 555")
    settings = load_settings()
    assert settings.allowed_user_ids == frozenset({444, 555})


def test_empty_allowed_ids_defaults_to_open_access(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("LLM_API_KEY", "sk-key")
    settings = load_settings()
    assert settings.allowed_user_ids == frozenset()


def test_invalid_allowed_user_ids_raises_config_error(set_env):
    set_env("TELEGRAM_BOT_TOKEN", "tg-token")
    set_env("LLM_API_KEY", "sk-key")
    set_env("ALLOWED_USER_IDS", "111,abc,333")
    with pytest.raises(ConfigError) as excinfo:
        load_settings()
    assert "ALLOWED_USER_IDS" in str(excinfo.value)
