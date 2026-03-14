import json
import os
from pathlib import Path
from unittest.mock import patch

import config.settings as settings_module
from config.settings import (
    APIConfig,
    AppConfig,
    DelayConfig,
    FavoriteProfileConfig,
    GenerationConfig,
    IntegrationConfig,
    PrivacyConfig,
    ScrapingConfig,
    SecurityConfig,
    TelegramConfig,
    URLConfig,
    UserProfileConfig,
)


class TestAppConfig:
    """Testes para a classe AppConfig"""

    def _build_config(self, base_dir: Path) -> AppConfig:
        return AppConfig(
            telegram=TelegramConfig(
                token="telegram-file-token",
                chat_id="123456",
                enabled=True,
                parse_mode="HTML",
                attach_responses_auto=False,
                attachment_format="json",
            ),
            scraping=ScrapingConfig(
                headless=False,
                timeout=90,
                delay_min=1.5,
                delay_max=3.5,
                max_retries=4,
                page_load_timeout=50,
                implicit_wait=15,
                explicit_wait=25,
            ),
            delays=DelayConfig(
                human_like_min=0.5,
                human_like_max=2.5,
                retry_base=3.0,
                error_recovery=12.0,
                rate_limit_retry=45.0,
                page_load_retry=6.0,
            ),
            api=APIConfig(host="0.0.0.0", port=8001, debug=True, workers=2),
            security=SecurityConfig(
                api_key="file-api-key-123",
                webhook_signing_secret="file-webhook-secret",
                openai_api_key="sk-file-openai-key",
            ),
            generation=GenerationConfig(
                mode="openai",
                openai_api_key="sk-generation-openai-key",
                openai_model="gpt-4.1-mini",
                gemini_api_key="gemini-secret",
                gemini_model="gemini-2.5-flash",
                claude_api_key="claude-secret",
                claude_model="claude-3-5-sonnet-latest",
                temperature=0.4,
                max_tokens=280,
                system_prompt="Seja objetivo e cordial.",
            ),
            integrations=IntegrationConfig(
                redis_url="redis://redis.internal:6379/1",
                selenium_remote_url="http://selenium.internal:4444/wd/hub",
                api_url="http://api.internal:8000",
                api_public_url="https://doctoralia.example.com/api",
            ),
            privacy=PrivacyConfig(
                mask_pii=False,
                id_salt="file-salt",
                job_result_ttl=7200,
                rate_limit_requests=25,
                rate_limit_window=120,
                require_tls_callbacks=False,
                allowed_callback_domains=["hooks.example.com", "n8n.example.com"],
            ),
            urls=URLConfig(
                base_url="https://www.doctoralia.com.br",
                profile_url="https://www.doctoralia.com.br/medico/teste",
            ),
            user_profile=UserProfileConfig(
                display_name="Dra. Ana",
                username="dra-ana",
                favorite_profiles=[
                    FavoriteProfileConfig(
                        name="Perfil principal",
                        profile_url="https://www.doctoralia.com.br/medico/teste",
                        specialty="Ginecologia",
                        notes="Responder primeiro",
                    )
                ],
            ),
            base_dir=base_dir,
            data_dir=base_dir / "data",
            logs_dir=base_dir / "data" / "logs",
        )

    def test_config_loading(self):
        """Testa se a configuração é carregada corretamente"""
        config = AppConfig.load()
        assert config is not None
        assert hasattr(config, "telegram")
        assert hasattr(config, "scraping")
        assert hasattr(config, "security")
        assert hasattr(config, "integrations")
        assert hasattr(config, "privacy")
        assert hasattr(config, "delays")
        assert hasattr(config, "urls")

    def test_config_file_exists(self):
        """Verifica se o arquivo de configuração existe"""
        config_path = Path("config/config.json")
        assert config_path.exists() or Path("config/config.example.json").exists()

    def test_config_json_format(self):
        """Verifica se o arquivo de configuração está em formato JSON válido"""
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert isinstance(data, dict)

    def test_environment_variables(self):
        """Testa se as variáveis de ambiente necessárias podem ser definidas"""
        # Testa se podemos definir uma variável de ambiente
        test_var = "TEST_TELEGRAM_TOKEN"
        test_value = "test_token_123"

        os.environ[test_var] = test_value
        assert os.environ.get(test_var) == test_value

        # Limpa a variável de teste
        del os.environ[test_var]

    def test_save_persists_extended_settings_sections(self, tmp_path):
        """Salva todas as novas seções da tela de settings no config.json."""
        config = self._build_config(tmp_path)

        config.save()

        saved_file = tmp_path / "config" / "config.json"
        saved_data = json.loads(saved_file.read_text(encoding="utf-8"))

        assert saved_data["telegram"]["enabled"] is True
        assert saved_data["telegram"]["attachment_format"] == "json"
        assert saved_data["delays"]["human_like_min"] == 0.5
        assert saved_data["security"]["api_key"] == "file-api-key-123"
        assert saved_data["generation"]["mode"] == "openai"
        assert saved_data["generation"]["gemini_api_key"] == "gemini-secret"
        assert (
            saved_data["integrations"]["selenium_remote_url"]
            == "http://selenium.internal:4444/wd/hub"
        )
        assert saved_data["privacy"]["allowed_callback_domains"] == [
            "hooks.example.com",
            "n8n.example.com",
        ]
        assert (
            saved_data["urls"]["profile_url"]
            == "https://www.doctoralia.com.br/medico/teste"
        )
        assert saved_data["user_profile"]["display_name"] == "Dra. Ana"
        assert len(saved_data["user_profile"]["favorite_profiles"]) == 1

    def test_load_reads_extended_settings_sections(self, tmp_path):
        """Carrega segredos, integrações, privacidade, delays e URLs do arquivo."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        (tmp_path / "data" / "logs").mkdir(parents=True)

        source_config = self._build_config(tmp_path)
        config_payload = {
            "telegram": {
                "token": source_config.telegram.token,
                "chat_id": source_config.telegram.chat_id,
                "enabled": source_config.telegram.enabled,
                "parse_mode": source_config.telegram.parse_mode,
                "attach_responses_auto": source_config.telegram.attach_responses_auto,
                "attachment_format": source_config.telegram.attachment_format,
            },
            "scraping": {
                "headless": source_config.scraping.headless,
                "timeout": source_config.scraping.timeout,
                "delay_min": source_config.scraping.delay_min,
                "delay_max": source_config.scraping.delay_max,
                "max_retries": source_config.scraping.max_retries,
                "page_load_timeout": source_config.scraping.page_load_timeout,
                "implicit_wait": source_config.scraping.implicit_wait,
                "explicit_wait": source_config.scraping.explicit_wait,
            },
            "delays": {
                "human_like_min": source_config.delays.human_like_min,
                "human_like_max": source_config.delays.human_like_max,
                "retry_base": source_config.delays.retry_base,
                "error_recovery": source_config.delays.error_recovery,
                "rate_limit_retry": source_config.delays.rate_limit_retry,
                "page_load_retry": source_config.delays.page_load_retry,
            },
            "api": {
                "host": source_config.api.host,
                "port": source_config.api.port,
                "debug": source_config.api.debug,
                "workers": source_config.api.workers,
            },
            "security": {
                "api_key": source_config.security.api_key,
                "webhook_signing_secret": source_config.security.webhook_signing_secret,
                "openai_api_key": source_config.security.openai_api_key,
            },
            "generation": {
                "mode": source_config.generation.mode,
                "openai_api_key": source_config.generation.openai_api_key,
                "openai_model": source_config.generation.openai_model,
                "gemini_api_key": source_config.generation.gemini_api_key,
                "gemini_model": source_config.generation.gemini_model,
                "claude_api_key": source_config.generation.claude_api_key,
                "claude_model": source_config.generation.claude_model,
                "temperature": source_config.generation.temperature,
                "max_tokens": source_config.generation.max_tokens,
                "system_prompt": source_config.generation.system_prompt,
            },
            "integrations": {
                "redis_url": source_config.integrations.redis_url,
                "selenium_remote_url": source_config.integrations.selenium_remote_url,
                "api_url": source_config.integrations.api_url,
                "api_public_url": source_config.integrations.api_public_url,
            },
            "privacy": {
                "mask_pii": source_config.privacy.mask_pii,
                "id_salt": source_config.privacy.id_salt,
                "job_result_ttl": source_config.privacy.job_result_ttl,
                "rate_limit_requests": source_config.privacy.rate_limit_requests,
                "rate_limit_window": source_config.privacy.rate_limit_window,
                "require_tls_callbacks": source_config.privacy.require_tls_callbacks,
                "allowed_callback_domains": source_config.privacy.allowed_callback_domains,
            },
            "urls": {
                "base_url": source_config.urls.base_url,
                "profile_url": source_config.urls.profile_url,
            },
            "user_profile": {
                "display_name": source_config.user_profile.display_name,
                "username": source_config.user_profile.username,
                "favorite_profiles": [
                    {
                        "name": favorite.name,
                        "profile_url": favorite.profile_url,
                        "specialty": favorite.specialty,
                        "notes": favorite.notes,
                    }
                    for favorite in source_config.user_profile.favorite_profiles
                ],
            },
        }
        (config_dir / "config.json").write_text(
            json.dumps(config_payload), encoding="utf-8"
        )

        fake_settings_file = tmp_path / "config" / "settings.py"
        env_overrides = {
            "API_KEY": "env-api-key",
            "WEBHOOK_SIGNING_SECRET": "env-webhook-secret",
            "OPENAI_API_KEY": "sk-env-openai-key",
            "REDIS_URL": "redis://env-redis:6379/0",
            "SELENIUM_REMOTE_URL": "http://env-selenium:4444/wd/hub",
            "API_URL": "http://env-api:8000",
            "API_PUBLIC_URL": "https://env.example.com/api",
            "MASK_PII": "true",
            "ID_SALT": "env-salt",
            "ALLOWED_CALLBACK_DOMAINS": "env.example.com",
        }

        with patch.object(settings_module, "__file__", str(fake_settings_file)):
            with patch.dict(os.environ, env_overrides, clear=False):
                loaded = AppConfig.load()

        assert loaded.telegram.enabled is True
        assert loaded.telegram.parse_mode == "HTML"
        assert loaded.security.api_key == "file-api-key-123"
        assert loaded.security.openai_api_key == "sk-file-openai-key"
        assert loaded.generation.mode == "openai"
        assert loaded.generation.gemini_api_key == "gemini-secret"
        assert loaded.integrations.redis_url == "redis://redis.internal:6379/1"
        assert (
            loaded.integrations.api_public_url == "https://doctoralia.example.com/api"
        )
        assert loaded.privacy.mask_pii is False
        assert loaded.privacy.allowed_callback_domains == [
            "hooks.example.com",
            "n8n.example.com",
        ]
        assert loaded.delays.retry_base == 3.0
        assert loaded.urls.profile_url == "https://www.doctoralia.com.br/medico/teste"
        assert loaded.user_profile.display_name == "Dra. Ana"
        assert loaded.user_profile.favorite_profiles[0].notes == "Responder primeiro"
