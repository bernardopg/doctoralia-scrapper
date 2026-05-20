from datetime import datetime

from fastapi import APIRouter, Depends, Request

from src.api.schemas.common import UnifiedResult
from src.api.schemas.requests import (
    JobCreateRequest,
    ScrapeRequest,
    WebhookRequest,
    WebhookResponse,
)
from src.api.v1._state import (
    increment_analysis_metric,
    increment_generation_metric,
    increment_scrapes_failed_metric,
    increment_scrapes_metric,
)
from src.api.v1.deps import require_api_key, verify_webhook_signature
from src.api.v1.providers import get_app_config, get_job_queue
from src.integrations.n8n.normalize import extract_scraper_result, make_unified_result

router = APIRouter(tags=["Scraping"])


@router.post(
    "/v1/scrape:run",
    response_model=UnifiedResult,
    dependencies=[Depends(require_api_key)],
)
async def scrape_run(
    request: ScrapeRequest,
    config=Depends(get_app_config),
):
    start_time = datetime.now()

    try:
        from src.scraper import DoctoraliaScraper

        scraper = DoctoraliaScraper(config)
        scraper_result = scraper.scrape_reviews(str(request.doctor_url))

        if not scraper_result:
            raise RuntimeError("Scraper returned no data")
        doctor_data, reviews_data = extract_scraper_result(scraper_result)

        analysis_data = None
        if request.include_analysis:
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

        generation_data = None
        if request.include_generation:
            from src.response_generator import ResponseGenerator

            generator = ResponseGenerator(config, logger=None)
            responses = []
            for idx, review in enumerate(reviews_data):
                try:
                    generation_result = generator.generate_response_with_metadata(
                        review,
                        doctor_context=doctor_data,
                        generation_mode=request.generation_mode,
                        language=request.language or "pt-BR",
                    )
                except Exception:
                    generation_result = {
                        "text": "",
                        "model": {
                            "type": "error",
                            "provider": request.generation_mode
                            or config.generation.mode,
                        },
                    }
                responses.append(
                    {
                        "review_id": str(review.get("id", idx)),
                        "text": generation_result["text"],
                        "language": request.language or "pt",
                        "provider": generation_result["model"].get("provider"),
                        "model": generation_result["model"].get("name"),
                        "fallback_used": generation_result["model"].get("mode")
                        == "local"
                        and (request.generation_mode or config.generation.mode)
                        != "local",
                        "status": "generated" if generation_result["text"] else "empty",
                    }
                )
            generation_data = {
                "template_id": request.response_template_id,
                "responses": responses,
                "model": {
                    "type": "batch",
                    "provider": request.generation_mode or config.generation.mode,
                },
            }

        increment_scrapes_metric()
        if request.include_analysis:
            increment_analysis_metric()
        if request.include_generation:
            increment_generation_metric()

        return make_unified_result(
            doctor_data=doctor_data,
            reviews_data=reviews_data,
            analysis_data=analysis_data,
            generation_data=generation_data,
            status="completed",
            start_time=start_time,
            end_time=datetime.now(),
        )

    except Exception:
        increment_scrapes_failed_metric()
        return make_unified_result(
            doctor_data={"name": "Error", "url": str(request.doctor_url)},
            reviews_data=[],
            status="failed",
            start_time=start_time,
            end_time=datetime.now(),
        )


@router.post(
    "/v1/hooks/n8n/scrape",
    response_model=WebhookResponse,
    tags=["Webhooks"],
)
async def webhook_scrape(
    request: WebhookRequest,
    req: Request,
    _: bool = Depends(verify_webhook_signature),
    config=Depends(get_app_config),
    q=Depends(get_job_queue),
):
    from src.api.v1.routers.jobs import enqueue_job

    job_request = JobCreateRequest(
        doctor_url=request.doctor_url,
        include_analysis=request.include_analysis,
        include_generation=request.include_generation,
        response_template_id=request.response_template_id,
        language=request.language,
        mode="async",
        callback_url=request.callback_url,
        meta=None,
        idempotency_key=None,
    )

    job_response = enqueue_job(job_request, config=config, q=q)

    return WebhookResponse(
        received=True,
        job_id=job_response.job_id,
        status=job_response.status,
    )
