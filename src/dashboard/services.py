"""Shared service container passed to all dashboard blueprints."""

from __future__ import annotations

import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from flask import request, session

from src.auth import get_dashboard_auth_state
from src.config.settings import AppConfig
from src.performance_monitor import PerformanceMonitor
from src.response_quality_analyzer import ResponseQualityAnalyzer
from src.services.stats import StatsService
from src.services.workspace_service import WorkspaceService


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@dataclass
class DashboardServices:
    config: Any
    logger: Any
    performance_monitor: PerformanceMonitor
    quality_analyzer: ResponseQualityAnalyzer
    stats_service: StatsService
    workspace_service: WorkspaceService
    api_port: int = 8000
    api_timeout: int = 5

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _get_runtime_config(self) -> Any:
        try:
            return AppConfig.load()
        except Exception:
            return self.config

    def get_api_base_url(self) -> str:
        config = self._get_runtime_config()
        api_url = _clean_optional(
            getattr(getattr(config, "integrations", None), "api_url", None)
        ) or _clean_optional(os.getenv("API_URL"))
        if api_url:
            return api_url
        port = getattr(getattr(config, "api", None), "port", self.api_port)
        return f"http://localhost:{port}"

    def get_api_docs_url(self) -> str:
        config = self._get_runtime_config()
        public_url = _clean_optional(
            getattr(getattr(config, "integrations", None), "api_public_url", None)
        ) or _clean_optional(os.getenv("API_PUBLIC_URL"))
        return f"{public_url}/docs" if public_url else ""

    def get_api_key(self) -> Optional[str]:
        config = self._get_runtime_config()
        return _clean_optional(
            getattr(getattr(config, "security", None), "api_key", None)
        ) or _clean_optional(os.getenv("API_KEY"))

    def get_data_directory(self) -> Path:
        if self.config and hasattr(self.config, "data_dir"):
            return Path(self.config.data_dir)
        return Path("data")

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def get_dashboard_auth_state(self):
        return get_dashboard_auth_state(self._get_runtime_config())

    def is_auth_enabled(self, app_config: Dict[str, Any]) -> bool:
        if app_config.get("AUTH_FORCE_DISABLED"):
            return False
        if app_config.get("AUTH_FORCE_ENABLED"):
            return True
        if app_config.get("TESTING"):
            return False
        return bool(self.get_dashboard_auth_state().enabled)

    def is_authenticated(self, app_config: Dict[str, Any]) -> bool:
        if not self.is_auth_enabled(app_config):
            return True
        return bool(session.get("dashboard_authenticated"))

    def login_session_user(self) -> None:
        auth_state = self.get_dashboard_auth_state()
        csrf_token = session.get("csrf_token") or secrets.token_urlsafe(32)
        session.clear()
        session.permanent = True
        session["csrf_token"] = csrf_token
        session["dashboard_authenticated"] = True
        session["dashboard_username"] = auth_state.username
        session["dashboard_authenticated_at"] = datetime.now().isoformat()

    def logout_session_user(self) -> None:
        session.clear()

    def csrf_token(self) -> str:
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return str(token)

    def is_csrf_valid(self) -> bool:
        expected = session.get("csrf_token")
        submitted = (
            request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
        )
        return bool(
            expected
            and submitted
            and hmac.compare_digest(str(expected), str(submitted))
        )

    # ------------------------------------------------------------------
    # API proxy helpers
    # ------------------------------------------------------------------

    def _api_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        api_key = self.get_api_key()
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    def call_api(self, endpoint: str, method: str = "GET", **kwargs) -> Optional[Dict]:
        try:
            url = f"{self.get_api_base_url()}{endpoint}"
            resp = requests.request(
                method,
                url,
                headers=self._api_headers(),
                timeout=self.api_timeout,
                **kwargs,
            )
            resp.raise_for_status()
            data: Optional[Dict] = resp.json()
            return data
        except requests.exceptions.HTTPError as e:
            if self.logger:
                self.logger.warning("API HTTP error %s %s: %s", method, endpoint, e)
            return None
        except Exception as e:
            if self.logger:
                self.logger.debug("API call failed %s %s: %s", method, endpoint, e)
            return None

    def request_api_with_status(self, endpoint: str, method: str = "GET", **kwargs):
        """Return (payload, status_code) or (None, None) on connection failure."""
        try:
            url = f"{self.get_api_base_url()}{endpoint}"
            resp = requests.request(
                method,
                url,
                headers=self._api_headers(),
                timeout=self.api_timeout,
                **kwargs,
            )
            try:
                payload = resp.json()
            except ValueError:
                payload = {"error": resp.text}
            return payload, resp.status_code
        except Exception as e:
            if self.logger:
                self.logger.debug("API request failed %s %s: %s", method, endpoint, e)
            return None, None

    def proxy_api_response(self, endpoint: str, method: str = "GET", **kwargs):
        """Forward request to API, return Flask response."""
        from flask import jsonify

        payload, status_code = self.request_api_with_status(
            endpoint, method=method, **kwargs
        )
        if payload is None:
            return jsonify({"error": "API não disponível"}), 503
        return jsonify(payload), status_code

    def get_api_health(self) -> Dict[str, Any]:
        api_base_url = self.get_api_base_url()
        api_data = self.call_api("/v1/health")
        if api_data:
            return {
                "status": "connected",
                "api_url": api_base_url,
                "api_data": api_data,
            }
        return {
            "status": "disconnected",
            "api_url": api_base_url,
            "message": "API não está acessível",
        }

    def get_api_statistics(self) -> Optional[Dict[str, Any]]:
        return self.call_api("/v1/statistics")

    def get_api_metrics(self) -> Optional[Dict[str, Any]]:
        return self.call_api("/v1/metrics")

    def update_remote_settings(
        self, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        response = self.call_api("/v1/settings")
        if not response or not response.get("success"):
            return None
        current = (response.get("settings") or {}).copy()
        current.update(updates)
        result = self.call_api("/v1/settings", method="PUT", json=current)
        if result and result.get("success"):
            return result.get("settings")
        return None

    def get_user_profile_settings(self) -> Dict[str, Any]:
        settings = self.call_api("/v1/settings")
        if settings and settings.get("success"):
            remote = settings.get("settings") or {}
            profile = remote.get("user_profile", {})
            if isinstance(profile, dict):
                return profile

        config = self._get_runtime_config()
        user_profile = getattr(config, "user_profile", None)
        if user_profile is not None:
            return {
                "display_name": getattr(user_profile, "display_name", "Administrador"),
                "username": getattr(user_profile, "username", "admin"),
                "favorite_profiles": [
                    {
                        "name": fav.name,
                        "profile_url": fav.profile_url,
                        "specialty": fav.specialty,
                        "notes": fav.notes,
                    }
                    for fav in getattr(user_profile, "favorite_profiles", [])
                ],
            }
        return {
            "display_name": "Administrador",
            "username": "admin",
            "favorite_profiles": [],
        }

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    def log_exception(self, message: str, exc: BaseException) -> None:
        if self.logger:
            self.logger.error(message, exc_info=(type(exc), exc, exc.__traceback__))

    def error_payload(
        self,
        message: str,
        status_code: int = 500,
        exc: Optional[BaseException] = None,
    ) -> Dict[str, Any]:
        if exc is not None:
            self.log_exception(message, exc)
        return {"error": message}

    def error_response(
        self,
        message: str,
        status_code: int = 500,
        exc: Optional[BaseException] = None,
    ):
        from flask import jsonify

        return jsonify(self.error_payload(message, status_code, exc)), status_code

    # ------------------------------------------------------------------
    # Data helpers (used by reports / api_proxy blueprints)
    # ------------------------------------------------------------------

    def get_trend_data(self) -> Dict[str, Any]:
        try:
            return self.stats_service.get_trend_data()
        except Exception as e:
            if self.logger:
                self.logger.error("Error getting trend data: %s", e)
            return {"dates": [], "reviews": [], "scrapes": []}

    def get_scraper_stats(self) -> Dict[str, Any]:
        try:
            return self.stats_service.get_scraper_stats()
        except Exception as e:
            if self.logger:
                self.logger.error("Error getting scraper stats: %s", e)
            return {
                "total_scraped_doctors": 0,
                "total_reviews": 0,
                "average_rating": 0.0,
                "last_scrape_time": None,
                "data_files": [],
                "platform_stats": {},
            }

    def get_recent_activities(self) -> List[Dict[str, Any]]:
        activities: List[Dict[str, Any]] = []
        try:
            data_dir = self.get_data_directory()
            if data_dir and data_dir.exists():
                json_files = sorted(
                    data_dir.glob("*.json"), key=os.path.getmtime, reverse=True
                )[:10]
                for json_file in json_files:
                    item = self._extract_activity_data(json_file)
                    if item:
                        activities.append(item)
        except Exception as e:
            if self.logger:
                self.logger.error("Error getting recent activities: %s", e)
        return activities

    def _extract_activity_data(self, json_file: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            doctor_name = data.get("doctor_name") or data.get("doctor", {}).get(
                "name", "Unknown"
            )
            reviews = data.get("reviews", [])
            reviews_count = data.get("total_reviews", 0) or len(reviews)
            if "summary" in data:
                average_rating = data["summary"].get("average_rating", 0.0)
            else:
                ratings = [r.get("rating", 0) for r in reviews if r.get("rating")]
                average_rating = sum(ratings) / len(ratings) if ratings else 0.0
            scraped_at = data.get("scraped_at") or data.get("extraction_timestamp")
            return {
                "filename": json_file.name,
                "doctor_name": doctor_name,
                "platform": data.get("platform", "doctoralia"),
                "reviews_count": reviews_count,
                "average_rating": average_rating,
                "scraped_at": scraped_at,
                "file_size": json_file.stat().st_size,
            }
        except Exception as e:
            if self.logger:
                self.logger.warning("Error reading activity %s: %s", json_file, e)
            return None

    def get_recent_logs(self, lines: int = 50) -> List[str]:
        try:
            if self.config and hasattr(self.config, "logs_dir"):
                logs_dir = Path(self.config.logs_dir)
                if logs_dir.exists():
                    log_files = list(logs_dir.glob("*.log"))
                    if log_files:
                        latest = max(log_files, key=os.path.getmtime)
                        with open(latest, "r", encoding="utf-8") as f:
                            all_lines = f.readlines()
                        return [line.strip() for line in all_lines[-lines:]]
        except Exception as e:
            if self.logger:
                self.logger.error("Error reading logs: %s", e)
        return ["Não foi possível ler os logs"]

    def get_data_files(self) -> List[Dict[str, Any]]:
        files: List[Dict[str, Any]] = []
        data_dir = self.get_data_directory()
        if not data_dir.exists():
            return files
        for json_file in sorted(
            data_dir.glob("*.json"), key=os.path.getmtime, reverse=True
        ):
            try:
                stat = json_file.stat()
                parts = json_file.stem.split("_", 2)
                date_str = parts[0] if parts else ""
                doctor_name = (
                    parts[2].replace("_", " ").title()
                    if len(parts) > 2
                    else json_file.stem
                )
                files.append(
                    {
                        "name": json_file.name,
                        "doctor": doctor_name,
                        "size": stat.st_size,
                        "size_human": _format_file_size(stat.st_size),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "date_str": (
                            f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                            if len(date_str) >= 8
                            else ""
                        ),
                    }
                )
            except Exception as exc:
                if self.logger:
                    self.logger.debug(
                        "Skipping unreadable data file %s: %s", json_file, exc
                    )
        return files

    def get_export_data(self) -> List[Dict[str, Any]]:
        data_dir = self.get_data_directory()
        all_data: List[Dict[str, Any]] = []
        if not data_dir.exists():
            return all_data
        for json_file in sorted(data_dir.glob("*.json"), key=os.path.getmtime):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    all_data.append(json.load(f))
            except Exception as exc:
                if self.logger:
                    self.logger.debug(
                        "Skipping unreadable data file %s: %s", json_file, exc
                    )
        return all_data

    def get_report_summary(self) -> Dict[str, Any]:
        data_dir = self.get_data_directory()
        total_files = today_files = total_reviews = 0
        doctors: set = set()
        today = datetime.now().strftime("%Y%m%d")
        if data_dir.exists():
            for json_file in data_dir.glob("*.json"):
                total_files += 1
                if json_file.name.startswith(today):
                    today_files += 1
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                    doctor_name = file_data.get("doctor_name", "")
                    if doctor_name:
                        doctors.add(doctor_name)
                    total_reviews += len(file_data.get("reviews", []))
                except Exception as exc:
                    if self.logger:
                        self.logger.debug(
                            "Skipping summary aggregation for %s: %s",
                            json_file,
                            exc,
                        )
        return {
            "total_files": total_files,
            "today_files": today_files,
            "total_reviews": total_reviews,
            "unique_doctors": len(doctors),
        }


def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
