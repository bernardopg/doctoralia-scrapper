"""
Web dashboard for monitoring Doctoralia scraper operations.
Provides real-time monitoring, analytics, and management interface.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS

from config.settings import AppConfig
from src.auth import (
    MIN_PASSWORD_LENGTH,
    get_dashboard_auth_state,
    verify_dashboard_login,
)
from src.logger import setup_logger
from src.multi_site_scraper import ScraperFactory
from src.performance_monitor import PerformanceMonitor
from src.response_quality_analyzer import ResponseQualityAnalyzer
from src.services.stats import StatsService
from src.services.workspace_service import WorkspaceService


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class DashboardApp:
    """
    Flask-based dashboard for monitoring scraper operations.
    """

    def __init__(self, config: Any = None, logger: Any = None) -> None:
        # Load config if not provided
        if config is None:
            try:
                config = AppConfig.load()
            except Exception:
                pass

        self.config = config
        self.logger = logger or (setup_logger("dashboard", config) if config else None)

        # Configure API connection
        api_port = 8000
        if self.config and hasattr(self.config, "api"):
            api_port = getattr(self.config.api, "port", api_port)

        self.api_port = api_port
        self.api_timeout = 5  # seconds

        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent.parent / "templates"),
            static_folder=str(Path(__file__).parent.parent / "static"),
        )
        CORS(self.app)

        self.performance_monitor = PerformanceMonitor(self.logger)
        self.quality_analyzer = ResponseQualityAnalyzer()

        # Shared stats service
        data_dir = self._get_data_directory()
        self.stats_service = StatsService(data_dir, self.logger)
        self.workspace_service = WorkspaceService(data_dir, self.logger)
        self._configure_session()

        self.setup_routes()

    # The run() method is defined near the end of the file with more options (debug flag).
    # We keep a single implementation there to avoid duplication.

    def _get_runtime_config(self) -> Any:
        try:
            return AppConfig.load()
        except Exception:
            return self.config

    def _configure_session(self) -> None:
        auth_state = get_dashboard_auth_state(self._get_runtime_config())
        public_url = self._get_api_docs_url()
        parsed_public_url = urlparse(public_url) if public_url else None
        use_secure_cookie = bool(
            parsed_public_url and parsed_public_url.scheme == "https"
        )

        self.app.secret_key = auth_state.session_secret
        self.app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_SECURE=use_secure_cookie,
            SESSION_REFRESH_EACH_REQUEST=True,
            PERMANENT_SESSION_LIFETIME=timedelta(
                minutes=auth_state.session_ttl_minutes
            ),
        )

    def _get_dashboard_auth_state(self):
        return get_dashboard_auth_state(self._get_runtime_config())

    def _is_auth_enabled(self) -> bool:
        if self.app.config.get("AUTH_FORCE_DISABLED"):
            return False
        if self.app.config.get("AUTH_FORCE_ENABLED"):
            return True
        if self.app.config.get("TESTING"):
            return False
        return bool(self._get_dashboard_auth_state().enabled)

    def _is_authenticated(self) -> bool:
        if not self._is_auth_enabled():
            return True
        return bool(session.get("dashboard_authenticated"))

    def _public_route(self, path: str) -> bool:
        if path.startswith("/static/"):
            return True
        if path in {"/login", "/favicon.ico", "/api/health", "/api/auth/session"}:
            return True
        if path.startswith("/api/auth/login"):
            return True
        return False

    def _safe_next_url(self, candidate: Optional[str]) -> str:
        if not candidate:
            return "/"
        parsed = urlparse(candidate)
        if parsed.scheme or parsed.netloc:
            return "/"
        if not candidate.startswith("/"):
            return "/"
        return candidate

    def _login_session_user(self) -> None:
        auth_state = self._get_dashboard_auth_state()
        session.clear()
        session.permanent = True
        session["dashboard_authenticated"] = True
        session["dashboard_username"] = auth_state.username
        session["dashboard_authenticated_at"] = datetime.now().isoformat()

    def _logout_session_user(self) -> None:
        session.clear()

    def _get_api_base_url(self) -> str:
        config = self._get_runtime_config()
        api_url = _clean_optional(
            getattr(getattr(config, "integrations", None), "api_url", None)
        ) or _clean_optional(os.getenv("API_URL"))
        if api_url:
            return api_url
        api_port = getattr(getattr(config, "api", None), "port", self.api_port)
        return f"http://localhost:{api_port}"

    def _get_api_docs_url(self) -> str:
        config = self._get_runtime_config()
        api_public_url = _clean_optional(
            getattr(getattr(config, "integrations", None), "api_public_url", None)
        ) or _clean_optional(os.getenv("API_PUBLIC_URL"))
        return f"{api_public_url}/docs" if api_public_url else ""

    def _get_api_key(self) -> Optional[str]:
        config = self._get_runtime_config()
        return _clean_optional(
            getattr(getattr(config, "security", None), "api_key", None)
        ) or _clean_optional(os.getenv("API_KEY"))

    def _log_exception(self, message: str, exc: BaseException) -> None:
        if self.logger:
            self.logger.error(
                message,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def _error_payload(
        self,
        public_message: str,
        status_code: int = 500,
        *,
        exc: Optional[BaseException] = None,
        log_message: Optional[str] = None,
    ) -> tuple[Dict[str, str], int]:
        if exc is not None:
            self._log_exception(log_message or public_message, exc)
        return {"error": public_message}, status_code

    def _error_response(
        self,
        public_message: str,
        status_code: int = 500,
        *,
        exc: Optional[BaseException] = None,
        log_message: Optional[str] = None,
    ):
        payload, resolved_status = self._error_payload(
            public_message,
            status_code,
            exc=exc,
            log_message=log_message,
        )
        return jsonify(payload), resolved_status

    def _get_remote_settings(self) -> Optional[Dict[str, Any]]:
        response = self._call_api("/v1/settings")
        if response and response.get("success"):
            return response.get("settings")
        return None

    def _get_user_profile_settings(self) -> Dict[str, Any]:
        settings = self._get_remote_settings()
        if settings and settings.get("user_profile"):
            profile = settings["user_profile"]
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
                        "name": favorite.name,
                        "profile_url": favorite.profile_url,
                        "specialty": favorite.specialty,
                        "notes": favorite.notes,
                    }
                    for favorite in getattr(user_profile, "favorite_profiles", [])
                ],
            }

        return {
            "display_name": "Administrador",
            "username": "admin",
            "favorite_profiles": [],
        }

    def _update_remote_settings(
        self, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        current = self._get_remote_settings()
        if current is None:
            return None
        payload = current.copy()
        payload.update(updates)
        response = self._call_api("/v1/settings", method="PUT", json=payload)
        if response and response.get("success"):
            return response.get("settings")
        return None

    def _call_api(self, endpoint: str, method: str = "GET", **kwargs) -> Optional[Dict]:
        """
        Make HTTP call to the main API.

        Args:
            endpoint: API endpoint (e.g., '/health', '/v1/metrics')
            method: HTTP method (GET, POST, etc.)
            **kwargs: Additional arguments for requests

        Returns:
            JSON response dict or None if API is unavailable
        """
        try:
            api_base_url = self._get_api_base_url()
            url = f"{api_base_url}{endpoint}"
            headers = kwargs.pop("headers", {})
            api_key = self._get_api_key()
            if api_key:
                headers["X-API-Key"] = api_key

            response = requests.request(
                method, url, headers=headers, timeout=self.api_timeout, **kwargs
            )
            if response.status_code in (200, 202):
                result: Dict[Any, Any] = response.json()
                return result
            else:
                if self.logger:
                    self.logger.warning(
                        f"API call failed: {method} {endpoint} -> {response.status_code} - {response.text}"
                    )
                return None
        except requests.exceptions.ConnectionError:
            if self.logger:
                self.logger.debug(
                    f"API not available at {api_base_url} (connection refused)"
                )
            return None
        except requests.exceptions.Timeout:
            if self.logger:
                self.logger.warning(f"API timeout: {method} {endpoint}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error calling API: {e}")
            return None

    def _request_api_with_status(
        self, endpoint: str, method: str = "GET", **kwargs
    ) -> tuple[Optional[Dict[str, Any]], int]:
        """Make an API call preserving the upstream status code and payload."""
        try:
            api_base_url = self._get_api_base_url()
            url = f"{api_base_url}{endpoint}"
            headers = kwargs.pop("headers", {})
            api_key = self._get_api_key()
            if api_key:
                headers["X-API-Key"] = api_key

            response = requests.request(
                method, url, headers=headers, timeout=self.api_timeout, **kwargs
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": response.text or "Resposta inválida da API"}

            return payload, response.status_code
        except requests.exceptions.ConnectionError:
            if self.logger:
                self.logger.debug("API not available for %s %s", method, endpoint)
            return None, 503
        except requests.exceptions.Timeout:
            if self.logger:
                self.logger.warning("API timeout: %s %s", method, endpoint)
            return {"error": "Timeout ao comunicar com a API"}, 504
        except Exception as e:
            return self._error_payload(
                "Erro interno ao comunicar com a API",
                exc=e,
                log_message="Dashboard API proxy request failed",
            )

    def _proxy_api_response(self, endpoint: str, method: str = "GET", **kwargs):
        """Proxy a backend response to the dashboard while preserving status codes."""
        payload, status_code = self._request_api_with_status(
            endpoint, method=method, **kwargs
        )
        if payload is None:
            return jsonify({"error": "API não disponível"}), 503
        return jsonify(payload), status_code

    def _get_api_health(self) -> Dict[str, Any]:
        """Get health status from main API."""
        api_data = self._call_api("/v1/health")
        api_base_url = self._get_api_base_url()
        if api_data:
            return {
                "status": "connected",
                "api_url": api_base_url,
                "api_data": api_data,
            }
        else:
            return {
                "status": "disconnected",
                "api_url": api_base_url,
                "message": "API não está acessível",
            }

    def _get_api_metrics(self) -> Optional[Dict[str, Any]]:
        """Get performance metrics from main API."""
        return self._call_api("/v1/metrics")

    def _get_api_statistics(self) -> Optional[Dict[str, Any]]:
        """Get statistics from main API."""
        return self._call_api("/v1/statistics")

    def setup_routes(self) -> None:
        """Setup Flask routes."""
        self._setup_main_routes()
        self._setup_api_routes()

    def _setup_main_routes(self) -> None:
        """Setup main application routes."""

        @self.app.before_request
        def protect_dashboard_routes():
            if not self._is_auth_enabled():
                return None

            if self._public_route(request.path):
                return None

            if self._is_authenticated():
                return None

            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401

            next_target = self._safe_next_url(request.full_path.rstrip("?"))
            login_url = url_for("login")
            if next_target and next_target != "/":
                login_url = f"{login_url}?{urlencode({'next': next_target})}"
            return redirect(login_url)

        @self.app.context_processor
        def inject_template_config():
            user_profile = self._get_user_profile_settings()
            return {
                "api_port": self.api_port,
                "api_docs_url": self._get_api_docs_url(),
                "dashboard_user_name": user_profile.get(
                    "display_name", "Administrador"
                ),
                "dashboard_username": user_profile.get("username", "admin"),
                "dashboard_auth_enabled": self._is_auth_enabled(),
                "dashboard_session_username": session.get("dashboard_username", ""),
                "dashboard_min_password_length": MIN_PASSWORD_LENGTH,
            }

        @self.app.route("/login", methods=["GET", "POST"])
        def login():
            """Dashboard login page."""
            auth_state = self._get_dashboard_auth_state()
            if not auth_state.enabled and request.method == "GET":
                return redirect(url_for("index"))

            if self._is_authenticated():
                return redirect(self._safe_next_url(request.args.get("next")))

            error_message = None
            next_target = self._safe_next_url(
                request.values.get("next") or request.args.get("next")
            )

            if request.method == "POST":
                username = (request.form.get("username") or "").strip()
                password = request.form.get("password") or ""
                if verify_dashboard_login(
                    self._get_runtime_config(), username, password
                ):
                    self._login_session_user()
                    return redirect(next_target or url_for("index"))
                error_message = "Credenciais inválidas."

            return render_template(
                "login.html",
                login_error=error_message,
                next_target=next_target,
                login_username_hint=auth_state.username,
                bootstrap_password_enabled=auth_state.bootstrap_password_enabled,
            )

        @self.app.route("/logout", methods=["POST"])
        def logout():
            """End dashboard session."""
            self._logout_session_user()
            return redirect(url_for("login"))

        @self.app.route("/")
        def index():
            """Main dashboard page."""
            return render_template("dashboard.html")

        @self.app.route("/settings")
        def settings():
            """Settings page."""
            return render_template("settings.html")

        @self.app.route("/profiles")
        def profiles():
            """Profile analytics page."""
            return render_template("profiles.html")

        @self.app.route("/responses")
        def responses():
            """Pending response generation workspace."""
            return render_template("responses.html")

        @self.app.route("/me")
        def me():
            """User/operator profile page."""
            return render_template("user_profile.html")

        @self.app.route("/history")
        def history():
            """History page."""
            return render_template("history.html")

        @self.app.route("/reports")
        def reports():
            """Reports page."""
            return render_template("reports.html")

        @self.app.route("/notifications/telegram/schedule")
        def telegram_notification_schedule():
            """Telegram notification scheduling page."""
            return render_template("telegram_schedule.html")

        @self.app.route("/health-check")
        def health_check_page():
            """Health check visual page."""
            return render_template("health.html")

        @self.app.route("/api/health")
        def health_check():
            """Health check endpoint with API connection status."""
            api_health = self._get_api_health()
            return jsonify(
                {
                    "dashboard": {
                        "status": "healthy",
                        "timestamp": datetime.now().isoformat(),
                        "version": "1.2.0-rc.1",
                    },
                    "api": api_health,
                }
            )

    def _setup_api_routes(self) -> None:
        """Setup API routes."""

        @self.app.route("/api/auth/login", methods=["POST"])
        def login_auth_session():
            """Authenticate a dashboard user and start a signed session."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                payload, status_code = self._request_api_with_status(
                    "/v1/auth/login",
                    method="POST",
                    json={
                        "username": (data.get("username") or "").strip(),
                        "password": data.get("password") or "",
                    },
                )

                if payload is None:
                    return jsonify({"error": "API não disponível"}), 503

                if status_code == 200 and payload.get("success"):
                    self._login_session_user()

                response_payload = dict(payload)
                response_payload["authenticated"] = self._is_authenticated()
                response_payload["username"] = session.get("dashboard_username")
                return jsonify(response_payload), status_code
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/auth/session")
        def get_auth_session():
            """Expose dashboard session state for authenticated pages."""
            auth_status = self._call_api("/v1/auth/status") or {}
            return jsonify(
                {
                    "authenticated": self._is_authenticated(),
                    "username": session.get("dashboard_username"),
                    "auth_enabled": self._is_auth_enabled(),
                    "password_configured": auth_status.get(
                        "password_configured", False
                    ),
                    "bootstrap_password_enabled": auth_status.get(
                        "bootstrap_password_enabled", False
                    ),
                    "session_ttl_minutes": auth_status.get("session_ttl_minutes", 480),
                }
            )

        @self.app.route("/api/auth/logout", methods=["POST"])
        def logout_auth_session():
            """End the dashboard session via JSON API."""
            self._logout_session_user()
            return jsonify({"success": True, "message": "Logout successful"})

        @self.app.route("/api/auth/change-password", methods=["POST"])
        def change_auth_password():
            """Proxy dashboard password rotation to the API."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                payload, status_code = self._request_api_with_status(
                    "/v1/auth/change-password",
                    method="POST",
                    json=data,
                )
                if payload is None:
                    return jsonify({"error": "API não disponível"}), 503

                if isinstance(payload.get("error"), dict):
                    api_error = payload.get("error") or {}
                    message = str(api_error.get("message") or "").strip()
                    if message:
                        payload = dict(payload)
                        payload["error"] = message

                return jsonify(payload), status_code
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/stats")
        def get_stats():
            """Get scraper statistics from API or local files."""
            try:
                # Try to get stats from main API first
                api_stats = self._get_api_statistics()
                if api_stats:
                    return jsonify({"source": "api", "data": api_stats})

                # Fallback to local files
                stats = self._get_scraper_stats()
                return jsonify({"source": "local", "data": stats})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/performance")
        def get_performance():
            """Get performance metrics from API or local monitor."""
            try:
                # Try to get metrics from main API first
                api_metrics = self._get_api_metrics()
                if api_metrics:
                    return jsonify(
                        {
                            "source": "api",
                            "data": api_metrics,
                        }
                    )

                # Fallback to local performance monitor
                if self.performance_monitor:
                    summary = self.performance_monitor.get_summary()
                    return jsonify({"source": "local", "data": summary})

                return jsonify(
                    {
                        "source": "none",
                        "message": "No performance data available. Start the API with 'make api'",
                    }
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/trends")
        def get_trends():
            """Get trend data for charts."""
            try:
                trends: Dict[str, Any] = self._get_trend_data()
                return jsonify({"source": "local", "data": trends})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/recent-activity")
        def get_recent_activity():
            """Get recent scraping activity."""
            try:
                activities = self._get_recent_activities()
                return jsonify(activities)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/quality-analysis", methods=["POST"])
        def analyze_quality():
            """Analyze response quality."""
            return self._handle_quality_analysis()

        @self.app.route("/api/platforms")
        def get_platforms():
            """Get supported platforms."""
            try:
                if hasattr(ScraperFactory, "get_supported_platforms"):
                    platforms = ScraperFactory.get_supported_platforms()
                    return jsonify({"platforms": platforms})
                return jsonify({"platforms": ["doctoralia"]})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/logs")
        def get_logs():
            """Get recent log entries."""
            try:
                lines = request.args.get("lines", default=50, type=int)
                logs = self._get_recent_logs(lines)
                return jsonify({"logs": logs})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        # Proxy endpoints to avoid CORS issues
        @self.app.route("/api/scrape", methods=["POST"])
        def proxy_scrape():
            """Proxy scraping request to main API."""
            try:
                data = request.get_json(force=True, silent=True)
                if not data:
                    return (
                        jsonify({"error": "Corpo da requisição inválido ou vazio"}),
                        400,
                    )

                # Backward compatibility: accept legacy "url" field.
                doctor_url = data.get("doctor_url") or data.get("url")
                if not doctor_url:
                    return (
                        jsonify(
                            {"error": "Campo 'doctor_url' (ou 'url') é obrigatório"}
                        ),
                        400,
                    )

                payload = {
                    "doctor_url": doctor_url,
                    "include_analysis": data.get("include_analysis", True),
                    "include_generation": data.get("include_generation", False),
                    "response_template_id": data.get("response_template_id"),
                    "language": data.get("language", "pt"),
                    "meta": data.get("meta"),
                    "mode": "async",
                    "callback_url": data.get("callback_url"),
                    "idempotency_key": data.get("idempotency_key"),
                }
                result = self._call_api("/v1/jobs", method="POST", json=payload)
                if result is not None:
                    return jsonify(result)
                return (
                    jsonify(
                        {
                            "error": "API não disponível. Execute 'make api' para iniciar."
                        }
                    ),
                    503,
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/tasks/<task_id>")
        def proxy_task_status(task_id):
            """Proxy task status request to main API."""
            try:
                result = self._call_api(f"/v1/jobs/{task_id}")
                if result is not None:
                    return jsonify(result)
                return (
                    jsonify({"error": "API não disponível ou task não encontrada"}),
                    503,
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/tasks")
        def proxy_list_tasks():
            """Proxy task list request to main API."""
            try:
                status = request.args.get("status")
                endpoint = "/v1/jobs"
                if status:
                    endpoint += f"?status={status}"

                result = self._call_api(endpoint)
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/settings")
        def proxy_get_settings():
            """Proxy GET settings request to main API."""
            try:
                result = self._call_api("/v1/settings")
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/settings", methods=["PUT"])
        def proxy_update_settings():
            """Proxy PUT settings request to main API."""
            try:
                data = request.get_json(force=True, silent=True)
                result = self._call_api("/v1/settings", method="PUT", json=data)
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/settings/validate", methods=["POST"])
        def proxy_validate_settings():
            """Proxy POST settings validate request to main API."""
            try:
                data = request.get_json(force=True, silent=True)
                result = self._call_api(
                    "/v1/settings/validate", method="POST", json=data
                )
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/generate/response", methods=["POST"])
        def proxy_generate_response():
            """Proxy single response generation to the main API."""
            try:
                data = request.get_json(force=True, silent=True)
                result = self._call_api(
                    "/v1/generate/response", method="POST", json=data
                )
                if result is not None:
                    return jsonify(result)
                return jsonify({"error": "API não disponível"}), 503
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/notifications/telegram/schedules")
        def get_telegram_notification_schedules():
            """List Telegram notification schedules."""
            try:
                return self._proxy_api_response("/v1/notifications/telegram/schedules")
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/notifications/telegram/schedules", methods=["POST"])
        def create_telegram_notification_schedule():
            """Create a Telegram notification schedule."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                return self._proxy_api_response(
                    "/v1/notifications/telegram/schedules",
                    method="POST",
                    json=data,
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route(
            "/api/notifications/telegram/schedules/<schedule_id>", methods=["PUT"]
        )
        def update_telegram_notification_schedule(schedule_id):
            """Update a Telegram notification schedule."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                return self._proxy_api_response(
                    f"/v1/notifications/telegram/schedules/{schedule_id}",
                    method="PUT",
                    json=data,
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route(
            "/api/notifications/telegram/schedules/<schedule_id>", methods=["DELETE"]
        )
        def delete_telegram_notification_schedule(schedule_id):
            """Delete a Telegram notification schedule."""
            try:
                return self._proxy_api_response(
                    f"/v1/notifications/telegram/schedules/{schedule_id}",
                    method="DELETE",
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route(
            "/api/notifications/telegram/schedules/<schedule_id>/run",
            methods=["POST"],
        )
        def run_telegram_notification_schedule(schedule_id):
            """Run a Telegram notification schedule immediately."""
            try:
                return self._proxy_api_response(
                    f"/v1/notifications/telegram/schedules/{schedule_id}/run?wait=false",
                    method="POST",
                    json={},
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/notifications/telegram/history")
        def get_telegram_notification_history():
            """List Telegram notification history."""
            try:
                limit = request.args.get("limit", default=50, type=int)
                endpoint = f"/v1/notifications/telegram/history?limit={limit}"
                return self._proxy_api_response(endpoint)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/notifications/telegram/test", methods=["POST"])
        def send_test_telegram_notification():
            """Send a manual Telegram test notification."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                return self._proxy_api_response(
                    "/v1/notifications/telegram/test",
                    method="POST",
                    json=data,
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/user-profile")
        def get_user_profile():
            """Return user profile settings extracted from the central settings API."""
            try:
                return jsonify(self._get_user_profile_settings())
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/user-profile", methods=["PUT"])
        def update_user_profile():
            """Persist user profile via the central settings endpoint."""
            try:
                payload = request.get_json(force=True, silent=True) or {}
                updated_settings = self._update_remote_settings(
                    {"user_profile": payload}
                )
                if updated_settings is None:
                    return jsonify({"error": "API não disponível"}), 503
                return jsonify(updated_settings.get("user_profile", payload))
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/user-profile/favorites/toggle", methods=["POST"])
        def toggle_favorite_profile():
            """Toggle a profile inside the saved favorites list."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                profile_url = _clean_optional(data.get("profile_url"))
                profile_name = _clean_optional(data.get("name")) or "Perfil favorito"
                if not profile_url:
                    return jsonify({"error": "profile_url é obrigatório"}), 400

                user_profile = self._get_user_profile_settings()
                favorites = user_profile.get("favorite_profiles", [])
                normalized_url = profile_url.lower()
                existing = next(
                    (
                        favorite
                        for favorite in favorites
                        if str(favorite.get("profile_url", "")).strip().lower()
                        == normalized_url
                    ),
                    None,
                )

                if existing:
                    favorites = [
                        favorite
                        for favorite in favorites
                        if str(favorite.get("profile_url", "")).strip().lower()
                        != normalized_url
                    ]
                else:
                    favorites.append(
                        {
                            "name": profile_name,
                            "profile_url": profile_url,
                            "specialty": _clean_optional(data.get("specialty")),
                            "notes": _clean_optional(data.get("notes")),
                        }
                    )

                user_profile["favorite_profiles"] = favorites
                updated_settings = self._update_remote_settings(
                    {"user_profile": user_profile}
                )
                if updated_settings is None:
                    return jsonify({"error": "API não disponível"}), 503
                return jsonify(
                    {
                        "success": True,
                        "favorite": existing is None,
                        "user_profile": updated_settings.get(
                            "user_profile", user_profile
                        ),
                    }
                )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/overview")
        def get_workspace_overview():
            """Get filterable dashboard overview metrics."""
            try:
                user_profile = self._get_user_profile_settings()
                overview = self.workspace_service.get_overview(
                    profile_id=request.args.get("profile_id"),
                    date_from=request.args.get("date_from"),
                    date_to=request.args.get("date_to"),
                    favorite_profiles=user_profile.get("favorite_profiles", []),
                )
                overview["user_profile"] = user_profile
                return jsonify(overview)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/profiles")
        def get_workspace_profiles():
            """Get aggregated profile list with favorite state and metrics."""
            try:
                user_profile = self._get_user_profile_settings()
                profiles = self.workspace_service.list_profiles(
                    date_from=request.args.get("date_from"),
                    date_to=request.args.get("date_to"),
                    favorite_profiles=user_profile.get("favorite_profiles", []),
                )
                return jsonify({"profiles": profiles})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/profile")
        def get_workspace_profile_detail():
            """Get a specific profile detail payload."""
            try:
                profile_id = request.args.get("profile_id")
                if not profile_id:
                    return jsonify({"error": "profile_id é obrigatório"}), 400
                user_profile = self._get_user_profile_settings()
                detail = self.workspace_service.get_profile_detail(
                    profile_id=profile_id,
                    date_from=request.args.get("date_from"),
                    date_to=request.args.get("date_to"),
                    favorite_profiles=user_profile.get("favorite_profiles", []),
                )
                if detail is None:
                    return jsonify({"error": "Perfil não encontrado"}), 404
                return jsonify(detail)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/responses")
        def get_workspace_pending_responses():
            """Get pending responses from the latest snapshot of each profile."""
            try:
                user_profile = self._get_user_profile_settings()
                payload = self.workspace_service.list_pending_responses(
                    profile_id=request.args.get("profile_id"),
                    date_from=request.args.get("date_from"),
                    date_to=request.args.get("date_to"),
                    favorite_profiles=user_profile.get("favorite_profiles", []),
                    favorites_only=request.args.get("favorites_only") == "1",
                    search=request.args.get("q"),
                )
                return jsonify(payload)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/history")
        def get_workspace_history():
            """Get snapshot history with latest/outdated markers and filters."""
            try:
                payload = self.workspace_service.get_history(
                    profile_id=request.args.get("profile_id"),
                    date_from=request.args.get("date_from"),
                    date_to=request.args.get("date_to"),
                    status=request.args.get("status"),
                    search=request.args.get("q"),
                )
                return jsonify(payload)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/history/delete", methods=["POST"])
        def delete_workspace_history_snapshot():
            """Delete a single stored snapshot by filename."""
            try:
                payload = request.get_json(force=True, silent=True) or {}
                filename = _clean_optional(payload.get("filename"))
                if not filename:
                    return jsonify({"error": "filename é obrigatório"}), 400
                deleted = self.workspace_service.delete_snapshot(filename)
                if deleted is None:
                    return jsonify({"error": "Snapshot não encontrado"}), 404
                return jsonify({"success": True, "deleted": deleted})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/history/prune", methods=["POST"])
        def prune_workspace_history():
            """Delete outdated snapshots, preserving the newest snapshot per profile."""
            try:
                payload = request.get_json(force=True, silent=True) or {}
                result = self.workspace_service.prune_outdated_snapshots(
                    profile_id=_clean_optional(payload.get("profile_id")),
                    date_from=_clean_optional(payload.get("date_from")),
                    date_to=_clean_optional(payload.get("date_to")),
                )
                return jsonify({"success": True, "result": result})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/reports")
        def get_workspace_reports():
            """Get richer report payload for the reports page."""
            try:
                user_profile = self._get_user_profile_settings()
                payload = self.workspace_service.get_reports(
                    profile_id=request.args.get("profile_id"),
                    date_from=request.args.get("date_from"),
                    date_to=request.args.get("date_to"),
                    favorite_profiles=user_profile.get("favorite_profiles", []),
                )
                return jsonify(payload)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/workspace/responses/save", methods=["POST"])
        def save_workspace_generated_response():
            """Persist a generated suggestion into the latest snapshot file."""
            try:
                data = request.get_json(force=True, silent=True) or {}
                profile_id = _clean_optional(data.get("profile_id"))
                review_id = str(data.get("review_id") or "").strip()
                generated_response = _clean_optional(data.get("generated_response"))
                if not profile_id or not review_id or not generated_response:
                    return (
                        jsonify(
                            {
                                "error": "profile_id, review_id e generated_response são obrigatórios"
                            }
                        ),
                        400,
                    )

                saved = self.workspace_service.save_generated_response(
                    profile_id=profile_id,
                    review_id=review_id,
                    generated_response=generated_response,
                )
                if saved is None:
                    return jsonify({"error": "Não foi possível salvar a sugestão"}), 404
                return jsonify({"success": True, "saved": saved})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/ready")
        def proxy_ready():
            """Proxy readiness check to main API (accepts 200 and 503)."""
            try:
                url = f"{self._get_api_base_url()}/v1/ready"
                headers = {}
                api_key = self._get_api_key()
                if api_key:
                    headers["X-API-Key"] = api_key
                resp = requests.get(url, headers=headers, timeout=self.api_timeout)
                if resp.status_code in (200, 503):
                    return jsonify(resp.json()), resp.status_code
                return jsonify({"error": "API não disponível"}), 503
            except requests.exceptions.ConnectionError:
                return jsonify({"error": "API não está acessível"}), 503
            except Exception as e:
                return self._error_response(
                    "Falha ao consultar a API",
                    status_code=503,
                    exc=e,
                )

        @self.app.route("/api/reports/files")
        def get_report_files():
            """List available data files for reports."""
            try:
                files = self._get_data_files()
                return jsonify({"files": files})
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/reports/export/<format_type>")
        def export_data(format_type):
            """Export scraped data in specified format."""
            try:
                from flask import Response

                data = self._get_export_data()
                if format_type == "json":
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    return Response(
                        content,
                        mimetype="application/json",
                        headers={
                            "Content-Disposition": "attachment; filename=doctoralia_export.json"
                        },
                    )
                elif format_type == "csv":
                    content = self._convert_to_csv(data)
                    return Response(
                        content,
                        mimetype="text/csv; charset=utf-8",
                        headers={
                            "Content-Disposition": "attachment; filename=doctoralia_export.csv"
                        },
                    )
                else:
                    return (
                        jsonify({"error": f"Formato '{format_type}' não suportado"}),
                        400,
                    )
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

        @self.app.route("/api/reports/summary")
        def get_report_summary():
            """Get report summary statistics."""
            try:
                summary = self._get_report_summary()
                return jsonify(summary)
            except Exception as e:
                return self._error_response("Erro interno do dashboard", exc=e)

    def _handle_quality_analysis(self):
        """Handle quality analysis request."""
        try:
            data = request.get_json(force=True, silent=True)
            if data is None:
                return jsonify({"error": "Invalid JSON in request body"}), 400
            response_text = data.get("response", "")
            original_review = data.get("original_review", "")

            if not response_text:
                return jsonify({"error": "Response text is required"}), 400

            if self.quality_analyzer:
                analysis = self.quality_analyzer.analyze_response(
                    response_text, original_review
                )
                return jsonify(
                    {
                        "score": analysis.score.to_dict(),
                        "strengths": analysis.strengths,
                        "weaknesses": analysis.weaknesses,
                        "suggestions": analysis.suggestions,
                        "keywords": analysis.keywords,
                        "sentiment": analysis.sentiment,
                        "readability_score": analysis.readability_score,
                    }
                )
            else:
                return jsonify({"error": "Quality analyzer not available"}), 503

        except Exception as e:
            return self._error_response(
                "Falha ao analisar a qualidade da resposta",
                exc=e,
            )

    def _get_trend_data(self) -> Dict[str, Any]:
        """Get trend data (reviews over time)."""
        try:
            return self.stats_service.get_trend_data()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting trend data: {e}")
            return {"dates": [], "reviews": [], "scrapes": []}

    def _get_scraper_stats(self) -> Dict[str, Any]:
        """Get comprehensive scraper statistics."""
        try:
            return self.stats_service.get_scraper_stats()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting scraper stats: {e}")
            return {
                "total_scraped_doctors": 0,
                "total_reviews": 0,
                "average_rating": 0.0,
                "last_scrape_time": None,
                "data_files": [],
                "platform_stats": {},
            }

    def _get_recent_activities(self) -> List[Dict[str, Any]]:
        """Get recent scraping activities."""
        activities = []

        try:
            data_dir = self._get_data_directory()
            if data_dir and data_dir.exists():
                json_files = self._get_recent_json_files(data_dir)
                activities = self._process_activity_files(json_files)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting recent activities: {e}")

        return activities

    def _get_data_directory(self) -> Path:
        """Get the data directory path."""
        if self.config and hasattr(self.config, "data_dir"):
            return Path(self.config.data_dir)
        return Path("data")

    def _get_recent_json_files(self, data_dir: Path) -> List[Path]:
        """Get the most recent JSON files."""
        json_files = sorted(data_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
        return json_files[:10]  # Last 10 activities

    def _process_activity_files(self, json_files: List[Path]) -> List[Dict[str, Any]]:
        """Process activity files and extract data."""
        activities = []
        for json_file in json_files:
            activity_data = self._extract_activity_data(json_file)
            if activity_data:
                activities.append(activity_data)
        return activities

    def _extract_activity_data(self, json_file: Path) -> Optional[Dict[str, Any]]:
        """Extract activity data from a single JSON file."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Support both flat format (scraper.save_data) and nested format
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
                self.logger.warning(f"Error reading activity {json_file}: {e}")
            return None

    def _get_recent_logs(self, lines: int = 50) -> List[str]:
        """Get recent log entries."""
        logs = []

        try:
            if self.config and hasattr(self.config, "logs_dir"):
                logs_dir = Path(self.config.logs_dir)
                if logs_dir.exists():
                    # Find the most recent log file
                    log_files = list(logs_dir.glob("*.log"))
                    if log_files:
                        latest_log = max(log_files, key=os.path.getmtime)

                        with open(latest_log, "r", encoding="utf-8") as f:
                            all_lines = f.readlines()
                            logs = [line.strip() for line in all_lines[-lines:]]

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading logs: {e}")
            logs = ["Não foi possível ler os logs"]

        return logs

    def _get_data_files(self) -> List[Dict[str, Any]]:
        """List available data files with metadata."""
        files: List[Dict[str, Any]] = []
        data_dir = self._get_data_directory()

        if not data_dir.exists():
            return files

        for json_file in sorted(
            data_dir.glob("*.json"), key=os.path.getmtime, reverse=True
        ):
            try:
                stat = json_file.stat()
                # Extract doctor name and date from filename
                parts = json_file.stem.split("_", 2)
                date_str = parts[0] if len(parts) > 0 else ""
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
                        "size_human": self._format_file_size(stat.st_size),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "date_str": (
                            f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                            if len(date_str) >= 8
                            else ""
                        ),
                    }
                )
            except Exception:
                continue

        return files

    def _get_export_data(self) -> List[Dict[str, Any]]:
        """Get all scraped data for export."""
        data_dir = self._get_data_directory()
        all_data: List[Dict[str, Any]] = []

        if not data_dir.exists():
            return all_data

        for json_file in sorted(data_dir.glob("*.json"), key=os.path.getmtime):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    all_data.append(file_data)
            except Exception:
                continue

        return all_data

    def _convert_to_csv(self, data: List[Dict[str, Any]]) -> str:
        """Convert scraped data to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "doctor_name",
                "extraction_date",
                "review_id",
                "author",
                "rating",
                "date",
                "comment",
                "generated_response",
            ]
        )

        for entry in data:
            doctor_name = entry.get("doctor_name", "")
            extraction_ts = entry.get("extraction_timestamp", "")
            reviews = entry.get("reviews", [])

            for review in reviews:
                writer.writerow(
                    [
                        doctor_name,
                        extraction_ts,
                        review.get("id", ""),
                        review.get("author", ""),
                        review.get("rating", ""),
                        review.get("date", ""),
                        review.get("comment", ""),
                        review.get("generated_response", ""),
                    ]
                )

        return output.getvalue()

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _get_report_summary(self) -> Dict[str, Any]:
        """Get summary statistics for reports page."""
        data_dir = self._get_data_directory()
        total_files = 0
        today_files = 0
        total_reviews = 0
        doctors = set()
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
                except Exception:
                    continue

        return {
            "total_files": total_files,
            "today_files": today_files,
            "total_reviews": total_reviews,
            "unique_doctors": len(doctors),
        }

    def run(
        self, host: str = "127.0.0.1", port: int = 5000, debug: bool = False
    ) -> None:
        """Run the Flask dashboard server."""
        if self.logger:
            self.logger.info(f"Starting dashboard server on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


def start_dashboard(
    host: str = "127.0.0.1", port: int = 5000, debug: bool = False
):  # pragma: no cover - thin wrapper
    """Convenience wrapper so the CLI can start the dashboard with a single import."""
    config = None
    try:
        from config.settings import AppConfig as _Cfg  # local import

        config = _Cfg.load()
    except Exception:  # noqa: BLE001
        config = None
    app = DashboardApp(config)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    dashboard = DashboardApp()
    dashboard.run(debug=False)
