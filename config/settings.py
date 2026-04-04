import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _coerce_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _env_first(*names: str) -> Optional[str]:
    for name in names:
        value = _clean_optional(os.getenv(name))
        if value:
            return value
    return None


def _normalize_favorite_profiles(value: object) -> List["FavoriteProfileConfig"]:
    profiles: List[FavoriteProfileConfig] = []
    if not isinstance(value, list):
        return profiles

    for item in value:
        if not isinstance(item, dict):
            continue
        profile_url = _clean_optional(item.get("profile_url"))
        if not profile_url:
            continue
        profiles.append(
            FavoriteProfileConfig(
                name=str(item.get("name") or "Perfil favorito").strip(),
                profile_url=profile_url,
                specialty=_clean_optional(item.get("specialty")),
                notes=_clean_optional(item.get("notes")),
            )
        )

    return profiles


@dataclass
class TelegramConfig:
    token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: bool = False
    # New customization options
    parse_mode: str = "Markdown"  # Options: "Markdown", "MarkdownV2", "HTML", ""
    attach_responses_auto: bool = True  # Auto-anexar arquivo de respostas quando houver
    attachment_format: str = "txt"  # "txt" | "json" | "csv"


@dataclass
class DelayConfig:
    """Configurações de delays para evitar detecção"""

    human_like_min: float = 1.0
    human_like_max: float = 3.0
    retry_base: float = 2.0
    error_recovery: float = 10.0
    rate_limit_retry: float = 60.0
    page_load_retry: float = 5.0


@dataclass
class APIConfig:
    """Configurações da API REST"""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    workers: int = 1


@dataclass
class ScrapingConfig:
    headless: bool = True
    timeout: int = 60
    delay_min: float = 2.0
    delay_max: float = 4.0
    max_retries: int = 5
    page_load_timeout: int = 45
    implicit_wait: int = 20
    explicit_wait: int = 30


@dataclass
class SecurityConfig:
    api_key: Optional[str] = None
    webhook_signing_secret: Optional[str] = None
    openai_api_key: Optional[str] = None
    dashboard_auth_enabled: bool = True
    dashboard_password_hash: Optional[str] = None
    dashboard_session_secret: Optional[str] = None
    dashboard_session_ttl_minutes: int = 480


@dataclass
class GenerationConfig:
    mode: str = "local"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4.1-mini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    claude_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-latest"
    temperature: float = 0.35
    max_tokens: int = 300
    system_prompt: Optional[str] = None


@dataclass
class IntegrationConfig:
    redis_url: str = "redis://localhost:6379/0"
    selenium_remote_url: str = "http://localhost:4444/wd/hub"
    api_url: Optional[str] = None
    api_public_url: Optional[str] = None


@dataclass
class PrivacyConfig:
    mask_pii: bool = True
    id_salt: str = "default-salt"
    job_result_ttl: int = 3600
    rate_limit_requests: int = 10
    rate_limit_window: int = 60
    require_tls_callbacks: bool = True
    allowed_callback_domains: List[str] = field(default_factory=list)


@dataclass
class URLConfig:
    base_url: str = "https://www.doctoralia.com.br"
    profile_url: Optional[str] = None


@dataclass
class FavoriteProfileConfig:
    name: str
    profile_url: str
    specialty: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class UserProfileConfig:
    display_name: str = "Administrador"
    username: str = "admin"
    favorite_profiles: List[FavoriteProfileConfig] = field(default_factory=list)


