"""
Common schema models for n8n integration.
Designed for flat, consistent key naming to simplify n8n field mapping.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Author(BaseModel):
    """Review author information."""

    name: str = Field(..., description="Author's name")
    is_verified: bool = Field(default=False, description="Whether author is verified")


class Review(BaseModel):
    """Individual review model."""

    id: str = Field(..., description="Unique review identifier")
    date: str = Field(..., description="Review date")
    rating: int = Field(..., description="Rating (1-5)")
    text: str = Field(..., description="Review text content")
    author: Author = Field(..., description="Review author")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Doctor(BaseModel):
    """Doctor profile information."""

    id: str = Field(..., description="Unique doctor identifier")
    name: str = Field(..., description="Doctor's full name")
    specialty: Optional[str] = Field(None, description="Medical specialty")
    location: Optional[str] = Field(None, description="Practice location")
    rating: Optional[float] = Field(None, description="Average rating")
    profile_url: str = Field(..., description="Profile URL")
    extra: Dict[str, Any] = Field(
        default_factory=dict, description="Additional information"
    )


class Sentiments(BaseModel):
    """Sentiment analysis scores."""

    compound: float = Field(..., description="Compound sentiment score")
    positive: float = Field(..., description="Positive sentiment score", alias="pos")
    neutral: float = Field(..., description="Neutral sentiment score", alias="neu")
    negative: float = Field(..., description="Negative sentiment score", alias="neg")

    class Config:
        populate_by_name = True


class AnalysisResult(BaseModel):
    """Analysis result for reviews."""

    summary: str = Field(..., description="Analysis summary")
    sentiments: Sentiments = Field(..., description="Sentiment scores")
    quality_score: float = Field(..., description="Overall quality score")
    flags: List[str] = Field(default_factory=list, description="Analysis flags")


class ResponseItem(BaseModel):
    """Generated response for a review."""

    review_id: str = Field(..., description="Associated review ID")
    text: str = Field(..., description="Generated response text")
    language: str = Field(..., description="Response language")


class GenerationResult(BaseModel):
    """Response generation result."""

    template_id: Optional[str] = Field(None, description="Template ID used")
    responses: List[ResponseItem] = Field(..., description="Generated responses")
    model: Dict[str, Any] = Field(default_factory=dict, description="Model information")


class Metrics(BaseModel):
    """Performance metrics."""

    scraped_count: int = Field(..., description="Number of items scraped")
    start_ts: datetime = Field(..., description="Start timestamp")
    end_ts: datetime = Field(..., description="End timestamp")
    duration_ms: int = Field(..., description="Duration in milliseconds")
    source: str = Field(default="doctoralia", description="Data source")


class UnifiedResult(BaseModel):
    """Unified result model for all operations."""

    doctor: Doctor = Field(..., description="Doctor information")
    reviews: List[Review] = Field(default_factory=list, description="Reviews list")
    analysis: Optional[AnalysisResult] = Field(None, description="Analysis results")
    generation: Optional[GenerationResult] = Field(
        None, description="Generated responses"
    )
    metrics: Metrics = Field(..., description="Performance metrics")
    job_id: Optional[str] = Field(None, description="Async job ID")
    status: str = Field(
        ..., description="Operation status", pattern="^(completed|failed|running)$"
    )


class ErrorDetail(BaseModel):
    """Error detail information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Any] = Field(None, description="Additional error details")
    request_id: Optional[str] = Field(None, description="Request identifier")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail = Field(..., description="Error information")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    uptime_s: int = Field(..., description="Uptime in seconds")


class ReadyComponent(BaseModel):
    """Detailed readiness component information."""

    status: bool = Field(..., description="Component status")
    latency_ms: Optional[int] = Field(
        None, description="Latency in milliseconds (if applicable)"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional component specific details"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": True,
                "latency_ms": 12,
                "details": {"queue_depth": 3},
            }
        }


class ReadyResponse(BaseModel):
    """Readiness check response."""

    ready: bool = Field(..., description="Service readiness")
    checks: Dict[str, bool] = Field(..., description="Component checks")
    components: Optional[Dict[str, ReadyComponent]] = Field(
        default=None,
        description="Detailed component diagnostics (status, latency, error, extra details)",
    )
