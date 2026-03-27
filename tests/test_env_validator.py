from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.env_validator import EnvironmentValidationError, EnvironmentValidator


def _make_config():
    return SimpleNamespace(
        security=SimpleNamespace(
            api_key="config-api-key",
            webhook_signing_secret="config-webhook-secret",
            openai_api_key="sk-security-openai",
        ),
        integrations=SimpleNamespace(
            redis_url="redis://config-redis:6379/1",
            selenium_remote_url="http://selenium-config:4444/wd/hub",
            api_url="http://api-config:8000",
            api_public_url="https://public-config.example.com/api",
        ),
        privacy=SimpleNamespace(mask_pii=False),
        api=SimpleNamespace(debug=False),
        generation=SimpleNamespace(
            mode="openai",
            openai_api_key="sk-generation-openai",
            gemini_api_key="gemini-config-key",
            claude_api_key="claude-config-key",
        ),
    )


def test_get_config_fallback_reads_values_from_app_config():
    with patch("config.settings.AppConfig.load", return_value=_make_config()):
        assert EnvironmentValidator._get_config_fallback("API_KEY") == "config-api-key"
        assert (
            EnvironmentValidator._get_config_fallback("WEBHOOK_SIGNING_SECRET")
            == "config-webhook-secret"
        )
        assert (
            EnvironmentValidator._get_config_fallback("REDIS_URL")
            == "redis://config-redis:6379/1"
        )
        assert (
            EnvironmentValidator._get_config_fallback("OPENAI_API_KEY")
            == "sk-generation-openai"
        )
        assert EnvironmentValidator._get_config_fallback("MASK_PII") == "false"


def test_get_var_prefers_environment_over_config():
    with patch("config.settings.AppConfig.load", return_value=_make_config()):
        with patch.dict("os.environ", {"REDIS_URL": "redis://env-redis:6379/9"}):
            value = EnvironmentValidator._get_var("REDIS_URL")

    assert value == "redis://env-redis:6379/9"


def test_validate_for_service_raises_when_required_values_are_missing():
    with patch("config.settings.AppConfig.load", side_effect=RuntimeError("no config")):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(EnvironmentValidationError) as exc:
                EnvironmentValidator.validate_for_service("api")

    assert exc.value.missing_vars == ["API_KEY", "WEBHOOK_SIGNING_SECRET"]
    assert (
        "Service 'api' requires these environment variables." in exc.value.error_message
    )


def test_validate_for_service_loads_required_and_optional_values():
    env = {
        "API_KEY": "env-api-key",
        "WEBHOOK_SIGNING_SECRET": "env-webhook-secret",
    }
    with patch("config.settings.AppConfig.load", return_value=_make_config()):
        with patch.dict("os.environ", env, clear=True):
            loaded = EnvironmentValidator.validate_for_service("api")

    assert loaded["API_KEY"] == "env-api-key"
    assert loaded["WEBHOOK_SIGNING_SECRET"] == "env-webhook-secret"
    assert loaded["REDIS_URL"] == "redis://config-redis:6379/1"
    assert loaded["SELENIUM_REMOTE_URL"] == "http://selenium-config:4444/wd/hub"
    assert loaded["GEMINI_API_KEY"] == "gemini-config-key"
    assert loaded["ANTHROPIC_API_KEY"] == "claude-config-key"


def test_validate_all_collects_every_required_variable():
    env = {
        "API_KEY": "env-api-key",
        "WEBHOOK_SIGNING_SECRET": "env-webhook-secret",
        "REDIS_URL": "redis://env-redis:6379/0",
        "SELENIUM_REMOTE_URL": "http://selenium-env:4444/wd/hub",
    }
    with patch("config.settings.AppConfig.load", return_value=_make_config()):
        with patch.dict("os.environ", env, clear=True):
            loaded = EnvironmentValidator.validate_all()

    assert loaded["API_KEY"] == "env-api-key"
    assert loaded["REDIS_URL"] == "redis://env-redis:6379/0"
    assert loaded["API_PUBLIC_URL"] == "https://public-config.example.com/api"
    assert loaded["GENERATION_MODE"] == "openai"


def test_print_startup_validation_success_masks_sensitive_values(capsys):
    env = {
        "API_KEY": "1234567890",
        "WEBHOOK_SIGNING_SECRET": "abcdef123456",
    }
    with patch("config.settings.AppConfig.load", return_value=_make_config()):
        with patch.dict("os.environ", env, clear=True):
            EnvironmentValidator.print_startup_validation("api")

    out = capsys.readouterr().out
    assert "Environment Validation for API" in out
    assert "All required environment variables are set" in out
    assert "***7890" in out
    assert "***3456" in out


def test_print_startup_validation_failure_exits(capsys):
    with patch("config.settings.AppConfig.load", side_effect=RuntimeError("no config")):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(SystemExit) as exc:
                EnvironmentValidator.print_startup_validation("worker")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Environment validation failed" in out
    assert "Missing variables: REDIS_URL" in out
