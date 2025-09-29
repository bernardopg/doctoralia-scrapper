"""
Async job tasks for scraping and processing.
"""

import json
import time
from datetime import datetime
from typing import Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.api.v1.deps import create_webhook_signature
from src.integrations.n8n.normalize import extract_scraper_result, make_unified_result


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
        print(f"Callback failed: {e}")
        return False


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
        # Import scraper
        from src.scraper import DoctoraliaScraper

        # Initialize scraper
        scraper = DoctoraliaScraper()

        # Run scraping
        scraper_result = scraper.scrape_doctor_reviews(request_data["doctor_url"])

        # Extract data
        doctor_data, reviews_data = extract_scraper_result(scraper_result)

        # Run analysis if requested
        analysis_data = None
        if request_data.get("include_analysis"):
            from src.response_quality_analyzer import ResponseQualityAnalyzer

            analyzer = ResponseQualityAnalyzer()
            sentiments = []

            for review in reviews_data:
                sentiment = analyzer.analyze_sentiment(review.get("comment", ""))
                sentiments.append(sentiment)

            # Aggregate sentiment
            if sentiments:
                avg_sentiment = {
                    "compound": sum(s["compound"] for s in sentiments)
                    / len(sentiments),
                    "pos": sum(s["pos"] for s in sentiments) / len(sentiments),
                    "neu": sum(s["neu"] for s in sentiments) / len(sentiments),
                    "neg": sum(s["neg"] for s in sentiments) / len(sentiments),
                }
            else:
                avg_sentiment = {"compound": 0, "pos": 0, "neu": 0, "neg": 0}

            analysis_data = {
                "summary": f"Analyzed {len(reviews_data)} reviews",
                "sentiment": avg_sentiment,
                "quality_score": avg_sentiment["compound"] * 100,
                "flags": [],
            }

        # Run generation if requested
        generation_data = None
        if request_data.get("include_generation"):
            from src.response_generator import ResponseGenerator

            generator = ResponseGenerator()
            responses = []

            for idx, review in enumerate(reviews_data):
                response_text = generator.generate_response(
                    review.get("comment", ""),
                    template_id=request_data.get("response_template_id"),
                    language=request_data.get("language", "pt"),
                )
                responses.append(
                    {
                        "review_id": str(idx),
                        "text": response_text,
                        "language": request_data.get("language", "pt"),
                    }
                )

            generation_data = {
                "template_id": request_data.get("response_template_id"),
                "responses": responses,
                "model": {"type": "template"},
            }

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

        # Log the exception for observability (avoid unused variable)
        try:
            print(f"scrape_and_process failed: {e}")
        except Exception:
            pass

        # Send error callback if URL provided
        if callback_url:
            post_callback(callback_url, error_result.dict(), job_id)

        return error_result.dict()
