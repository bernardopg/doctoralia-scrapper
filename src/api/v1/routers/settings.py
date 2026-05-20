from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends

from src.api.schemas.settings import SettingsModel, SettingsResponse
from src.api.v1._state import is_masked_secret, mask_secret
from src.api.v1.deps import require_api_key
from src.api.v1.providers import get_app_config

router = APIRouter(tags=["Settings"])


def _is_http_url(value: Optional[str]) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _config_to_settings_model(config, *, mask_secrets: bool = False) -> SettingsModel:
    from src.api.schemas.settings import (
        APISettingsModel,
        DelaySettingsModel,
        FavoriteProfileModel,
        GenerationSettingsModel,
        IntegrationSettingsModel,
        PrivacySettingsModel,
        ScrapingSettingsModel,
        SecuritySettingsModel,
        TelegramSettingsModel,
        URLSettingsModel,
        UserProfileSettingsModel,
    )

    return SettingsModel(
        telegram=TelegramSettingsModel(
            enabled=config.telegram.enabled,
            token=(
                mask_secret(config.telegram.token)
                if mask_secrets
                else config.telegram.token
            ),
            chat_id=config.telegram.chat_id,
            parse_mode=config.telegram.parse_mode,
            attach_responses_auto=config.telegram.attach_responses_auto,
            attachment_format=config.telegram.attachment_format,
        ),
        scraping=ScrapingSettingsModel(
            headless=config.scraping.headless,
            timeout=config.scraping.timeout,
            delay_min=config.scraping.delay_min,
            delay_max=config.scraping.delay_max,
            max_retries=config.scraping.max_retries,
            page_load_timeout=config.scraping.page_load_timeout,
            implicit_wait=config.scraping.implicit_wait,
            explicit_wait=config.scraping.explicit_wait,
        ),
        delays=DelaySettingsModel(
            human_like_min=config.delays.human_like_min,
            human_like_max=config.delays.human_like_max,
            retry_base=config.delays.retry_base,
            error_recovery=config.delays.error_recovery,
            rate_limit_retry=config.delays.rate_limit_retry,
            page_load_retry=config.delays.page_load_retry,
        ),
        api=APISettingsModel(
            host=config.api.host,
            port=config.api.port,
            debug=config.api.debug,
            workers=config.api.workers,
        ),
        security=SecuritySettingsModel(
            api_key=(
                mask_secret(config.security.api_key)
                if mask_secrets
                else config.security.api_key
            ),
            webhook_signing_secret=(
                mask_secret(config.security.webhook_signing_secret)
                if mask_secrets
                else config.security.webhook_signing_secret
            ),
            openai_api_key=(
                mask_secret(config.security.openai_api_key)
                if mask_secrets
                else config.security.openai_api_key
            ),
        ),
        generation=GenerationSettingsModel(
            mode=config.generation.mode,
            openai_api_key=(
                mask_secret(config.generation.openai_api_key)
                if mask_secrets
                else config.generation.openai_api_key
            ),
            openai_model=config.generation.openai_model,
            gemini_api_key=(
                mask_secret(config.generation.gemini_api_key)
                if mask_secrets
                else config.generation.gemini_api_key
            ),
            gemini_model=config.generation.gemini_model,
            claude_api_key=(
                mask_secret(config.generation.claude_api_key)
                if mask_secrets
                else config.generation.claude_api_key
            ),
            claude_model=config.generation.claude_model,
            temperature=config.generation.temperature,
            max_tokens=config.generation.max_tokens,
            system_prompt=config.generation.system_prompt,
        ),
        integrations=IntegrationSettingsModel(
            redis_url=config.integrations.redis_url,
            selenium_remote_url=config.integrations.selenium_remote_url,
            api_url=config.integrations.api_url,
            api_public_url=config.integrations.api_public_url,
        ),
        privacy=PrivacySettingsModel(
            mask_pii=config.privacy.mask_pii,
            id_salt=(
                mask_secret(config.privacy.id_salt) or config.privacy.id_salt
                if mask_secrets
                else config.privacy.id_salt
            ),
            job_result_ttl=config.privacy.job_result_ttl,
            rate_limit_requests=config.privacy.rate_limit_requests,
            rate_limit_window=config.privacy.rate_limit_window,
            require_tls_callbacks=config.privacy.require_tls_callbacks,
            allowed_callback_domains=config.privacy.allowed_callback_domains,
        ),
        urls=URLSettingsModel(
            base_url=config.urls.base_url,
            profile_url=config.urls.profile_url,
        ),
        user_profile=UserProfileSettingsModel(
            display_name=config.user_profile.display_name,
            username=config.user_profile.username,
            favorite_profiles=[
                FavoriteProfileModel(
                    name=profile.name,
                    profile_url=profile.profile_url,
                    specialty=profile.specialty,
                    notes=profile.notes,
                )
                for profile in config.user_profile.favorite_profiles
            ],
        ),
    )