@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    scraping: ScrapingConfig = field(default_factory=ScrapingConfig)
    delays: DelayConfig = field(default_factory=DelayConfig)
    api: APIConfig = field(default_factory=APIConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    integrations: IntegrationConfig = field(default_factory=IntegrationConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    urls: URLConfig = field(default_factory=URLConfig)
    base_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )
    data_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data"
    )
    logs_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "logs"
    )
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    user_profile: UserProfileConfig = field(default_factory=UserProfileConfig)

    @classmethod
    def load(cls) -> "AppConfig":
        base_dir = Path(__file__).parent.parent
        config_file = base_dir / "config" / "config.json"

        # Valores padrão
        telegram = TelegramConfig()
        scraping = ScrapingConfig()
        delays = DelayConfig()
        api = APIConfig()
        security = SecurityConfig(
            api_key=_clean_optional(os.getenv("API_KEY")),
            webhook_signing_secret=_clean_optional(os.getenv("WEBHOOK_SIGNING_SECRET")),
            openai_api_key=_clean_optional(os.getenv("OPENAI_API_KEY")),
            dashboard_auth_enabled=_env_bool("DASHBOARD_AUTH_ENABLED", True),
            dashboard_password_hash=_clean_optional(
                os.getenv("DASHBOARD_PASSWORD_HASH")
            ),
            dashboard_session_secret=_clean_optional(
                os.getenv("DASHBOARD_SESSION_SECRET")
            ),
            dashboard_session_ttl_minutes=int(
                os.getenv("DASHBOARD_SESSION_TTL_MINUTES", "480")
            ),
        )
        generation = GenerationConfig(
            mode=_clean_optional(os.getenv("GENERATION_MODE")) or "local",
            openai_api_key=_env_first("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            gemini_api_key=_env_first("GEMINI_API_KEY", "GOOGLE_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            claude_api_key=_env_first("CLAUDE_API_KEY", "ANTHROPIC_API_KEY"),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest"),
            temperature=float(os.getenv("GENERATION_TEMPERATURE", "0.35")),
            max_tokens=int(os.getenv("GENERATION_MAX_TOKENS", "300")),
            system_prompt=_clean_optional(os.getenv("GENERATION_SYSTEM_PROMPT")),
        )
        integrations = IntegrationConfig(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            selenium_remote_url=os.getenv(
                "SELENIUM_REMOTE_URL", "http://localhost:4444/wd/hub"
            ),
            api_url=_clean_optional(os.getenv("API_URL")),
            api_public_url=_clean_optional(os.getenv("API_PUBLIC_URL")),
        )
        privacy = PrivacyConfig(
            mask_pii=_env_bool("MASK_PII", True),
            id_salt=os.getenv("ID_SALT", "default-salt"),
            job_result_ttl=int(os.getenv("JOB_RESULT_TTL", "3600")),
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "10")),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
            require_tls_callbacks=_env_bool("REQUIRE_TLS_CALLBACKS", True),
            allowed_callback_domains=_coerce_list(
                os.getenv("ALLOWED_CALLBACK_DOMAINS", "")
            ),
        )
        urls = URLConfig()
        user_profile = UserProfileConfig()

        # Carregar configurações se existir
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                tg_data = data.get("telegram", {})
                telegram_token = _clean_optional(
                    tg_data.get("token")
                    or os.getenv("TELEGRAM_TOKEN")
                    or os.getenv("TELEGRAM_BOT_TOKEN")
                )
                telegram_chat_id = _clean_optional(
                    tg_data.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID")
                )
                enabled_default = _env_bool(
                    "TELEGRAM_ENABLED", bool(telegram_token and telegram_chat_id)
                )
                telegram = TelegramConfig(
                    token=telegram_token,
                    chat_id=telegram_chat_id,
                    enabled=bool(tg_data.get("enabled", enabled_default)),
                    parse_mode=tg_data.get("parse_mode", "Markdown"),
                    attach_responses_auto=tg_data.get("attach_responses_auto", True),
                    attachment_format=tg_data.get("attachment_format", "txt"),
                )

                scraping_data = data.get("scraping", {})
                scraping = ScrapingConfig(
                    headless=scraping_data.get(
                        "headless", _env_bool("SCRAPER_HEADLESS", True)
                    ),
                    timeout=scraping_data.get("timeout", 60),
                    delay_min=scraping_data.get("delay_min", 2.0),
                    delay_max=scraping_data.get("delay_max", 4.0),
                    max_retries=scraping_data.get("max_retries", 5),
                    page_load_timeout=scraping_data.get("page_load_timeout", 45),
                    implicit_wait=scraping_data.get("implicit_wait", 20),
                    explicit_wait=scraping_data.get("explicit_wait", 30),
                )

                delay_data = data.get("delays", {})
                delays = DelayConfig(
                    human_like_min=delay_data.get(
                        "human_like_min", delays.human_like_min
                    ),
                    human_like_max=delay_data.get(
                        "human_like_max", delays.human_like_max
                    ),
                    retry_base=delay_data.get("retry_base", delays.retry_base),
                    error_recovery=delay_data.get(
                        "error_recovery", delays.error_recovery
                    ),
                    rate_limit_retry=delay_data.get(
                        "rate_limit_retry", delays.rate_limit_retry
                    ),
                    page_load_retry=delay_data.get(
                        "page_load_retry", delays.page_load_retry
                    ),
                )

                api_data = data.get("api", {})
                api = APIConfig(
                    host=api_data.get("host", "0.0.0.0"),
                    port=api_data.get("port", 8000),
                    debug=api_data.get("debug", _env_bool("DEBUG", False)),
                    workers=api_data.get("workers", 1),
                )

                security_data = data.get("security", {})
                security = SecurityConfig(
                    api_key=_clean_optional(
                        security_data.get("api_key") or os.getenv("API_KEY")
                    ),
                    webhook_signing_secret=_clean_optional(
                        security_data.get("webhook_signing_secret")
                        or os.getenv("WEBHOOK_SIGNING_SECRET")
                    ),
                    openai_api_key=_clean_optional(
                        security_data.get("openai_api_key")
                        or os.getenv("OPENAI_API_KEY")
                    ),
                    dashboard_auth_enabled=bool(
                        security_data.get(
                            "dashboard_auth_enabled",
                            _env_bool("DASHBOARD_AUTH_ENABLED", True),
                        )
                    ),
                    dashboard_password_hash=_clean_optional(
                        security_data.get("dashboard_password_hash")
                    ),
                    dashboard_session_secret=_clean_optional(
                        security_data.get("dashboard_session_secret")
                        or os.getenv("DASHBOARD_SESSION_SECRET")
                    ),
                    dashboard_session_ttl_minutes=int(
                        security_data.get(
                            "dashboard_session_ttl_minutes",
                            os.getenv("DASHBOARD_SESSION_TTL_MINUTES", "480"),
                        )
                    ),
                )

                generation_data = data.get("generation", {})
                generation = GenerationConfig(
                    mode=str(generation_data.get("mode", generation.mode) or "local"),
                    openai_api_key=_clean_optional(
                        generation_data.get("openai_api_key")
                        or security_data.get("openai_api_key")
                        or _env_first("OPENAI_API_KEY")
                    ),
                    openai_model=str(
                        generation_data.get("openai_model", generation.openai_model)
                    ),
                    gemini_api_key=_clean_optional(
                        generation_data.get("gemini_api_key")
                        or _env_first("GEMINI_API_KEY", "GOOGLE_API_KEY")
                    ),
                    gemini_model=str(
                        generation_data.get("gemini_model", generation.gemini_model)
                    ),
                    claude_api_key=_clean_optional(
                        generation_data.get("claude_api_key")
                        or _env_first("CLAUDE_API_KEY", "ANTHROPIC_API_KEY")
                    ),
                    claude_model=str(
                        generation_data.get("claude_model", generation.claude_model)
                    ),
                    temperature=float(
                        generation_data.get(
                            "temperature",
                            os.getenv(
                                "GENERATION_TEMPERATURE", str(generation.temperature)
                            ),
                        )
                    ),
                    max_tokens=int(
                        generation_data.get(
                            "max_tokens",
                            os.getenv(
                                "GENERATION_MAX_TOKENS", str(generation.max_tokens)
                            ),
                        )
                    ),
                    system_prompt=_clean_optional(
                        generation_data.get("system_prompt")
                        or os.getenv("GENERATION_SYSTEM_PROMPT")
                    ),
                )

                integrations_data = data.get("integrations", {})
                integrations = IntegrationConfig(
                    redis_url=integrations_data.get(
                        "redis_url", os.getenv("REDIS_URL", integrations.redis_url)
                    ),
                    selenium_remote_url=integrations_data.get(
                        "selenium_remote_url",
                        os.getenv(
                            "SELENIUM_REMOTE_URL", integrations.selenium_remote_url
                        ),
                    ),
                    api_url=_clean_optional(
                        integrations_data.get("api_url") or os.getenv("API_URL")
                    ),
                    api_public_url=_clean_optional(
                        integrations_data.get("api_public_url")
                        or os.getenv("API_PUBLIC_URL")
                    ),
                )

                privacy_data = data.get("privacy", {})
                privacy = PrivacyConfig(
                    mask_pii=bool(
                        privacy_data.get("mask_pii", _env_bool("MASK_PII", True))
                    ),
                    id_salt=str(
                        privacy_data.get(
                            "id_salt", os.getenv("ID_SALT", "default-salt")
                        )
                    ),
                    job_result_ttl=int(
                        privacy_data.get(
                            "job_result_ttl", os.getenv("JOB_RESULT_TTL", "3600")
                        )
                    ),
                    rate_limit_requests=int(
                        privacy_data.get(
                            "rate_limit_requests",
                            os.getenv("RATE_LIMIT_REQUESTS", "10"),
                        )
                    ),
                    rate_limit_window=int(
                        privacy_data.get(
                            "rate_limit_window", os.getenv("RATE_LIMIT_WINDOW", "60")
                        )
                    ),
                    require_tls_callbacks=bool(
                        privacy_data.get(
                            "require_tls_callbacks",
                            _env_bool("REQUIRE_TLS_CALLBACKS", True),
                        )
                    ),
                    allowed_callback_domains=_coerce_list(
                        privacy_data.get(
                            "allowed_callback_domains",
                            os.getenv("ALLOWED_CALLBACK_DOMAINS", ""),
                        )
                    ),
                )

                urls_data = data.get("urls", {})
                urls = URLConfig(
                    base_url=urls_data.get("base_url", urls.base_url),
                    profile_url=_clean_optional(urls_data.get("profile_url")),
                )

                user_data = data.get("user_profile", {})
                user_profile = UserProfileConfig(
                    display_name=str(
                        user_data.get("display_name", user_profile.display_name)
                    ).strip()
                    or user_profile.display_name,
                    username=str(
                        user_data.get("username", user_profile.username)
                    ).strip()
                    or user_profile.username,
                    favorite_profiles=_normalize_favorite_profiles(
                        user_data.get("favorite_profiles", [])
                    ),
                )
            except Exception:
                pass
        else:
            telegram_token = _clean_optional(
                os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
            )
            telegram_chat_id = _clean_optional(os.getenv("TELEGRAM_CHAT_ID"))
            telegram = TelegramConfig(
                token=telegram_token,
                chat_id=telegram_chat_id,
                enabled=_env_bool(
                    "TELEGRAM_ENABLED", bool(telegram_token and telegram_chat_id)
                ),
                parse_mode="Markdown",
                attach_responses_auto=True,
                attachment_format="txt",
            )
            scraping.headless = _env_bool("SCRAPER_HEADLESS", scraping.headless)
            api.debug = _env_bool("DEBUG", api.debug)

        return cls(
            telegram=telegram,
            scraping=scraping,
            delays=delays,
            api=api,
            security=security,
            generation=generation,
            integrations=integrations,
            privacy=privacy,
            urls=urls,
            user_profile=user_profile,
            base_dir=base_dir,
            data_dir=base_dir / "data",
            logs_dir=base_dir / "data" / "logs",
        )

    def save(self) -> None:
        config_file = self.base_dir / "config" / "config.json"
        config_file.parent.mkdir(exist_ok=True)

        data = {
            "telegram": {
                "token": self.telegram.token,
                "chat_id": self.telegram.chat_id,
                "enabled": self.telegram.enabled,
                "parse_mode": self.telegram.parse_mode,
                "attach_responses_auto": self.telegram.attach_responses_auto,
                "attachment_format": self.telegram.attachment_format,
            },
            "scraping": {
                "headless": self.scraping.headless,
                "timeout": self.scraping.timeout,
                "delay_min": self.scraping.delay_min,
                "delay_max": self.scraping.delay_max,
                "max_retries": self.scraping.max_retries,
                "page_load_timeout": self.scraping.page_load_timeout,
                "implicit_wait": self.scraping.implicit_wait,
                "explicit_wait": self.scraping.explicit_wait,
            },
            "delays": {
                "human_like_min": self.delays.human_like_min,
                "human_like_max": self.delays.human_like_max,
                "retry_base": self.delays.retry_base,
                "error_recovery": self.delays.error_recovery,
                "rate_limit_retry": self.delays.rate_limit_retry,
                "page_load_retry": self.delays.page_load_retry,
            },
            "api": {
                "host": self.api.host,
                "port": self.api.port,
                "debug": self.api.debug,
                "workers": self.api.workers,
            },
            "security": {
                "api_key": self.security.api_key,
                "webhook_signing_secret": self.security.webhook_signing_secret,
                "openai_api_key": self.security.openai_api_key,
                "dashboard_auth_enabled": self.security.dashboard_auth_enabled,
                "dashboard_password_hash": self.security.dashboard_password_hash,
                "dashboard_session_secret": self.security.dashboard_session_secret,
                "dashboard_session_ttl_minutes": self.security.dashboard_session_ttl_minutes,
            },
            "generation": {
                "mode": self.generation.mode,
                "openai_api_key": self.generation.openai_api_key,
                "openai_model": self.generation.openai_model,
                "gemini_api_key": self.generation.gemini_api_key,
                "gemini_model": self.generation.gemini_model,
                "claude_api_key": self.generation.claude_api_key,
                "claude_model": self.generation.claude_model,
                "temperature": self.generation.temperature,
                "max_tokens": self.generation.max_tokens,
                "system_prompt": self.generation.system_prompt,
            },
            "integrations": {
                "redis_url": self.integrations.redis_url,
                "selenium_remote_url": self.integrations.selenium_remote_url,
                "api_url": self.integrations.api_url,
                "api_public_url": self.integrations.api_public_url,
            },
            "privacy": {
                "mask_pii": self.privacy.mask_pii,
                "id_salt": self.privacy.id_salt,
                "job_result_ttl": self.privacy.job_result_ttl,
                "rate_limit_requests": self.privacy.rate_limit_requests,
                "rate_limit_window": self.privacy.rate_limit_window,
                "require_tls_callbacks": self.privacy.require_tls_callbacks,
                "allowed_callback_domains": self.privacy.allowed_callback_domains,
            },
            "urls": {
                "base_url": self.urls.base_url,
                "profile_url": self.urls.profile_url,
            },
            "user_profile": {
                "display_name": self.user_profile.display_name,
                "username": self.user_profile.username,
                "favorite_profiles": [
                    {
                        "name": profile.name,
                        "profile_url": profile.profile_url,
                        "specialty": profile.specialty,
                        "notes": profile.notes,
                    }
                    for profile in self.user_profile.favorite_profiles
                ],
            },
            "updated_at": str(datetime.now()),
        }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- Added method used by CLI (main.py) ---
    def validate(self) -> bool:
        """Basic validation used by CLI.

        Returns True if mandatory directories can be created and basic numeric
        constraints look sane. This keeps behaviour simple while avoiding
        AttributeErrors where the CLI previously expected a validate() method.
        """
        ok = True

        # Ensure data/log dirs exist
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            ok = False

        # Scraping delay sanity
        if self.scraping.delay_min < 0 or self.scraping.delay_max < 0:
            ok = False
        if self.scraping.delay_min > self.scraping.delay_max:
            ok = False
        if self.generation.mode not in {"local", "openai", "gemini", "claude"}:
            ok = False
        if self.generation.temperature < 0 or self.generation.temperature > 1.5:
            ok = False
        if self.generation.max_tokens < 50:
            ok = False
        if self.privacy.job_result_ttl < 60:
            ok = False
        if self.privacy.rate_limit_requests < 1 or self.privacy.rate_limit_window < 1:
            ok = False

        return ok
