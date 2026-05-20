from fastapi import APIRouter, Depends

from src.api.schemas.settings import (
    BatchQualityAnalysisRequest,
    QualityAnalysisRequest,
    QualityAnalysisResponse,
    StatisticsResponse,
)
from src.api.v1._state import increment_analysis_metric
from src.api.v1.deps import require_api_key
from src.api.v1.providers import get_app_config

router = APIRouter(tags=["Analysis"])


@router.get(
    "/v1/statistics",
    response_model=StatisticsResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Monitoring"],
)
async def get_statistics(config=Depends(get_app_config)):
    from src.services.stats import StatsService

    svc = StatsService(config.data_dir)
    stats = svc.get_scraper_stats()
    return StatisticsResponse(**stats)


@router.post(
    "/v1/analyze/quality",
    response_model=QualityAnalysisResponse,
    dependencies=[Depends(require_api_key)],
)
async def analyze_quality(request: QualityAnalysisRequest):
    from src.response_quality_analyzer import ResponseQualityAnalyzer

    analyzer = ResponseQualityAnalyzer()
    analysis = analyzer.analyze_response(request.response_text, request.original_review)
    increment_analysis_metric()
    return QualityAnalysisResponse(
        score=analysis.score.to_dict(),
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        suggestions=analysis.suggestions,
        keywords=analysis.keywords,
        sentiment=analysis.sentiment,
        readability_score=analysis.readability_score,
    )


@router.post(
    "/v1/analyze/quality/batch",
    response_model=list[QualityAnalysisResponse],
    dependencies=[Depends(require_api_key)],
)
async def analyze_quality_batch(request: BatchQualityAnalysisRequest):
    from src.response_quality_analyzer import ResponseQualityAnalyzer

    analyzer = ResponseQualityAnalyzer()
    results: list[QualityAnalysisResponse] = []
    for item in request.analyses:
        analysis = analyzer.analyze_response(item.response_text, item.original_review)
        results.append(
            QualityAnalysisResponse(
                score=analysis.score.to_dict(),
                strengths=analysis.strengths,
                weaknesses=analysis.weaknesses,
                suggestions=analysis.suggestions,
                keywords=analysis.keywords,
                sentiment=analysis.sentiment,
                readability_score=analysis.readability_score,
            )
        )
    increment_analysis_metric(len(results))
    return results