def _preserve_masked_settings(settings: SettingsModel, config) -> SettingsModel:
    if is_masked_secret(settings.telegram.token):
        settings.telegram.token = config.telegram.token
    if is_masked_secret(settings.security.api_key):
        settings.security.api_key = config.security.api_key
    if is_masked_secret(settings.security.webhook_signing_secret):
        settings.security.webhook_signing_secret = (
            config.security.webhook_signing_secret
        )
    if is_masked_secret(settings.security.openai_api_key):
        settings.security.openai_api_key = config.security.openai_api_key
    if is_masked_secret(settings.generation.openai_api_key):
        settings.generation.openai_api_key = config.generation.openai_api_key
    if is_masked_secret(settings.generation.gemini_api_key):
        settings.generation.gemini_api_key = config.generation.gemini_api_key
    if is_masked_secret(settings.generation.claude_api_key):
        settings.generation.claude_api_key = config.generation.claude_api_key
    if is_masked_secret(settings.privacy.id_salt):
        settings.privacy.id_salt = config.privacy.id_salt
    return settings


def _validate_settings(settings: SettingsModel) -> dict:
    from src.secure_config import ConfigValidator

    errors: list[str] = []
    valid_generation_modes = {"local", "openai", "gemini", "claude"}

    if settings.scraping.delay_min > settings.scraping.delay_max:
        errors.append("delay_min cannot be greater than delay_max")
    if settings.scraping.timeout < 10:
        errors.append("Timeout must be at least 10 seconds")
    if settings.scraping.max_retries < 1:
        errors.append("max_retries must be at least 1")
    if settings.api.port < 1024 or settings.api.port > 65535:
        errors.append("API port must be between 1024 and 65535")
    if settings.api.workers < 1:
        errors.append("Workers must be at least 1")
    if settings.delays.human_like_min > settings.delays.human_like_max:
        errors.append("human_like_min cannot be greater than human_like_max")
    if settings.telegram.token and not settings.telegram.chat_id:
        errors.append("chat_id is required when telegram token is provided")
    if settings.telegram.enabled and not ConfigValidator.validate_telegram_config(
        settings.telegram.token, settings.telegram.chat_id
    ):
        errors.append("Enabled Telegram requires a valid token and chat_id")
    if settings.telegram.parse_mode not in ("", "Markdown", "MarkdownV2", "HTML"):
        errors.append("Invalid parse_mode")
    if settings.telegram.attachment_format not in ("txt", "json", "csv"):
        errors.append("Invalid attachment_format")
    if settings.security.api_key and len(settings.security.api_key.strip()) < 8:
        errors.append("API key must be at least 8 characters long")
    if (
        settings.security.webhook_signing_secret
        and len(settings.security.webhook_signing_secret.strip()) < 8
    ):
        errors.append("Webhook signing secret must be at least 8 characters long")
    if (
        settings.security.openai_api_key
        and not settings.security.openai_api_key.startswith("sk-")
    ):
        errors.append("OpenAI API key must start with 'sk-'")
    if settings.generation.mode not in valid_generation_modes:
        errors.append("Generation mode must be local, openai, gemini or claude")
    if (
        settings.generation.openai_api_key
        and not settings.generation.openai_api_key.startswith("sk-")
    ):
        errors.append("Generation OpenAI API key must start with 'sk-'")
    if settings.generation.temperature < 0 or settings.generation.temperature > 1.5:
        errors.append("Generation temperature must be between 0 and 1.5")
    if settings.generation.max_tokens < 50 or settings.generation.max_tokens > 2000:
        errors.append("Generation max_tokens must be between 50 and 2000")
    if settings.generation.mode == "openai" and not settings.generation.openai_api_key:
        errors.append("OpenAI mode requires an OpenAI API key")
    if settings.generation.mode == "gemini" and not settings.generation.gemini_api_key:
        errors.append("Gemini mode requires a Gemini API key")
    if settings.generation.mode == "claude" and not settings.generation.claude_api_key:
        errors.append("Claude mode requires a Claude API key")
    if not settings.generation.openai_model.strip():
        errors.append("OpenAI model cannot be empty")
    if not settings.generation.gemini_model.strip():
        errors.append("Gemini model cannot be empty")
    if not settings.generation.claude_model.strip():
        errors.append("Claude model cannot be empty")
    if not settings.integrations.redis_url.startswith(("redis://", "rediss://")):
        errors.append("Redis URL must start with redis:// or rediss://")
    if not _is_http_url(settings.integrations.selenium_remote_url):
        errors.append("Selenium remote URL must be a valid HTTP(S) URL")
    if not _is_http_url(settings.integrations.api_url):
        errors.append("API URL must be a valid HTTP(S) URL")
    if not _is_http_url(settings.integrations.api_public_url):
        errors.append("API public URL must be a valid HTTP(S) URL")
    if settings.privacy.job_result_ttl < 60:
        errors.append("job_result_ttl must be at least 60 seconds")
    if settings.privacy.rate_limit_requests < 1:
        errors.append("rate_limit_requests must be at least 1")
    if settings.privacy.rate_limit_window < 1:
        errors.append("rate_limit_window must be at least 1 second")
    if any("://" in domain for domain in settings.privacy.allowed_callback_domains):
        errors.append(
            "allowed_callback_domains must contain domains only, without protocol"
        )
    if not _is_http_url(settings.urls.base_url):
        errors.append("Base URL must be a valid HTTP(S) URL")
    if not _is_http_url(settings.urls.profile_url):
        errors.append("Profile URL must be a valid HTTP(S) URL")
    if not settings.user_profile.display_name.strip():
        errors.append("Display name cannot be empty")
    if not settings.user_profile.username.strip():
        errors.append("Username cannot be empty")
    seen_profiles: set[str] = set()
    for favorite in settings.user_profile.favorite_profiles:
        if not favorite.name.strip():
            errors.append("Favorite profile name cannot be empty")
        if not _is_http_url(favorite.profile_url):
            errors.append("Favorite profile URL must be a valid HTTP(S) URL")
        normalized_url = favorite.profile_url.strip().lower()
        if normalized_url in seen_profiles:
            errors.append("Favorite profiles must not contain duplicate URLs")
        seen_profiles.add(normalized_url)

    return {"valid": len(errors) == 0, "errors": errors}


