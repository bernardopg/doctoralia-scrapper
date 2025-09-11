"""
Request schema models for n8n integration.
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field, HttpUrl


class ScrapeRequest(BaseModel):
    """Request model for scraping operations."""
    doctor_url: HttpUrl = Field(..., description="Doctor profile URL to scrape")
    include_analysis: bool = Field(default=True, description="Include sentiment analysis")
    include_generation: bool = Field(default=False, description="Generate AI responses")
    response_template_id: Optional[str] = Field(None, description="Response template ID")
    language: Optional[str] = Field(default="pt", description="Language for responses")
    meta: Optional[Dict] = Field(None, description="Additional metadata")


class JobCreateRequest(ScrapeRequest):
    """Request model for async job creation."""
    mode: str = Field(default="async", description="Execution mode", pattern="^async$")
    callback_url: Optional[HttpUrl] = Field(None, description="Webhook callback URL")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for deduplication")


class WebhookRequest(BaseModel):
    """Request model for webhook triggers."""
    doctor_url: HttpUrl = Field(..., description="Doctor profile URL to scrape")
    callback_url: Optional[HttpUrl] = Field(None, description="Webhook callback URL")
    include_analysis: bool = Field(default=True, description="Include sentiment analysis")
    include_generation: bool = Field(default=False, description="Generate AI responses")
    response_template_id: Optional[str] = Field(None, description="Response template ID")
    language: Optional[str] = Field(default="pt", description="Language for responses")


class JobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    message: Optional[str] = Field(None, description="Status message")


class WebhookResponse(BaseModel):
    """Response model for webhook acknowledgment."""
    received: bool = Field(..., description="Request received")
    job_id: str = Field(..., description="Created job ID")
    status: str = Field(..., description="Job status")
