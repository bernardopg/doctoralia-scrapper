"""
Data normalization and mapping functions for n8n integration.
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

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


def normalize_doctor(raw_data: Dict[str, Any]) -> Doctor:
    """
    Normalize raw doctor data to Doctor schema.
    """
    # Generate ID from URL if not provided
    doctor_id = raw_data.get("id")
    if not doctor_id and raw_data.get("url"):
        doctor_id = hashlib.md5(raw_data["url"].encode()).hexdigest()[:8]
    
    return Doctor(
        id=doctor_id or "unknown",
        name=raw_data.get("name", "Unknown Doctor"),
        specialty=raw_data.get("specialty"),
        location=raw_data.get("location"),
        rating=raw_data.get("rating"),
        profile_url=raw_data.get("url", ""),
        extra={
            k: v for k, v in raw_data.items()
            if k not in ["id", "name", "specialty", "location", "rating", "url"]
        }
    )


def normalize_reviews(raw_reviews: List[Dict[str, Any]]) -> List[Review]:
    """
    Normalize raw reviews data to Review schema.
    """
    reviews = []
    
    for idx, raw in enumerate(raw_reviews):
        # Generate review ID if not present
        review_id = raw.get("id")
        if not review_id:
            content = f"{raw.get('date', '')}{raw.get('text', '')}{idx}"
            review_id = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Extract author info
        author = Author(
            name=raw.get("author_name", raw.get("author", "Anonymous")),
            is_verified=raw.get("is_verified", False)
        )
        
        # Create review
        review = Review(
            id=review_id,
            date=raw.get("date", datetime.now().isoformat()),
            rating=raw.get("rating", 0),
            text=raw.get("comment", raw.get("text", "")),
            author=author,
            metadata={
                k: v for k, v in raw.items()
                if k not in ["id", "date", "rating", "comment", "text", 
                           "author_name", "author", "is_verified"]
            }
        )
        
        reviews.append(review)
    
    return reviews


def normalize_analysis(raw_analysis: Dict[str, Any]) -> Optional[AnalysisResult]:
    """
    Normalize raw analysis data to AnalysisResult schema.
    """
    if not raw_analysis:
        return None
    
    # Extract sentiment scores
    sentiment_data = raw_analysis.get("sentiment", {})
    sentiments = Sentiments(
        compound=sentiment_data.get("compound", 0.0),
        positive=sentiment_data.get("pos", sentiment_data.get("positive", 0.0)),
        neutral=sentiment_data.get("neu", sentiment_data.get("neutral", 0.0)),
        negative=sentiment_data.get("neg", sentiment_data.get("negative", 0.0))
    )
    
    return AnalysisResult(
        summary=raw_analysis.get("summary", "No summary available"),
        sentiments=sentiments,
        quality_score=raw_analysis.get("quality_score", 0.0),
        flags=raw_analysis.get("flags", [])
    )


def normalize_generation(raw_generation: Dict[str, Any]) -> Optional[GenerationResult]:
    """
    Normalize raw generation data to GenerationResult schema.
    """
    if not raw_generation:
        return None
    
    # Extract responses
    responses = []
    for resp in raw_generation.get("responses", []):
        responses.append(ResponseItem(
            review_id=resp.get("review_id", ""),
            text=resp.get("text", ""),
            language=resp.get("language", "pt")
        ))
    
    return GenerationResult(
        template_id=raw_generation.get("template_id"),
        responses=responses,
        model=raw_generation.get("model", {})
    )


def make_unified_result(
    doctor_data: Dict[str, Any],
    reviews_data: List[Dict[str, Any]],
    analysis_data: Optional[Dict[str, Any]] = None,
    generation_data: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    status: str = "completed",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> UnifiedResult:
    """
    Create a unified result from various data sources.
    """
    # Calculate metrics
    start_ts = start_time or datetime.now()
    end_ts = end_time or datetime.now()
    duration_ms = int((end_ts - start_ts).total_seconds() * 1000)
    
    metrics = Metrics(
        scraped_count=len(reviews_data),
        start_ts=start_ts,
        end_ts=end_ts,
        duration_ms=duration_ms,
        source="doctoralia"
    )
    
    # Normalize all data
    doctor = normalize_doctor(doctor_data)
    reviews = normalize_reviews(reviews_data)
    analysis = normalize_analysis(analysis_data) if analysis_data else None
    generation = normalize_generation(generation_data) if generation_data else None
    
    return UnifiedResult(
        doctor=doctor,
        reviews=reviews,
        analysis=analysis,
        generation=generation,
        metrics=metrics,
        job_id=job_id,
        status=status
    )


def extract_scraper_result(scraper_output: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Extract doctor and reviews data from scraper output.
    
    Returns:
        Tuple of (doctor_data, reviews_data)
    """
    # Extract doctor info
    doctor_data = {
        "name": scraper_output.get("doctor_name", "Unknown"),
        "url": scraper_output.get("url", ""),
        "rating": scraper_output.get("average_rating"),
        "specialty": scraper_output.get("specialty"),
        "location": scraper_output.get("location"),
    }
    
    # Extract reviews
    reviews_data = scraper_output.get("reviews", [])
    
    return doctor_data, reviews_data