@router.get(
    "/v1/settings",
    response_model=SettingsResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_settings(config=Depends(get_app_config)):
    try:
        return SettingsResponse(
            success=True,
            message="Settings retrieved successfully",
            settings=_config_to_settings_model(config, mask_secrets=True),
        )
    except Exception as exc:
        return SettingsResponse(
            success=False,
            message=f"Failed to get settings: {exc}",
            settings=None,
        )


@router.put(
    "/v1/settings",
    response_model=SettingsResponse,
    dependencies=[Depends(require_api_key)],
)
async def update_settings(
    settings: SettingsModel,
    config=Depends(get_app_config),
):
    try:
        settings = _preserve_masked_settings(settings, config)
        validation = _validate_settings(settings)
        if not validation["valid"]:
            return SettingsResponse(
                success=False,
                message=f"Validation failed: {', '.join(validation['errors'])}",
                settings=None,
            )

        provided_sections = set(settings.model_fields_set)

        if "telegram" in provided_sections:
            config.telegram.enabled = settings.telegram.enabled
            config.telegram.token = settings.telegram.token
            config.telegram.chat_id = settings.telegram.chat_id
            config.telegram.parse_mode = settings.telegram.parse_mode
            config.telegram.attach_responses_auto = (
                settings.telegram.attach_responses_auto
            )
            config.telegram.attachment_format = settings.telegram.attachment_format

        if "scraping" in provided_sections:
            config.scraping.headless = settings.scraping.headless
            config.scraping.timeout = settings.scraping.timeout
            config.scraping.delay_min = settings.scraping.delay_min
            config.scraping.delay_max = settings.scraping.delay_max
            config.scraping.max_retries = settings.scraping.max_retries
            config.scraping.page_load_timeout = settings.scraping.page_load_timeout
            config.scraping.implicit_wait = settings.scraping.implicit_wait
            config.scraping.explicit_wait = settings.scraping.explicit_wait

        if "delays" in provided_sections:
            config.delays.human_like_min = settings.delays.human_like_min
            config.delays.human_like_max = settings.delays.human_like_max
            config.delays.retry_base = settings.delays.retry_base
            config.delays.error_recovery = settings.delays.error_recovery
            config.delays.rate_limit_retry = settings.delays.rate_limit_retry
            config.delays.page_load_retry = settings.delays.page_load_retry

        if "api" in provided_sections:
            config.api.host = settings.api.host
            config.api.port = settings.api.port
            config.api.debug = settings.api.debug
            config.api.workers = settings.api.workers

        if "security" in provided_sections:
            config.security.api_key = settings.security.api_key
            config.security.webhook_signing_secret = (
                settings.security.webhook_signing_secret
            )
            config.security.openai_api_key = settings.security.openai_api_key

        if "generation" in provided_sections:
            config.generation.mode = settings.generation.mode
            config.generation.openai_api_key = settings.generation.openai_api_key
            config.generation.openai_model = settings.generation.openai_model
            config.generation.gemini_api_key = settings.generation.gemini_api_key
            config.generation.gemini_model = settings.generation.gemini_model
            config.generation.claude_api_key = settings.generation.claude_api_key
            config.generation.claude_model = settings.generation.claude_model
            config.generation.temperature = settings.generation.temperature
            config.generation.max_tokens = settings.generation.max_tokens
            config.generation.system_prompt = settings.generation.system_prompt
            config.security.openai_api_key = settings.generation.openai_api_key

        if "integrations" in provided_sections:
            config.integrations.redis_url = settings.integrations.redis_url
            config.integrations.selenium_remote_url = (
                settings.integrations.selenium_remote_url
            )
            config.integrations.api_url = settings.integrations.api_url
            config.integrations.api_public_url = settings.integrations.api_public_url

        if "privacy" in provided_sections:
            config.privacy.mask_pii = settings.privacy.mask_pii
            config.privacy.id_salt = settings.privacy.id_salt
            config.privacy.job_result_ttl = settings.privacy.job_result_ttl
            config.privacy.rate_limit_requests = settings.privacy.rate_limit_requests
            config.privacy.rate_limit_window = settings.privacy.rate_limit_window
            config.privacy.require_tls_callbacks = (
                settings.privacy.require_tls_callbacks
            )
            config.privacy.allowed_callback_domains = [
                domain.strip()
                for domain in settings.privacy.allowed_callback_domains
                if domain.strip()
            ]

        if "urls" in provided_sections:
            config.urls.base_url = settings.urls.base_url
            config.urls.profile_url = settings.urls.profile_url

        if "user_profile" in provided_sections:
            from config.settings import FavoriteProfileConfig

            config.user_profile.display_name = settings.user_profile.display_name
            config.user_profile.username = settings.user_profile.username
            config.user_profile.favorite_profiles = [
                FavoriteProfileConfig(
                    name=favorite.name.strip(),
                    profile_url=favorite.profile_url.strip(),
                    specialty=favorite.specialty,
                    notes=favorite.notes,
                )
                for favorite in settings.user_profile.favorite_profiles
            ]

        config.save()

        return SettingsResponse(
            success=True,
            message="Settings updated successfully. Restart required for some changes to take effect.",
            settings=_config_to_settings_model(config, mask_secrets=True),
        )
    except Exception as exc:
        return SettingsResponse(
            success=False,
            message=f"Failed to update settings: {exc}",
            settings=None,
        )


@router.post(
    "/v1/settings/validate",
    response_model=SettingsResponse,
    dependencies=[Depends(require_api_key)],
)
async def validate_settings_endpoint(
    settings: SettingsModel,
    config=Depends(get_app_config),
):
    settings = _preserve_masked_settings(settings, config)
    validation = _validate_settings(settings)
    if validation["valid"]:
        return SettingsResponse(
            success=True,
            message="Settings are valid",
            settings=_config_to_settings_model(config, mask_secrets=True),
        )
    return SettingsResponse(
        success=False,
        message=f"Validation failed: {', '.join(validation['errors'])}",
        settings=None,
    )
