"""
Schema models for Telegram notification schedules and history.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TelegramNotificationScheduleModel(BaseModel):
    """Persisted Telegram schedule definition."""

    name: str = Field(..., description="Friendly schedule name")
    enabled: bool = Field(default=True, description="Enable or disable the schedule")
    timezone: str = Field(
        default="America/Sao_Paulo", description="IANA timezone for execution"
    )
    recurrence_type: str = Field(
        default="daily",
        description="daily, weekdays, weekly, interval or custom_cron",
    )
    time_of_day: Optional[str] = Field(
        default="09:00", description="Time of day in HH:MM for fixed recurrences"
    )
    day_of_week: Optional[int] = Field(
        default=None, description="0=Sunday ... 6=Saturday for weekly schedules"
    )
    interval_minutes: Optional[int] = Field(
        default=None, description="Minutes between runs for interval schedules"
    )
    cron_expression: Optional[str] = Field(
        default=None,
        description="Custom cron expression when recurrence_type=custom_cron",
    )
    profile_url: Optional[str] = Field(
        default=None, description="Doctoralia profile URL used for scraping"
    )
    profile_label: Optional[str] = Field(
        default=None, description="Optional operator-facing profile label"
    )
    trigger_new_scrape: bool = Field(
        default=True, description="Run a fresh scrape before sending the notification"
    )
    include_generation: bool = Field(
        default=False, description="Generate suggested responses before sending"
    )
    generation_mode: str = Field(
        default="default", description="default, local, openai, gemini or claude"
    )
    report_type: str = Field(
        default="complete", description="simple, complete or health"
    )
    include_health_status: bool = Field(
        default=False, description="Include Redis/Selenium/API health details"
    )
    send_attachment: bool = Field(
        default=True, description="Send a file attachment along with the message"
    )
    attachment_scope: str = Field(
        default="responses", description="responses, comments or snapshot"
    )
    attachment_format: str = Field(default="txt", description="txt, json or csv")
    max_reviews: int = Field(
        default=20, ge=1, le=100, description="Maximum reviews processed in one run"
    )
    telegram_token: Optional[str] = Field(
        default=None, description="Optional token override for this schedule"
    )
    telegram_chat_id: Optional[str] = Field(
        default=None, description="Optional chat ID override for this schedule"
    )
    parse_mode: str = Field(
        default="Markdown", description="Telegram parse mode override"
    )


class TelegramNotificationScheduleResponse(TelegramNotificationScheduleModel):
    """Schedule definition returned by the API."""

    id: str
    cron_expression: Optional[str] = None
    recurrence_label: str
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class TelegramNotificationHistoryEntry(BaseModel):
    """Single schedule execution entry."""

    id: str
    schedule_id: Optional[str] = None
    schedule_name: str
    status: str
    manual: bool = False
    run_at: str
    completed_at: str
    summary: str
    error: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    attachment_path: Optional[str] = None


class TelegramNotificationTestRequest(BaseModel):
    """Manual Telegram test payload."""

    message: Optional[str] = Field(
        default=None, description="Optional custom message for the test send"
    )
    telegram_token: Optional[str] = Field(
        default=None, description="Optional token override for test sends"
    )
    telegram_chat_id: Optional[str] = Field(
        default=None, description="Optional chat id override for test sends"
    )
    parse_mode: str = Field(default="Markdown", description="Telegram parse mode")


class TelegramNotificationRunResponse(BaseModel):
    """Result of a manual test or schedule execution."""

    success: bool
    message: str
    result: Dict[str, Any] = Field(default_factory=dict)


class TelegramNotificationScheduleListResponse(BaseModel):
    """List schedules plus lightweight summary."""

    schedules: List[TelegramNotificationScheduleResponse]
    summary: Dict[str, Any] = Field(default_factory=dict)


class TelegramNotificationHistoryResponse(BaseModel):
    """List schedule execution history."""

    history: List[TelegramNotificationHistoryEntry]
