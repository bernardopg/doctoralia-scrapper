import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from src.api.schemas.notifications import (
    TelegramNotificationHistoryResponse,
    TelegramNotificationRunResponse,
    TelegramNotificationScheduleListResponse,
    TelegramNotificationScheduleModel,
    TelegramNotificationTestRequest,
)
from src.api.v1._helpers import raise_public_http_error
from src.api.v1._state import (
    SCHEDULE_RUN_ACCEPTED_MESSAGE,
    SCHEDULE_RUN_ALREADY_RUNNING_MESSAGE,
    SCHEDULE_RUN_FAILURE_MESSAGE,
    SCHEDULE_RUN_HEALTH_CHECK_ERROR,
    SCHEDULE_RUN_SUCCESS_MESSAGE,
    get_telegram_schedule_service,
)
from src.api.v1.deps import require_api_key
from src.jobs.queue import get_queue
from src.jobs.tasks import run_telegram_schedule_job

router = APIRouter(tags=["Notifications"])


def _sanitize_schedule_run_metrics(raw_metrics: Any) -> dict[str, Any]:
    if not isinstance(raw_metrics, dict):
        return {}

    safe_metrics: dict[str, Any] = {}
    for field in (
        "total_reviews",
        "generated_responses",
        "scraped",
        "profile_url",
        "manual",
    ):
        if field in raw_metrics:
            safe_metrics[field] = raw_metrics[field]

    health_checks = raw_metrics.get("health_checks")
    if isinstance(health_checks, dict):
        safe_health_checks: dict[str, Any] = {}
        for component, component_data in health_checks.items():
            if not isinstance(component_data, dict):
                safe_health_checks[component] = component_data
                continue

            safe_component = {
                key: value for key, value in component_data.items() if key != "error"
            }
            if component_data.get("error"):
                safe_component["error"] = SCHEDULE_RUN_HEALTH_CHECK_ERROR
            safe_health_checks[component] = safe_component

        safe_metrics["health_checks"] = safe_health_checks

    return safe_metrics


def _sanitize_schedule_run_response(raw_response: dict[str, Any]) -> dict[str, Any]:
    raw_result = raw_response.get("result")
    safe_result: dict[str, Any] = {}

    if isinstance(raw_result, dict):
        if raw_result.get("error"):
            safe_result["error"] = SCHEDULE_RUN_FAILURE_MESSAGE

        for field in ("sent", "schedule_id", "schedule_name", "doctor_name"):
            if field in raw_result:
                safe_result[field] = raw_result[field]

        if "metrics" in raw_result:
            safe_result["metrics"] = _sanitize_schedule_run_metrics(
                raw_result["metrics"]
            )

    success = bool(raw_response.get("success"))
    return {
        "success": success,
        "message": (
            SCHEDULE_RUN_SUCCESS_MESSAGE if success else SCHEDULE_RUN_FAILURE_MESSAGE
        ),
        "result": safe_result,
    }


@router.get(
    "/v1/notifications/telegram/schedules",
    response_model=TelegramNotificationScheduleListResponse,
    dependencies=[Depends(require_api_key)],
)
async def list_telegram_notification_schedules():
    service = get_telegram_schedule_service(start_runner=True)
    return {
        "schedules": service.list_schedules(),
        "summary": service.get_summary(),
    }


@router.post(
    "/v1/notifications/telegram/schedules",
    response_model=dict,
    dependencies=[Depends(require_api_key)],
)
async def create_telegram_notification_schedule(
    schedule: TelegramNotificationScheduleModel,
):
    try:
        service = get_telegram_schedule_service(start_runner=True)
        saved = service.save_schedule(schedule.model_dump())
        return {"success": True, "schedule": saved}
    except ValueError as exc:
        raise_public_http_error(
            status.HTTP_400_BAD_REQUEST,
            "Invalid schedule payload",
            exc=exc,
        )


