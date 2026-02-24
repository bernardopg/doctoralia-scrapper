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


class APISettingsModel(BaseModel):
    """API configuration model."""

    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8080, ge=1024, le=65535, description="API port")
    debug: bool = Field(default=False, description="Debug mode")
    workers: int = Field(default=1, ge=1, le=8, description="Number of workers")


class SettingsModel(BaseModel):
    """Complete settings model."""

    telegram: TelegramSettingsModel = Field(..., description="Telegram settings")
    scraping: ScrapingSettingsModel = Field(..., description="Scraping settings")
    api: APISettingsModel = Field(..., description="API settings")


class SettingsResponse(BaseModel):
    """Response model for settings operations."""

    success: bool
    message: str
    settings: Optional[SettingsModel] = None
