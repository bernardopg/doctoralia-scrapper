from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from src.api.v1._state import API_VERSION
from src.api.v1.providers import get_metrics_snapshot
from src.api.v1.routers.health import get_api_start_time

router = APIRouter(tags=["Metrics"])


def _percentile(data: list[int], pct: float) -> Optional[float]:
    if not data:
        return None
    idx = int(round((len(data) - 1) * pct))
    return sorted(data)[idx]


@router.get("/v1/metrics")
async def metrics_endpoint(metrics_snapshot=Depends(get_metrics_snapshot)):
    snapshot, redis_available = metrics_snapshot
    durations: list[int] = snapshot["request_durations_ms"]  # type: ignore[assignment]
    return {
        "version": API_VERSION,
        "uptime_s": int((datetime.now() - get_api_start_time()).total_seconds()),
        "backend": {"type": "redis", "available": redis_available},
        "requests": {
            "total": snapshot["requests_total"],
            "in_progress": snapshot["requests_in_progress"],
            "failed": snapshot["requests_failed_total"],
            "p50_ms": _percentile(durations, 0.50),
            "p95_ms": _percentile(durations, 0.95),
            "p99_ms": _percentile(durations, 0.99),
            "latest_ms": durations[0] if durations else None,
            "sample_size": len(durations),
        },
        "scraping": {
            "scrapes_total": snapshot["scrapes_total"],
            "scrapes_failed_total": snapshot["scrapes_failed_total"],
            "analysis_total": snapshot["analysis_total"],
            "generation_total": snapshot["generation_total"],
        },
    }