@router.put(
    "/v1/notifications/telegram/schedules/{schedule_id}",
    response_model=dict,
    dependencies=[Depends(require_api_key)],
)
async def update_telegram_notification_schedule(
    schedule_id: str,
    schedule: TelegramNotificationScheduleModel,
):
    try:
        service = get_telegram_schedule_service(start_runner=True)
        if service.get_schedule(schedule_id) is None:
            raise HTTPException(status_code=404, detail="Schedule not found")
        saved = service.save_schedule(schedule.model_dump(), schedule_id=schedule_id)
        return {"success": True, "schedule": saved}
    except ValueError as exc:
        raise_public_http_error(
            status.HTTP_400_BAD_REQUEST,
            "Invalid schedule payload",
            exc=exc,
        )


@router.delete(
    "/v1/notifications/telegram/schedules/{schedule_id}",
    response_model=dict,
    dependencies=[Depends(require_api_key)],
)
async def delete_telegram_notification_schedule(schedule_id: str):
    service = get_telegram_schedule_service(start_runner=True)
    deleted = service.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


@router.post(
    "/v1/notifications/telegram/schedules/{schedule_id}/run",
    response_model=TelegramNotificationRunResponse,
    dependencies=[Depends(require_api_key)],
)
async def run_telegram_notification_schedule(
    schedule_id: str,
    wait: bool = Query(
        default=True,
        description="When false, enqueue the execution in RQ and return immediately.",
    ),
):
    try:
        service = get_telegram_schedule_service(start_runner=True)
        if not wait:
            schedule = service.get_schedule(schedule_id)
            if schedule is None:
                raise ValueError(f"Schedule {schedule_id} not found")

            manual_lock_key = service.claim_manual_execution(schedule_id)
            if manual_lock_key is None:
                raise ValueError(f"Schedule {schedule_id} not found")
            if manual_lock_key == "":
                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "success": True,
                        "message": SCHEDULE_RUN_ALREADY_RUNNING_MESSAGE,
                        "result": {
                            "queued": False,
                            "already_running": True,
                            "schedule_id": schedule_id,
                            "schedule_name": schedule.get("name"),
                        },
                    },
                )

            job_id = f"telegram-schedule-{uuid.uuid4()}"
            try:
                q = get_queue()
                q.enqueue(
                    run_telegram_schedule_job,
                    schedule_id,
                    manual_lock_key,
                    job_id=job_id,
                    job_timeout=1800,
                    result_ttl=86400,
                )
            except Exception:
                service.release_manual_execution(schedule_id)
                raise

            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "success": True,
                    "message": SCHEDULE_RUN_ACCEPTED_MESSAGE,
                    "result": {
                        "queued": True,
                        "job_id": job_id,
                        "schedule_id": schedule_id,
                        "schedule_name": schedule.get("name"),
                    },
                },
            )

        result = service.execute_schedule(schedule_id, manual=True)
        return _sanitize_schedule_run_response(result)
    except ValueError as exc:
        raise_public_http_error(
            status.HTTP_404_NOT_FOUND,
            "Schedule not found",
            exc=exc,
        )
    except Exception as exc:
        raise_public_http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Failed to start schedule execution",
            exc=exc,
        )


@router.get(
    "/v1/notifications/telegram/history",
    response_model=TelegramNotificationHistoryResponse,
    dependencies=[Depends(require_api_key)],
)
async def list_telegram_notification_history(
    limit: int = Query(default=50, ge=1, le=200),
):
    service = get_telegram_schedule_service(start_runner=True)
    return {"history": service.list_history(limit=limit)}


@router.post(
    "/v1/notifications/telegram/test",
    response_model=TelegramNotificationRunResponse,
    dependencies=[Depends(require_api_key)],
)
async def send_test_telegram_notification(payload: TelegramNotificationTestRequest):
    service = get_telegram_schedule_service(start_runner=True)
    result = service.send_test_notification(
        message=payload.message,
        telegram_token=payload.telegram_token,
        telegram_chat_id=payload.telegram_chat_id,
        parse_mode=payload.parse_mode or "Markdown",
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
