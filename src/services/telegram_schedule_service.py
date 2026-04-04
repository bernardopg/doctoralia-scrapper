"""
Redis-backed schedule management and execution for Telegram notifications.
"""

from __future__ import annotations

import copy
import csv
import ipaddress
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import redis
import requests
from croniter import croniter  # type: ignore[import-untyped]

from config.settings import AppConfig
from src.integrations.n8n.normalize import extract_scraper_result
from src.jobs.queue import get_redis_connection
from src.response_generator import ResponseGenerator
from src.scraper import DoctoraliaScraper
from src.telegram_notifier import TelegramNotifier

VALID_RECURRENCE_TYPES = {"daily", "weekdays", "weekly", "interval", "custom_cron"}
VALID_REPORT_TYPES = {"simple", "complete", "health"}
VALID_ATTACHMENT_SCOPES = {"responses", "comments", "snapshot"}
VALID_ATTACHMENT_FORMATS = {"txt", "json", "csv"}
VALID_GENERATION_MODES = {"default", "local", "openai", "gemini", "claude"}
VALID_PARSE_MODES = {"", "Markdown", "MarkdownV2", "HTML"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _safe_json_loads(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        return cast(Dict[str, Any], json.loads(raw))
    if isinstance(raw, dict):
        return cast(Dict[str, Any], raw)
    raise ValueError("Unsupported schedule payload")


def _coerce_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_path(value: Any) -> Path:
    if isinstance(value, Path):
        return value
    return Path(str(value))


class TelegramScheduleService:
    """Manage Telegram schedules, history and background execution."""

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        logger: Optional[logging.Logger] = None,
        config_loader: Any = AppConfig.load,
        poll_interval_s: int = 30,
        history_limit: int = 200,
        redis_prefix: str = "doctoralia:telegram:schedules",
    ) -> None:
        self.redis = redis_client or get_redis_connection()
        self.logger = logger or logging.getLogger(__name__)
        self.config_loader = config_loader
        self.poll_interval_s = poll_interval_s
        self.history_limit = history_limit
        self.redis_prefix = redis_prefix
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._local_lock = threading.Lock()

    @property
    def schedules_key(self) -> str:
        return f"{self.redis_prefix}:definitions"

    @property
    def history_key(self) -> str:
        return f"{self.redis_prefix}:history"

    def _execution_lock_key(self, schedule_id: str, next_run_at: Optional[str]) -> str:
        suffix = next_run_at or "manual"
        return f"{self.redis_prefix}:lock:{schedule_id}:{suffix}"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="telegram-schedule-runner",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_due_schedules()
            except Exception as exc:  # pragma: no cover - daemon safety net
                self.logger.error("Telegram schedule loop failed: %s", exc)
            self._stop_event.wait(self.poll_interval_s)

    def list_schedules(self) -> List[Dict[str, Any]]:
        raw = cast(dict[Any, Any], self.redis.hgetall(self.schedules_key))
        schedules: List[Dict[str, Any]] = []
        for payload in raw.values():
            schedule = _safe_json_loads(payload)
            schedules.append(schedule)
        schedules.sort(
            key=lambda item: (item.get("next_run_at") or "", item.get("name") or "")
        )
        return schedules

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        payload = self.redis.hget(self.schedules_key, schedule_id)
        if not payload:
            return None
        return _safe_json_loads(payload)

    def list_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        entries = cast(
            list[Any], self.redis.lrange(self.history_key, 0, max(limit - 1, 0))
        )
        history = [_safe_json_loads(item) for item in entries]
        return history

    @staticmethod
    def _is_unspecified_host(host: str) -> bool:
        try:
            return ipaddress.ip_address(host).is_unspecified
        except ValueError:
            return False

    def get_summary(self) -> Dict[str, Any]:
        schedules = self.list_schedules()
        history = self.list_history(limit=100)
        active = [item for item in schedules if item.get("enabled")]
        last_success = next(
            (item for item in history if item.get("status") == "sent"),
            None,
        )
        last_failure = next(
            (item for item in history if item.get("status") == "failed"),
            None,
        )
        return {
            "total": len(schedules),
            "active": len(active),
            "paused": len(schedules) - len(active),
            "last_success_at": (
                last_success.get("completed_at") if last_success else None
            ),
            "last_failure_at": (
                last_failure.get("completed_at") if last_failure else None
            ),
        }

    def save_schedule(
        self, payload: Dict[str, Any], schedule_id: Optional[str] = None
    ) -> Dict[str, Any]:
        with self._local_lock:
            now = _utcnow()
            existing = self.get_schedule(schedule_id) if schedule_id else None
            normalized = self._normalize_schedule(payload, existing=existing, now=now)
            self.redis.hset(
                self.schedules_key,
                normalized["id"],
                json.dumps(normalized, ensure_ascii=False),
            )
            return normalized

    def delete_schedule(self, schedule_id: str) -> bool:
        return bool(self.redis.hdel(self.schedules_key, schedule_id))

    def claim_manual_execution(
        self, schedule_id: str, *, ttl_seconds: int = 1800
    ) -> Optional[str]:
        schedule = self.get_schedule(schedule_id)
        if schedule is None:
            return None

        lock_key = self._execution_lock_key(schedule_id, None)
        locked = self.redis.set(lock_key, "1", ex=ttl_seconds, nx=True)
        if not locked:
            return ""
        return lock_key

    def release_manual_execution(self, schedule_id: str) -> None:
        lock_key = self._execution_lock_key(schedule_id, None)
        try:
            self.redis.delete(lock_key)
        except Exception:
            # Lock TTL is the final safety net; deletion failure should not
            # surface as a user-facing schedule execution error.
            self.logger.debug(
                "Unable to release manual execution lock for %s",
                schedule_id,
            )

    def run_due_schedules(self) -> List[Dict[str, Any]]:
        now = _utcnow()
        results = []
        for schedule in self.list_schedules():
            if not schedule.get("enabled"):
                continue
            next_run_at = _parse_iso(schedule.get("next_run_at"))
            if next_run_at is None or next_run_at > now:
                continue
            result = self.execute_schedule(schedule["id"], manual=False)
            results.append(result)
        return results

    def execute_schedule(
        self, schedule_id: str, manual: bool = False
    ) -> Dict[str, Any]:
        schedule = self.get_schedule(schedule_id)
        if schedule is None:
            raise ValueError(f"Schedule {schedule_id} not found")

        execution_lock_key = self._execution_lock_key(
            schedule_id,
            None if manual else schedule.get("next_run_at"),
        )
        if not manual:
            locked = self.redis.set(execution_lock_key, "1", ex=1200, nx=True)
            if not locked:
                return {
                    "success": False,
                    "message": "Schedule already claimed by another worker",
                    "result": {"schedule_id": schedule_id},
                }

        completed_at = _utcnow()
        try:
            result = self._execute_schedule(schedule, manual=manual)
            status = "sent" if result.get("sent") else "failed"
            error = None if result.get("sent") else result.get("error")
        except Exception as exc:
            # Log full exception details server-side, but avoid storing or exposing them.
            self.logger.exception("Failed to execute schedule %s", schedule_id)
            status = "failed"
            error = "Schedule execution failed"
            result = {
                "sent": False,
                "error": error,
                "schedule_id": schedule_id,
                "schedule_name": schedule.get("name"),
            }
        finally:
            completed_at = _utcnow()

        updated = copy.deepcopy(schedule)
        updated["last_run_at"] = _isoformat(completed_at)
        updated["last_status"] = status
        updated["last_error"] = error
        updated["last_result"] = result
        updated["updated_at"] = _isoformat(completed_at)
        if updated.get("enabled"):
            updated["next_run_at"] = self._compute_next_run_at(
                updated, base_time=completed_at
            )
        self.redis.hset(
            self.schedules_key,
            updated["id"],
            json.dumps(updated, ensure_ascii=False),
        )

        history_entry = {
            "id": str(uuid.uuid4()),
            "schedule_id": updated["id"],
            "schedule_name": updated["name"],
            "status": status,
            "manual": manual,
            "run_at": updated.get("last_run_at"),
            "completed_at": _isoformat(completed_at),
            "summary": result.get("summary")
            or result.get("message")
            or updated["name"],
            "error": error,
            "metrics": result.get("metrics", {}),
            "attachment_path": result.get("attachment_path"),
        }
        self.redis.lpush(
            self.history_key, json.dumps(history_entry, ensure_ascii=False)
        )
        self.redis.ltrim(self.history_key, 0, self.history_limit - 1)

        return {
            "success": status == "sent",
            "message": history_entry["summary"],
            "result": result,
        }

    def send_test_notification(
        self,
        message: Optional[str] = None,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
    ) -> Dict[str, Any]:
        config = copy.deepcopy(self.config_loader())
        if telegram_token:
            config.telegram.token = telegram_token
        if telegram_chat_id:
            config.telegram.chat_id = telegram_chat_id
        config.telegram.parse_mode = (
            parse_mode if parse_mode in VALID_PARSE_MODES else ""
        )

        notifier = TelegramNotifier(config, self.logger)
        validation = notifier.validate_config()
        if not validation["valid"]:
            return {
                "success": False,
                "message": "Telegram configuration is invalid",
                "result": {"issues": validation["issues"]},
            }

        test_message = (
            message
            or "Teste de notificacao Doctoralia\nOrigem: scheduler da API\nStatus: ok"
        )
        sent = notifier.send_message(test_message)
        return {
            "success": sent,
            "message": (
                "Test notification sent" if sent else "Failed to send test notification"
            ),
            "result": {"sent": sent},
        }

    def _normalize_schedule(
        self,
        payload: Dict[str, Any],
        existing: Optional[Dict[str, Any]],
        now: datetime,
    ) -> Dict[str, Any]:
        schedule_id = existing["id"] if existing else str(uuid.uuid4())
        config = self.config_loader()

        recurrence_type = str(
            payload.get("recurrence_type")
            or (existing or {}).get("recurrence_type")
            or "daily"
        ).strip()
        if recurrence_type not in VALID_RECURRENCE_TYPES:
            raise ValueError("Unsupported recurrence_type")

        timezone_name = (
            _coerce_optional_str(payload.get("timezone"))
            or (existing or {}).get("timezone")
            or "America/Sao_Paulo"
        )
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:
            raise ValueError("Invalid timezone") from exc

        time_of_day = (
            _coerce_optional_str(payload.get("time_of_day"))
            if "time_of_day" in payload
            else None
        )
        if time_of_day is None and "time_of_day" not in payload:
            time_of_day = (existing or {}).get("time_of_day") or "09:00"
        if recurrence_type in {"daily", "weekdays", "weekly"}:
            if not self._is_valid_time_of_day(time_of_day):
                raise ValueError("time_of_day must be in HH:MM format")
        else:
            time_of_day = None

        day_of_week = payload.get("day_of_week") if "day_of_week" in payload else None
        if day_of_week is None and "day_of_week" not in payload:
            day_of_week = (existing or {}).get("day_of_week")
        if recurrence_type == "weekly":
            if day_of_week is None or int(day_of_week) not in range(0, 7):
                raise ValueError(
                    "day_of_week must be between 0 and 6 for weekly schedules"
                )
            day_of_week = int(day_of_week)
        else:
            day_of_week = None

        interval_minutes = (
            payload.get("interval_minutes") if "interval_minutes" in payload else None
        )
        if interval_minutes is None and "interval_minutes" not in payload:
            interval_minutes = (existing or {}).get("interval_minutes")
        if recurrence_type == "interval":
            if interval_minutes is None or int(interval_minutes) < 5:
                raise ValueError("interval_minutes must be at least 5")
            interval_minutes = int(interval_minutes)
        else:
            interval_minutes = None

        cron_expression = self._build_cron_expression(
            recurrence_type=recurrence_type,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            interval_minutes=interval_minutes,
            custom_expression=_coerce_optional_str(payload.get("cron_expression"))
            or (existing or {}).get("cron_expression"),
        )

        report_type = str(
            payload.get("report_type")
            or (existing or {}).get("report_type")
            or "complete"
        ).strip()
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError("Unsupported report_type")

        attachment_scope = str(
            payload.get("attachment_scope")
            or (existing or {}).get("attachment_scope")
            or "responses"
        ).strip()
        if attachment_scope not in VALID_ATTACHMENT_SCOPES:
            raise ValueError("Unsupported attachment_scope")

        attachment_format = str(
            payload.get("attachment_format")
            or (existing or {}).get("attachment_format")
            or config.telegram.attachment_format
            or "txt"
        ).strip()
        if attachment_format not in VALID_ATTACHMENT_FORMATS:
            raise ValueError("Unsupported attachment_format")

        generation_mode = str(
            payload.get("generation_mode")
            or (existing or {}).get("generation_mode")
            or "default"
        ).strip()
        if generation_mode not in VALID_GENERATION_MODES:
            raise ValueError("Unsupported generation_mode")

        parse_mode = str(
            payload.get("parse_mode")
            or (existing or {}).get("parse_mode")
            or config.telegram.parse_mode
            or ""
        ).strip()
        if parse_mode not in VALID_PARSE_MODES:
            raise ValueError("Unsupported parse_mode")

        trigger_new_scrape = bool(
            payload.get(
                "trigger_new_scrape",
                (existing or {}).get("trigger_new_scrape", True),
            )
        )
        include_generation = bool(
            payload.get(
                "include_generation",
                (existing or {}).get("include_generation", False),
            )
        )
        include_health_status = bool(
            payload.get(
                "include_health_status",
                (existing or {}).get("include_health_status", False),
            )
        )
        send_attachment = bool(
            payload.get(
                "send_attachment",
                (existing or {}).get("send_attachment", True),
            )
        )

        telegram_token = (
            _coerce_optional_str(payload.get("telegram_token"))
            if "telegram_token" in payload
            else None
        )
        if telegram_token is None and "telegram_token" not in payload:
            telegram_token = (existing or {}).get("telegram_token")
        telegram_chat_id = (
            _coerce_optional_str(payload.get("telegram_chat_id"))
            if "telegram_chat_id" in payload
            else None
        )
        if telegram_chat_id is None and "telegram_chat_id" not in payload:
            telegram_chat_id = (existing or {}).get("telegram_chat_id")
        if not (telegram_token or config.telegram.token):
            raise ValueError("Telegram token is required for schedules")
        if not (telegram_chat_id or config.telegram.chat_id):
            raise ValueError("Telegram chat_id is required for schedules")

        profile_url = (
            _coerce_optional_str(payload.get("profile_url"))
            if "profile_url" in payload
            else None
        )
        if profile_url is None and "profile_url" not in payload:
            profile_url = (existing or {}).get("profile_url")
        if trigger_new_scrape and not (profile_url or config.urls.profile_url):
            raise ValueError(
                "profile_url is required when trigger_new_scrape is enabled"
            )

        normalized = {
            "id": schedule_id,
            "name": _coerce_optional_str(payload.get("name"))
            or (existing or {}).get("name")
            or "Telegram Schedule",
            "enabled": bool(
                payload.get("enabled", (existing or {}).get("enabled", True))
            ),
            "timezone": timezone_name,
            "recurrence_type": recurrence_type,
            "time_of_day": time_of_day,
            "day_of_week": day_of_week,
            "interval_minutes": interval_minutes,
            "cron_expression": cron_expression,
            "recurrence_label": self._build_recurrence_label(
                recurrence_type=recurrence_type,
                time_of_day=time_of_day,
                day_of_week=day_of_week,
                interval_minutes=interval_minutes,
                cron_expression=cron_expression,
            ),
            "profile_url": profile_url,
            "profile_label": (
                _coerce_optional_str(payload.get("profile_label"))
                if "profile_label" in payload
                else (existing or {}).get("profile_label")
            ),
            "trigger_new_scrape": trigger_new_scrape,
            "include_generation": include_generation,
            "generation_mode": generation_mode,
            "report_type": report_type,
            "include_health_status": include_health_status,
            "send_attachment": send_attachment,
            "attachment_scope": attachment_scope,
            "attachment_format": attachment_format,
            "max_reviews": int(
                payload.get("max_reviews") or (existing or {}).get("max_reviews") or 20
            ),
            "telegram_token": telegram_token,
            "telegram_chat_id": telegram_chat_id,
            "parse_mode": parse_mode,
            "last_run_at": (existing or {}).get("last_run_at"),
            "last_status": (existing or {}).get("last_status"),
            "last_error": (existing or {}).get("last_error"),
            "last_result": (existing or {}).get("last_result"),
            "created_at": (existing or {}).get("created_at") or _isoformat(now),
            "updated_at": _isoformat(now),
        }
        normalized["next_run_at"] = (
            self._compute_next_run_at(normalized, base_time=now)
            if normalized["enabled"]
            else None
        )
        return normalized

    @staticmethod
    def _is_valid_time_of_day(value: Optional[str]) -> bool:
        if not value or ":" not in value:
            return False
        parts = value.split(":", 1)
        if len(parts) != 2:
            return False
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return False
        return 0 <= hour <= 23 and 0 <= minute <= 59

    def _build_cron_expression(
        self,
        recurrence_type: str,
        time_of_day: Optional[str],
        day_of_week: Optional[int],
        interval_minutes: Optional[int],
        custom_expression: Optional[str],
    ) -> Optional[str]:
        if recurrence_type == "interval":
            return None

        if recurrence_type == "custom_cron":
            if not custom_expression:
                raise ValueError(
                    "cron_expression is required for custom_cron schedules"
                )
            croniter(custom_expression, _utcnow())
            return custom_expression

        hour, minute = (time_of_day or "09:00").split(":", 1)
        if recurrence_type == "daily":
            return f"{int(minute)} {int(hour)} * * *"
        if recurrence_type == "weekdays":
            return f"{int(minute)} {int(hour)} * * 1-5"
        if recurrence_type == "weekly":
            normalized_day_of_week = 0 if day_of_week is None else int(day_of_week)
            return f"{int(minute)} {int(hour)} * * {normalized_day_of_week}"
        raise ValueError("Unsupported recurrence_type")

    def _build_recurrence_label(
        self,
        recurrence_type: str,
        time_of_day: Optional[str],
        day_of_week: Optional[int],
        interval_minutes: Optional[int],
        cron_expression: Optional[str],
    ) -> str:
        if recurrence_type == "daily":
            return f"Diariamente às {time_of_day}"
        if recurrence_type == "weekdays":
            return f"Dias úteis às {time_of_day}"
        if recurrence_type == "weekly":
            weekday_names = {
                0: "domingo",
                1: "segunda",
                2: "terça",
                3: "quarta",
                4: "quinta",
                5: "sexta",
                6: "sábado",
            }
            normalized_day_of_week = 0 if day_of_week is None else day_of_week
            return (
                f"Semanal ({weekday_names.get(normalized_day_of_week, 'dia')})"
                f" às {time_of_day}"
            )
        if recurrence_type == "interval":
            return f"A cada {interval_minutes} minuto(s)"
        return f"Cron customizado: {cron_expression}"

    def _compute_next_run_at(
        self, schedule: Dict[str, Any], base_time: Optional[datetime] = None
    ) -> Optional[str]:
        base = (base_time or _utcnow()).astimezone(ZoneInfo(schedule["timezone"]))
        recurrence_type = schedule["recurrence_type"]

        if recurrence_type == "interval":
            interval_minutes = int(schedule.get("interval_minutes") or 15)
            reference = _parse_iso(schedule.get("last_run_at")) or base
            next_run = reference + timedelta(minutes=interval_minutes)
            return _isoformat(next_run)

        cron_expression = schedule.get("cron_expression")
        if not cron_expression:
            return None
        iterator = croniter(cron_expression, base)
        next_run = iterator.get_next(datetime)
        return _isoformat(next_run)

    def _execute_schedule(
        self, schedule: Dict[str, Any], manual: bool = False
    ) -> Dict[str, Any]:
        runtime_config = copy.deepcopy(self.config_loader())
        runtime_config.telegram.token = (
            schedule.get("telegram_token") or runtime_config.telegram.token
        )
        runtime_config.telegram.chat_id = (
            schedule.get("telegram_chat_id") or runtime_config.telegram.chat_id
        )
        runtime_config.telegram.parse_mode = schedule.get("parse_mode") or ""
        runtime_config.telegram.attachment_format = (
            schedule.get("attachment_format") or "txt"
        )
        runtime_config.telegram.enabled = True
        if schedule.get("generation_mode") and schedule["generation_mode"] != "default":
            runtime_config.generation.mode = schedule["generation_mode"]

        notifier = TelegramNotifier(runtime_config, self.logger)
        validation = notifier.validate_config()
        if not validation["valid"]:
            raise ValueError(", ".join(validation["issues"]))

        doctor_data: Dict[str, Any] = {}
        reviews_data: List[Dict[str, Any]] = []
        generated_responses: List[Dict[str, Any]] = []
        snapshot_payload: Optional[Dict[str, Any]] = None
        snapshot_path: Optional[Path] = None

        if schedule.get("report_type") != "health" or schedule.get(
            "trigger_new_scrape"
        ):
            snapshot_payload, snapshot_path = self._resolve_snapshot(
                schedule, runtime_config
            )
            if snapshot_payload:
                doctor_data, reviews_data = extract_scraper_result(snapshot_payload)

        if schedule.get("include_generation") and reviews_data:
            generated_responses = self._generate_responses(
                reviews_data=reviews_data,
                doctor_data=doctor_data,
                runtime_config=runtime_config,
                generation_mode=schedule.get("generation_mode"),
                max_reviews=int(schedule.get("max_reviews") or 20),
            )
            if snapshot_payload is not None and generated_responses:
                snapshot_payload["reviews"] = reviews_data
                snapshot_payload["total_reviews"] = len(reviews_data)
                snapshot_path = self._save_snapshot(snapshot_payload, runtime_config)

        health_snapshot = (
            self._collect_health_snapshot(runtime_config)
            if schedule.get("include_health_status")
            else {}
        )

        attachment_path = None
        if schedule.get("send_attachment"):
            attachment_path = self._build_attachment(
                schedule=schedule,
                runtime_config=runtime_config,
                notifier=notifier,
                doctor_data=doctor_data,
                reviews_data=reviews_data,
                generated_responses=generated_responses,
                snapshot_payload=snapshot_payload,
            )

        summary_message = self._build_report_message(
            schedule=schedule,
            doctor_data=doctor_data,
            reviews_data=reviews_data,
            generated_responses=generated_responses,
            health_snapshot=health_snapshot,
            snapshot_path=snapshot_path,
        )

        sent = False
        if attachment_path is not None:
            sent = notifier.send_document(attachment_path, summary_message)
        else:
            sent = notifier.send_message(summary_message)

        metrics = {
            "total_reviews": len(reviews_data),
            "generated_responses": len(generated_responses),
            "scraped": bool(schedule.get("trigger_new_scrape")),
            "health_checks": health_snapshot,
            "profile_url": schedule.get("profile_url")
            or runtime_config.urls.profile_url,
            "manual": manual,
        }
        return {
            "sent": sent,
            "summary": summary_message.splitlines()[0].replace("*", "").strip(),
            "attachment_path": str(attachment_path) if attachment_path else None,
            "metrics": metrics,
            "doctor_name": doctor_data.get("name"),
            "error": (
                None if sent else "Telegram send_message/send_document returned False"
            ),
        }

    def _resolve_snapshot(
        self, schedule: Dict[str, Any], runtime_config: Any
    ) -> tuple[Optional[Dict[str, Any]], Optional[Path]]:
        profile_url = schedule.get("profile_url") or runtime_config.urls.profile_url
        if schedule.get("trigger_new_scrape"):
            if not profile_url:
                raise ValueError("profile_url is required to run a fresh scrape")
            scraper = DoctoraliaScraper(runtime_config, logger=self.logger)
            snapshot_payload = scraper.scrape_reviews(profile_url)
            if not snapshot_payload:
                raise RuntimeError(
                    "Scraper returned no data for scheduled notification"
                )
            snapshot_path = scraper.save_data(snapshot_payload)
            return snapshot_payload, snapshot_path
        return self._load_latest_snapshot(runtime_config.data_dir, profile_url)

    def _load_latest_snapshot(
        self, data_dir: Path, profile_url: Optional[str]
    ) -> tuple[Optional[Dict[str, Any]], Optional[Path]]:
        data_dir = _as_path(data_dir)
        if not data_dir.exists():
            raise FileNotFoundError("data directory not found")

        for json_file in sorted(
            data_dir.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            try:
                with open(json_file, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                candidate_url = _coerce_optional_str(
                    payload.get("url")
                ) or _coerce_optional_str(payload.get("profile_url"))
                if (
                    profile_url
                    and candidate_url
                    and candidate_url.rstrip("/") != profile_url.rstrip("/")
                ):
                    continue
                return payload, json_file
            except Exception:
                continue
        raise FileNotFoundError("No snapshot available for the requested profile")

    def _generate_responses(
        self,
        reviews_data: List[Dict[str, Any]],
        doctor_data: Dict[str, Any],
        runtime_config: Any,
        generation_mode: Optional[str],
        max_reviews: int,
    ) -> List[Dict[str, Any]]:
        generator = ResponseGenerator(runtime_config, logger=self.logger)
        pending_reviews = [
            review
            for review in reviews_data
            if not review.get("doctor_reply") and not review.get("generated_response")
        ][:max_reviews]

        results = []
        for review in pending_reviews:
            try:
                response = generator.generate_response_with_metadata(
                    review,
                    doctor_context=doctor_data,
                    generation_mode=generation_mode,
                    language="pt-BR",
                )
                review["generated_response"] = response["text"]
                results.append(
                    {
                        "review_id": review.get("id"),
                        "author": review.get("author", "Paciente"),
                        "comment": review.get("comment", ""),
                        "date": review.get("date", ""),
                        "rating": review.get("rating", ""),
                        "response": response["text"],
                    }
                )
            except Exception as exc:
                self.logger.warning(
                    "Scheduled generation failed for review %s: %s",
                    review.get("id"),
                    exc,
                )
        return results

    def _build_attachment(
        self,
        schedule: Dict[str, Any],
        runtime_config: Any,
        notifier: TelegramNotifier,
        doctor_data: Dict[str, Any],
        reviews_data: List[Dict[str, Any]],
        generated_responses: List[Dict[str, Any]],
        snapshot_payload: Optional[Dict[str, Any]],
    ) -> Optional[Path]:
        scope = schedule.get("attachment_scope") or "responses"
        if scope == "responses":
            if not generated_responses:
                return None
            return notifier._create_attachment_file(generated_responses)

        notifications_dir = Path(runtime_config.data_dir) / "notifications"
        notifications_dir.mkdir(parents=True, exist_ok=True)
        extension = schedule.get("attachment_format") or "txt"
        file_path = notifications_dir / (
            f"{schedule['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
        )

        if scope == "comments":
            payload = {
                "doctor": doctor_data,
                "total": len(reviews_data),
                "items": reviews_data,
            }
        else:
            payload = {
                "doctor": doctor_data,
                "total_reviews": len(reviews_data),
                "generated_responses": generated_responses,
                "snapshot": snapshot_payload,
            }

        self._write_attachment(file_path, payload, extension)
        return file_path

    def _write_attachment(
        self, file_path: Path, payload: Dict[str, Any], extension: str
    ) -> None:
        if extension == "json":
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            return

        if extension == "csv":
            rows = payload.get("generated_responses") or payload.get("items") or []
            with open(file_path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    ["review_id", "author", "rating", "date", "comment", "response"]
                )
                for row in rows:
                    writer.writerow(
                        [
                            row.get("review_id", ""),
                            row.get("author", ""),
                            row.get("rating", ""),
                            row.get("date", ""),
                            row.get("comment", ""),
                            row.get("response", ""),
                        ]
                    )
            return

        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("RELATORIO AGENDADO DOCTORALIA\n")
            handle.write("=" * 48 + "\n\n")
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))

    def _save_snapshot(
        self, payload: Dict[str, Any], runtime_config: Any
    ) -> Optional[Path]:
        data_dir = _as_path(runtime_config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doctor_name = str(payload.get("doctor_name") or "notification_snapshot")
        safe_name = (
            "".join(ch for ch in doctor_name if ch.isalnum() or ch in {"_", "-", " "})
            .strip()
            .replace(" ", "_")
            .lower()
        )
        file_path = data_dir / f"{timestamp}_{safe_name}.json"
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return file_path

    def _collect_health_snapshot(self, runtime_config: Any) -> Dict[str, Any]:
        api_base_url = (
            _coerce_optional_str(getattr(runtime_config.integrations, "api_url", None))
            or f"http://127.0.0.1:{getattr(runtime_config.api, 'port', 8000)}"
        )
        snapshot: Dict[str, Any] = {}
        parsed_api_url = urlparse(api_base_url)
        api_host = (parsed_api_url.hostname or "").strip().lower()
        default_port = 443 if parsed_api_url.scheme == "https" else 80
        api_port = parsed_api_url.port or default_port
        local_api_port = int(getattr(runtime_config.api, "port", 8000))
        is_local_host = api_host in {
            "127.0.0.1",
            "localhost",
        } or self._is_unspecified_host(api_host)
        is_in_process_api = is_local_host and api_port == local_api_port
        try:
            if is_in_process_api:
                snapshot["api"] = {"status": "ok", "mode": "in-process"}
            else:
                response = requests.get(
                    f"{api_base_url.rstrip('/')}/v1/ready", timeout=5
                )
                payload = response.json()
                snapshot["api"] = {
                    "status": "ok" if payload.get("ready") else "degraded",
                    "http_status": response.status_code,
                    "ready": payload.get("ready"),
                }
        except Exception as exc:
            snapshot["api"] = {"status": "error", "error": str(exc)[:200]}

        try:
            redis_client = redis.Redis.from_url(runtime_config.integrations.redis_url)
            redis_client.ping()
            snapshot["redis"] = {"status": "ok"}
        except Exception as exc:
            snapshot["redis"] = {"status": "error", "error": str(exc)[:200]}

        try:
            selenium_url = runtime_config.integrations.selenium_remote_url.rstrip("/")
            response = requests.get(f"{selenium_url}/status", timeout=5)
            snapshot["selenium"] = {
                "status": "ok" if response.ok else "error",
                "http_status": response.status_code,
            }
        except Exception as exc:
            snapshot["selenium"] = {"status": "error", "error": str(exc)[:200]}
        return snapshot

    def _build_report_message(
        self,
        schedule: Dict[str, Any],
        doctor_data: Dict[str, Any],
        reviews_data: List[Dict[str, Any]],
        generated_responses: List[Dict[str, Any]],
        health_snapshot: Dict[str, Any],
        snapshot_path: Optional[Path],
    ) -> str:
        report_type = schedule.get("report_type") or "complete"
        lines = [f"📣 *{schedule['name']}*"]
        lines.append(f"🗓️ Execução: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

        if report_type != "health":
            lines.append(
                f"👨‍⚕️ Perfil: {doctor_data.get('name') or schedule.get('profile_label') or 'Perfil monitorado'}"
            )
            lines.append(f"📝 Reviews analisados: {len(reviews_data)}")
            if doctor_data.get("rating") is not None:
                lines.append(f"⭐ Avaliação média: {doctor_data.get('rating')}")
            if generated_responses:
                lines.append(f"🤖 Respostas geradas: {len(generated_responses)}")
            if snapshot_path is not None:
                lines.append(f"📁 Snapshot: `{snapshot_path.name}`")

        if schedule.get("include_health_status") and health_snapshot:
            api_status = health_snapshot.get("api", {}).get("status", "unknown")
            redis_status = health_snapshot.get("redis", {}).get("status", "unknown")
            selenium_status = health_snapshot.get("selenium", {}).get(
                "status", "unknown"
            )
            lines.append(
                f"🩺 Stack: API {api_status} • Redis {redis_status} • Selenium {selenium_status}"
            )

        if report_type == "complete" and reviews_data:
            preview = reviews_data[:3]
            lines.append("")
            lines.append("*Prévia operacional*")
            for review in preview:
                author = str(review.get("author") or "Paciente")
                comment = str(review.get("comment") or "").strip()
                comment = comment[:80] + "..." if len(comment) > 80 else comment
                lines.append(f"• {author}: {comment or 'Sem comentário'}")

        if report_type == "health":
            lines.append("🛠️ Relatório focado em saúde operacional.")

        return "\n".join(lines)
