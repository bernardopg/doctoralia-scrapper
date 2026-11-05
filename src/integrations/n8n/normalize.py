"""Compatibility exports for the former n8n normalization module."""

from src.api.schemas.common import (
    AnalysisResult,
    Author,
    Doctor,
    GenerationResult,
    Metrics,
    ResponseItem,
    Review,
    Sentiments,
    UnifiedResult,
)
from src.normalization import (
    _build_review_id,
    extract_scraper_result,
    make_unified_result,
    normalize_analysis,
    normalize_doctor,
    normalize_generation,
    normalize_reviews,
    sanitize_raw_reviews,
)

__all__ = [
    "AnalysisResult",
    "Author",
    "Doctor",
    "GenerationResult",
    "Metrics",
    "ResponseItem",
    "Review",
    "Sentiments",
    "UnifiedResult",
    "_build_review_id",
    "extract_scraper_result",
    "make_unified_result",
    "normalize_analysis",
    "normalize_doctor",
    "normalize_generation",
    "normalize_reviews",
    "sanitize_raw_reviews",
]
