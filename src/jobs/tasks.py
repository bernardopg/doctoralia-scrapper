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


def _update_job_meta(
    progress: Optional[int] = None, message: Optional[str] = None
) -> None:
    """Persist lightweight job progress details for the dashboard."""
    try:
        from rq import get_current_job

        job = get_current_job()
        if job is None:
            return

        if progress is not None:
            job.meta["progress"] = max(0, min(100, int(progress)))
        if message is not None:
            job.meta["message"] = str(message)[:500]
        job.save_meta()
    except Exception as exc:  # pragma: no cover - depends on active RQ worker
        logger.debug("Unable to update job metadata: %s", exc)


def _merge_generated_responses(
    reviews_data: List[Dict[str, Any]],
    generation_data: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Attach generated suggestions back to the persisted snapshot reviews."""
    if not generation_data:
        return [dict(review) for review in reviews_data]

    responses_by_review_id = {
        str(response.get("review_id")): response.get("text", "")
        for response in generation_data.get("responses", [])
        if response.get("review_id") not in (None, "") and response.get("text")
    }

    merged_reviews: List[Dict[str, Any]] = []
    for review in reviews_data:
        review_payload = dict(review)
        response_text = responses_by_review_id.get(str(review_payload.get("id", "")))
        if response_text:
            review_payload["generated_response"] = response_text
        merged_reviews.append(review_payload)

    return merged_reviews


def _build_snapshot_payload(
    scraper_result: Dict[str, Any],
    doctor_data: Dict[str, Any],
    reviews_data: List[Dict[str, Any]],
    generation_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the JSON snapshot consumed by the workspace/dashboard pages."""
    snapshot_reviews = _merge_generated_responses(reviews_data, generation_data)
    snapshot_payload = dict(scraper_result)
    snapshot_payload["doctor_name"] = doctor_data.get("name") or snapshot_payload.get(
        "doctor_name", "Unknown"
    )
    snapshot_payload["url"] = doctor_data.get("url") or snapshot_payload.get("url", "")
    snapshot_payload["specialty"] = doctor_data.get(
        "specialty"
    ) or snapshot_payload.get("specialty")
    snapshot_payload["location"] = doctor_data.get("location") or snapshot_payload.get(
        "location"
    )
    if doctor_data.get("rating") is not None:
        snapshot_payload["average_rating"] = doctor_data.get("rating")
    snapshot_payload["reviews"] = snapshot_reviews
    snapshot_payload["total_reviews"] = len(snapshot_reviews)
    snapshot_payload["extraction_timestamp"] = (
        snapshot_payload.get("extraction_timestamp") or datetime.now().isoformat()
    )
    return snapshot_payload


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
    reviews_data: List[Dict[str, Any]],
    request_data: Dict,
    doctor_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate responses for reviews and return generation data."""
    from config.settings import AppConfig
    from src.response_generator import ResponseGenerator

    config = AppConfig.load()
    generator = ResponseGenerator(config, logger)
    responses = []
    doctor_context = {
        "name": (doctor_data or {}).get("name") or request_data.get("doctor_name"),
        "specialty": (doctor_data or {}).get("specialty")
        or request_data.get("doctor_specialty"),
        "profile_url": (doctor_data or {}).get("url") or request_data.get("doctor_url"),
    }

    for idx, review in enumerate(reviews_data):
        try:
            generation_result = generator.generate_response_with_metadata(
                review,
                doctor_context=doctor_context,
                generation_mode=request_data.get("generation_mode"),
                language=request_data.get("language", "pt-BR"),
            )
        except Exception as exc:
            logger.exception(
                "Error generating response for review %s at index %d",
                review.get("id", idx),
                idx,
            )
            generation_result = {
                "text": "",
                "model": {
                    "type": "error",
                    "provider": request_data.get("generation_mode")
                    or config.generation.mode,
                },
                "error": str(exc),
            }
        responses.append(
            {
                "review_id": str(review.get("id", idx)),
                "text": generation_result["text"],
                "language": request_data.get("language", "pt"),
                "provider": generation_result["model"].get("provider"),
                "model": generation_result["model"].get("name"),
                "fallback_used": generation_result["model"].get("mode") == "local"
                and (request_data.get("generation_mode") or config.generation.mode)
                != "local",
                "status": "generated" if generation_result["text"] else "empty",
                "error": generation_result.get("error"),
            }
        )

    return {
        "template_id": request_data.get("response_template_id"),
        "responses": responses,
        "model": {
            "type": "batch",
            "provider": request_data.get("generation_mode") or config.generation.mode,
        },
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
        _update_job_meta(progress=5, message="Inicializando scraping")

        # Run scraping (correct method name)
        scraper_result = scraper.scrape_reviews(str(request_data["doctor_url"]))

        if not scraper_result:
            raise RuntimeError("Scraper returned no data")

        # Extract data
        doctor_data, reviews_data = extract_scraper_result(scraper_result)
        _update_job_meta(
            progress=55,
            message=f"{len(reviews_data)} reviews extraídos de {doctor_data.get('name') or 'perfil'}",
        )

        # Run analysis if requested
        analysis_data = None
        if request_data.get("include_analysis"):
            analysis_data = _run_sentiment_analysis(reviews_data)

        # Run generation if requested
        generation_data = None
        if request_data.get("include_generation"):
            generation_data = _run_response_generation(
                reviews_data, request_data, doctor_data
            )

        _update_job_meta(progress=80, message="Persistindo snapshot do scraping")
        snapshot_payload = _build_snapshot_payload(
            scraper_result=scraper_result,
            doctor_data=doctor_data,
            reviews_data=reviews_data,
            generation_data=generation_data,
        )
        saved_file = scraper.save_data(snapshot_payload)
        if saved_file is None:
            raise RuntimeError("Scraping concluído, mas o snapshot não pôde ser salvo")

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

        _update_job_meta(progress=100, message=f"Snapshot salvo em {saved_file.name}")
        return result.dict()

    except Exception as e:
        # Create error result
        error_result = make_unified_result(
            doctor_data={
                "name": "Error",
                "url": str(request_data.get("doctor_url", "")),
            },
            reviews_data=[],
            job_id=job_id,
            status="failed",
            start_time=start_time,
            end_time=datetime.now(),
        )

        logger.error(f"scrape_and_process failed: {e}")
        _update_job_meta(progress=0, message=f"Falha: {e}")

        # Send error callback if URL provided
        if callback_url:
            post_callback(callback_url, error_result.dict(), job_id)

        return error_result.dict()


def run_telegram_schedule_job(
    schedule_id: str,
    manual_lock_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a persisted Telegram schedule inside the RQ worker."""
    from src.services.telegram_schedule_service import TelegramScheduleService

    service = TelegramScheduleService()
    try:
        return service.execute_schedule(schedule_id, manual=True)
    finally:
        if manual_lock_key:
            try:
                service.redis.delete(manual_lock_key)
            except Exception as exc:  # pragma: no cover - best effort cleanup
                logger.warning(
                    "Failed to release manual schedule lock %s: %s",
                    manual_lock_key,
                    exc,
                )
