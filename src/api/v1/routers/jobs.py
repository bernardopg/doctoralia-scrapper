import uuid
from typing import Any, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.schemas.common import UnifiedResult
from src.api.schemas.requests import JobCreateRequest, JobResponse
from src.api.v1._state import load_config
from src.api.v1.deps import require_api_key
from src.integrations.n8n.normalize import make_unified_result
from src.jobs.queue import get_queue
from src.jobs.tasks import scrape_and_process

router = APIRouter(tags=["Jobs"])


def _map_job_status(job: Any) -> str:
    result_status: Optional[str] = None
    result = getattr(job, "result", None)
    if isinstance(result, dict):
        raw_status = result.get("status")
        if isinstance(raw_status, str):
            result_status = raw_status
    elif result is not None:
        raw_status = getattr(result, "status", None)
        if isinstance(raw_status, str):
            result_status = raw_status

    if job.is_queued or job.is_deferred:
        return "pending"
    if job.is_started:
        return "running"
    if job.is_finished and result_status in {"completed", "failed"}:
        return result_status
    if job.is_failed:
        return "failed"
    if job.is_finished:
        return "completed"
    return "unknown"


@router.post(
    "/v1/jobs",
    response_model=JobResponse,
    dependencies=[Depends(require_api_key)],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(request: JobCreateRequest) -> JobResponse:
    from typing import cast

    config = load_config()
    if request.idempotency_key:
        r = redis.Redis.from_url(config.integrations.redis_url)
        existing_job_id = cast(
            bytes | str | None, r.get(f"idem:{request.idempotency_key}")
        )
        if existing_job_id:
            return JobResponse(
                job_id=(
                    existing_job_id.decode()
                    if isinstance(existing_job_id, bytes)
                    else existing_job_id
                ),
                status="queued",
                message="Job already exists",
            )

    job_id = str(uuid.uuid4())
    q = get_queue()
    q.enqueue(
        scrape_and_process,
        request.model_dump(),
        job_id,
        str(request.callback_url) if request.callback_url else None,
        job_id=job_id,
    )

    if request.idempotency_key:
        r = redis.Redis.from_url(config.integrations.redis_url)
        r.setex(f"idem:{request.idempotency_key}", 3600, job_id)

    return JobResponse(
        job_id=job_id,
        status="queued",
        message="Job created successfully",
    )


@router.get("/v1/jobs", dependencies=[Depends(require_api_key)])
async def list_jobs(
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

    q = get_queue()
    job_ids = set()
    normalized_filter = (status_filter or "").strip().lower()
    if normalized_filter == "queued":
        normalized_filter = "pending"

    if not normalized_filter or normalized_filter == "pending":
        job_ids.update(q.job_ids)
    if not normalized_filter or normalized_filter == "running":
        job_ids.update(StartedJobRegistry(queue=q).get_job_ids())
    if not normalized_filter or normalized_filter in {"completed", "failed"}:
        job_ids.update(FinishedJobRegistry(queue=q).get_job_ids())
    if not normalized_filter or normalized_filter == "failed":
        job_ids.update(FailedJobRegistry(queue=q).get_job_ids())

    jobs = []
    for jid in list(job_ids)[:100]:
        job = q.fetch_job(jid)
        if not job:
            continue

        job_status = _map_job_status(job)
        if normalized_filter and job_status != normalized_filter:
            continue

        progress = job.meta.get("progress", 0) if job.meta else 0
        if job_status == "completed":
            progress = 100

        jobs.append(
            {
                "task_id": job.id,
                "status": job_status,
                "progress": progress,
                "message": job.meta.get("message", "") if job.meta else "",
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            }
        )

    jobs.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return jobs


@router.get(
    "/v1/jobs/{job_id}",
    response_model=UnifiedResult,
    dependencies=[Depends(require_api_key)],
)
async def get_job_status(job_id: str):
    q = get_queue()
    job = q.fetch_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    job_status = _map_job_status(job)

    if job.result and (job.is_finished or job.is_failed):
        return job.result

    return make_unified_result(
        doctor_data={"name": "Processing", "url": ""},
        reviews_data=[],
        job_id=job_id,
        status=job_status,
    )
