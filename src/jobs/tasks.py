"""
Async job tasks for scraping and processing.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.api.v1.deps import create_webhook_signature
from src.integrations.n8n.normalize import extract_scraper_result, make_unified_result

logger = logging.getLogger(__name__)


def post_callback(url: str, payload: Dict, job_id: Optional[str] = None) -> bool:
    """
    Post callback to webhook URL with retries and signing.
    """
    # Create session with retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Prepare payload
    payload_json = json.dumps(payload)

    # Create signature
    timestamp = time.time()
    ts_str, signature = create_webhook_signature(payload_json, timestamp)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": ts_str,
        "X-Source": "doctoralia-scrapper",
    }

    if signature:
        headers["X-Signature"] = signature

    if job_id:
        headers["X-Job-Id"] = job_id

    try:
        # Send request
        response = session.post(url, data=payload_json, headers=headers, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Callback failed: {e}")
        return False


def _run_sentiment_analysis(reviews_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run sentiment analysis on reviews and return analysis data."""
    from src.response_quality_analyzer import ResponseQualityAnalyzer

    analyzer = ResponseQualityAnalyzer()
    sentiments = []

    for review in reviews_data:
        review_text = review.get("comment", "")
        if review_text:
            sia_scores = analyzer.sia.polarity_scores(review_text)
            sentiments.append(
                {
                    "compound": sia_scores.get("compound", 0.0),
                    "pos": sia_scores.get("pos", 0.0),
                    "neu": sia_scores.get("neu", 0.0),
                    "neg": sia_scores.get("neg", 0.0),
                }
            )

    if sentiments:
        avg_sentiment = {
            "compound": sum(s["compound"] for s in sentiments) / len(sentiments),
            "pos": sum(s["pos"] for s in sentiments) / len(sentiments),
            "neu": sum(s["neu"] for s in sentiments) / len(sentiments),
            "neg": sum(s["neg"] for s in sentiments) / len(sentiments),
        }
    else:
        avg_sentiment = {"compound": 0, "pos": 0, "neu": 0, "neg": 0}

    return {
        "summary": f"Analyzed {len(reviews_data)} reviews",
        "sentiment": avg_sentiment,
        "quality_score": avg_sentiment["compound"] * 100,
        "flags": [],
    }


def _run_response_generation(
    reviews_data: List[Dict[str, Any]], request_data: Dict
) -> Dict[str, Any]:
    """Generate responses for reviews and return generation data."""
    from config.settings import AppConfig
    from src.response_generator import ResponseGenerator

    config = AppConfig.load()
    generator = ResponseGenerator(config, logger)
    responses = []

    for idx, review in enumerate(reviews_data):
        try:
            response_text = generator.generate_response(review)
        except Exception:
            response_text = ""
        responses.append(
            {
                "review_id": str(review.get("id", idx)),
                "text": response_text,
                "language": request_data.get("language", "pt"),
            }
        )

    return {
        "template_id": request_data.get("response_template_id"),
        "responses": responses,
        "model": {"type": "rule-based"},
    }


def scrape_and_process(
    request_data: Dict,
    job_id: Optional[str] = None,
    callback_url: Optional[str] = None,
) -> Dict:
    """
    Main job function for async scraping and processing.
    """
    start_time = datetime.now()

    try:
        # Import scraper and config
        from config.settings import AppConfig
        from src.scraper import DoctoraliaScraper

        # Initialize scraper with required config
        config = AppConfig.load()
        scraper = DoctoraliaScraper(config, logger)

        # Run scraping (correct method name)
        scraper_result = scraper.scrape_reviews(request_data["doctor_url"])

        if not scraper_result:
            raise RuntimeError("Scraper returned no data")

        # Extract data
        doctor_data, reviews_data = extract_scraper_result(scraper_result)

        # Run analysis if requested
        analysis_data = None
        if request_data.get("include_analysis"):
            analysis_data = _run_sentiment_analysis(reviews_data)

        # Run generation if requested
        generation_data = None
        if request_data.get("include_generation"):
            generation_data = _run_response_generation(reviews_data, request_data)

        # Create unified result
        result = make_unified_result(
            doctor_data=doctor_data,
            reviews_data=reviews_data,
            analysis_data=analysis_data,
            generation_data=generation_data,
            job_id=job_id,
            status="completed",
            start_time=start_time,
            end_time=datetime.now(),
        )

        # Send callback if URL provided
        if callback_url:
            post_callback(callback_url, result.dict(), job_id)

        return result.dict()

    except Exception as e:
        # Create error result
        error_result = make_unified_result(
            doctor_data={"name": "Error", "url": request_data.get("doctor_url", "")},
            reviews_data=[],
            job_id=job_id,
            status="failed",
            start_time=start_time,
            end_time=datetime.now(),
        )

        logger.error(f"scrape_and_process failed: {e}")

        # Send error callback if URL provided
        if callback_url:
            post_callback(callback_url, error_result.dict(), job_id)

        return error_result.dict()
