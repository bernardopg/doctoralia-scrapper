"""
Pydantic models for settings and quality-analysis endpoints.
Migrated from the legacy ``api_server.py``.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ---- Quality Analysis ----


class QualityAnalysisRequest(BaseModel):
    """Request model for quality analysis."""

    response_text: str = Field(..., description="Doctor's response text to analyze")
    original_review: Optional[str] = Field(
        default=None, description="Original patient review for context"
    )


class BatchQualityAnalysisRequest(BaseModel):
    """Request model for batch quality analysis."""

    analyses: List[QualityAnalysisRequest] = Field(
        ..., description="List of quality analysis requests"
    )


class QualityAnalysisResponse(BaseModel):
    """Response model for quality analysis."""

    score: Dict[str, Any] = Field(..., description="Quality scores")
    strengths: List[str] = Field(..., description="Response strengths")
    weaknesses: List[str] = Field(..., description="Response weaknesses")
    suggestions: List[str] = Field(..., description="Improvement suggestions")
    keywords: List[str] = Field(..., description="Key terms identified")
    sentiment: str = Field(..., description="Overall sentiment")
    readability_score: float = Field(..., description="Readability score")


# ---- Statistics ----


class StatisticsResponse(BaseModel):
    """Response model for scraper statistics."""

    total_scraped_doctors: int
    total_reviews: int
    average_rating: float
    last_scrape_time: Optional[str]
    data_files: List[str]
    platform_stats: Dict[str, Any]


# ---- Settings ----


class TelegramSettingsModel(BaseModel):
    """Telegram configuration model."""

    enabled: bool = Field(default=False, description="Enable Telegram notifications")
    token: Optional[str] = Field(None, description="Telegram bot token")
    chat_id: Optional[str] = Field(None, description="Telegram chat ID")
    parse_mode: str = Field(default="Markdown", description="Message parse mode")
    attach_responses_auto: bool = Field(
        default=True, description="Auto-attach responses file"
    )
    attachment_format: str = Field(default="txt", description="Attachment format")


class ScrapingSettingsModel(BaseModel):
    """Scraping configuration model."""

    headless: bool = Field(default=True, description="Run browser in headless mode")
    timeout: int = Field(default=60, ge=10, le=300, description="Operation timeout")
    delay_min: float = Field(
        default=2.0, ge=0.1, le=10.0, description="Minimum delay between actions"
    )
    delay_max: float = Field(
        default=4.0, ge=0.1, le=10.0, description="Maximum delay between actions"
    )
    max_retries: int = Field(default=5, ge=1, le=10, description="Maximum retries")
    page_load_timeout: int = Field(
        default=45, ge=10, le=120, description="Page load timeout"
    )
    implicit_wait: int = Field(default=20, ge=5, le=60, description="Implicit wait")
    explicit_wait: int = Field(default=30, ge=5, le=120, description="Explicit wait")


class DelaySettingsModel(BaseModel):
    """Human-like delay and retry pacing configuration."""

    human_like_min: float = Field(
        default=1.0, ge=0.0, le=30.0, description="Minimum human-like delay"
    )
    human_like_max: float = Field(
        default=3.0, ge=0.0, le=60.0, description="Maximum human-like delay"
    )
    retry_base: float = Field(
        default=2.0, ge=0.0, le=120.0, description="Retry base delay"
    )
    error_recovery: float = Field(
        default=10.0, ge=0.0, le=300.0, description="Error recovery delay"
    )
    rate_limit_retry: float = Field(
        default=60.0, ge=0.0, le=600.0, description="Rate limit backoff"
    )
    page_load_retry: float = Field(
        default=5.0, ge=0.0, le=120.0, description="Page load retry delay"
    )


class APISettingsModel(BaseModel):
    """API configuration model."""

    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, ge=1024, le=65535, description="API port")
    debug: bool = Field(default=False, description="Debug mode")
    workers: int = Field(default=1, ge=1, le=8, description="Number of workers")


class SecuritySettingsModel(BaseModel):
    """Secrets and authentication settings."""

    api_key: Optional[str] = Field(None, description="API authentication key")
    webhook_signing_secret: Optional[str] = Field(
        None, description="Webhook HMAC signing secret"
    )
    openai_api_key: Optional[str] = Field(
        None,
        description="OpenAI API key reserved for future integrations",
    )


class GenerationSettingsModel(BaseModel):
    """Automatic response generation provider settings."""

    mode: str = Field(
        default="local",
        description="Default generation mode: local, openai, gemini or claude",
    )
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key for response generation"
    )
    openai_model: str = Field(
        default="gpt-4.1-mini", description="OpenAI model identifier"
    )
    gemini_api_key: Optional[str] = Field(
        default=None, description="Gemini API key for response generation"
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash", description="Gemini model identifier"
    )
    claude_api_key: Optional[str] = Field(
        default=None, description="Claude/Anthropic API key for response generation"
    )
    claude_model: str = Field(
        default="claude-3-5-sonnet-latest",
        description="Claude model identifier",
    )
    temperature: float = Field(
        default=0.35, ge=0.0, le=1.5, description="Generation temperature"
    )
    max_tokens: int = Field(
        default=300, ge=50, le=2000, description="Maximum response tokens"
    )
    system_prompt: Optional[str] = Field(
        default=None, description="Optional system prompt override"
    )


class IntegrationSettingsModel(BaseModel):
    """External service integration settings."""

    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    selenium_remote_url: str = Field(
        default="http://localhost:4444/wd/hub",
        description="Remote Selenium hub URL",
    )
    api_url: Optional[str] = Field(
        default=None, description="Dashboard-to-API internal base URL"
    )
    api_public_url: Optional[str] = Field(
        default=None, description="Public API base URL for docs links"
    )


class PrivacySettingsModel(BaseModel):
    """Privacy, callback hardening and rate limiting settings."""

    mask_pii: bool = Field(default=True, description="Mask PII in outbound payloads")
    id_salt: str = Field(default="default-salt", description="Salt for anonymized IDs")
    job_result_ttl: int = Field(
        default=3600, ge=60, le=604800, description="TTL for job results in seconds"
    )
    rate_limit_requests: int = Field(
        default=10, ge=1, le=1000, description="Allowed requests per window"
    )
    rate_limit_window: int = Field(
        default=60, ge=1, le=3600, description="Rate limit window in seconds"
    )
    require_tls_callbacks: bool = Field(
        default=True, description="Require HTTPS for callback URLs"
    )
    allowed_callback_domains: List[str] = Field(
        default_factory=list,
        description="Allowed callback domains when TLS validation is enabled",
    )


class URLSettingsModel(BaseModel):
    """Stored URLs for operational shortcuts."""

    base_url: str = Field(
        default="https://www.doctoralia.com.br", description="Doctoralia base URL"
    )
    profile_url: Optional[str] = Field(
        default=None, description="Default Doctoralia profile URL"
    )


class FavoriteProfileModel(BaseModel):
    """Favorite doctor profile saved for quick access."""

    name: str = Field(..., description="Friendly profile name")
    profile_url: str = Field(..., description="Doctoralia profile URL")
    specialty: Optional[str] = Field(default=None, description="Doctor specialty")
    notes: Optional[str] = Field(default=None, description="Optional personal notes")


class UserProfileSettingsModel(BaseModel):
    """Operator profile shown in the dashboard."""

    display_name: str = Field(
        default="Administrador", description="Displayed operator name"
    )
    username: str = Field(default="admin", description="Dashboard username/handle")
    favorite_profiles: List[FavoriteProfileModel] = Field(
        default_factory=list, description="Favorite doctors for quick access"
    )


class SettingsModel(BaseModel):
    """Complete settings model."""

    telegram: TelegramSettingsModel = Field(
        default_factory=TelegramSettingsModel, description="Telegram settings"
    )
    security: SecuritySettingsModel = Field(
        default_factory=SecuritySettingsModel, description="Secrets and auth settings"
    )
    generation: GenerationSettingsModel = Field(
        default_factory=GenerationSettingsModel,
        description="Automatic response generation settings",
    )
    integrations: IntegrationSettingsModel = Field(
        default_factory=IntegrationSettingsModel,
        description="Integration settings",
    )
    scraping: ScrapingSettingsModel = Field(
        default_factory=ScrapingSettingsModel, description="Scraping settings"
    )
    delays: DelaySettingsModel = Field(
        default_factory=DelaySettingsModel, description="Delay settings"
    )
    privacy: PrivacySettingsModel = Field(
        default_factory=PrivacySettingsModel, description="Privacy settings"
    )
    api: APISettingsModel = Field(
        default_factory=APISettingsModel, description="API settings"
    )
    urls: URLSettingsModel = Field(
        default_factory=URLSettingsModel, description="Operational URLs"
    )
    user_profile: UserProfileSettingsModel = Field(
        default_factory=UserProfileSettingsModel, description="Dashboard user profile"
    )


class SettingsResponse(BaseModel):
    """Response model for settings operations."""

    success: bool
    message: str
    settings: Optional[SettingsModel] = None
