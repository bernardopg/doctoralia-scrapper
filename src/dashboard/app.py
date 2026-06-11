"""DashboardApp — thin Flask wiring; all routes live in blueprints."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

from flask import Flask, jsonify, redirect, request, session, url_for
from flask_cors import CORS

import src.dashboard.api_proxy as api_proxy_bp
import src.dashboard.auth as auth_bp
import src.dashboard.notifications as notifications_bp
import src.dashboard.pages as pages_bp
import src.dashboard.reports as reports_bp
import src.dashboard.user_profile as user_profile_bp
import src.dashboard.workspace as workspace_bp
from src.auth import MIN_PASSWORD_LENGTH, get_dashboard_auth_state
from src.config.settings import AppConfig
from src.dashboard.services import DashboardServices, _clean_optional
from src.logger import setup_logger
from src.performance_monitor import PerformanceMonitor
from src.response_quality_analyzer import ResponseQualityAnalyzer
from src.services.stats import StatsService
from src.services.workspace_service import WorkspaceService


class DashboardApp:
    """Flask-based dashboard for monitoring scraper operations."""

    def __init__(self, config: Any = None, logger: Any = None) -> None:
        if config is None:
            try:
                config = AppConfig.load()
            except Exception:  # nosec B110
                pass

        self.config = config
        self.logger = logger or (setup_logger("dashboard", config) if config else None)

        api_port = 8000
        if self.config and hasattr(self.config, "api"):
            api_port = getattr(self.config.api, "port", api_port)
        self.api_port = api_port

        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent.parent.parent / "templates"),
            static_folder=str(Path(__file__).parent.parent / "static"),
        )
        CORS(self.app)

        data_dir = self._get_data_directory()
        svc = DashboardServices(
            config=config,
            logger=self.logger,
            performance_monitor=PerformanceMonitor(self.logger),
            quality_analyzer=ResponseQualityAnalyzer(),
            stats_service=StatsService(data_dir, self.logger),
            workspace_service=WorkspaceService(data_dir, self.logger),
            api_port=api_port,
        )
        self.svc = svc

        self._configure_session()
        self._register_blueprints()
        self._register_before_request()
        self._register_context_processor()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _get_data_directory(self):
        if self.config and hasattr(self.config, "data_dir"):
            return Path(self.config.data_dir)
        return Path("data")

    def _get_runtime_config(self) -> Any:
        try:
            return AppConfig.load()
        except Exception:
            return self.config

    def _configure_session(self) -> None:
        config = self._get_runtime_config()
        auth_state = get_dashboard_auth_state(config)
        api_public_url = _clean_optional(
            getattr(getattr(config, "integrations", None), "api_public_url", None)
        )
        parsed = urlparse(api_public_url) if api_public_url else None
        use_secure_cookie = bool(parsed and parsed.scheme == "https")

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

    # ------------------------------------------------------------------
    # Blueprint registration
    # ------------------------------------------------------------------

    def _register_blueprints(self) -> None:
        svc = self.svc
        self.app.register_blueprint(auth_bp.create_blueprint(svc))
        self.app.register_blueprint(pages_bp.create_blueprint(svc))
        self.app.register_blueprint(api_proxy_bp.create_blueprint(svc))
        self.app.register_blueprint(workspace_bp.create_blueprint(svc))
        self.app.register_blueprint(reports_bp.create_blueprint(svc))
        self.app.register_blueprint(notifications_bp.create_blueprint(svc))
        self.app.register_blueprint(user_profile_bp.create_blueprint(svc))

    # ------------------------------------------------------------------
    # Cross-cutting concerns
    # ------------------------------------------------------------------

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

    def _register_before_request(self) -> None:
        svc = self.svc
        app = self.app

        @app.before_request
        def protect_dashboard_routes():
            cfg = app.config
            if not svc.is_auth_enabled(cfg):
                return None

            if self._public_route(request.path) and not (
                request.path == "/login" and request.method == "POST"
            ):
                return None

            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                if not svc.is_csrf_valid():
                    if request.path.startswith("/api/"):
                        return jsonify({"error": "CSRF token inválido ou ausente"}), 403
                    return redirect(url_for("auth.login"))

            if request.path == "/login":
                return None

            if svc.is_authenticated(cfg):
                return None

            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401

            next_target = self._safe_next_url(request.full_path.rstrip("?"))
            login_url = url_for("auth.login")
            if next_target and next_target != "/":
                login_url = f"{login_url}?{urlencode({'next': next_target})}"
            return redirect(login_url)

    def _register_context_processor(self) -> None:
        svc = self.svc
        app = self.app

        @app.context_processor
        def inject_template_config():
            user_profile_data = svc.get_user_profile_settings()
            return {
                "api_port": self.api_port,
                "api_docs_url": svc.get_api_docs_url(),
                "dashboard_user_name": user_profile_data.get(
                    "display_name", "Administrador"
                ),
                "dashboard_username": user_profile_data.get("username", "admin"),
                "dashboard_auth_enabled": svc.is_auth_enabled(app.config),
                "dashboard_session_username": session.get("dashboard_username", ""),
                "dashboard_min_password_length": MIN_PASSWORD_LENGTH,
                "csrf_token": svc.csrf_token(),
            }

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(
        self, host: str = "127.0.0.1", port: int = 5000, debug: bool = False
    ) -> None:
        if self.logger:
            self.logger.info("Starting dashboard server on http://%s:%s", host, port)
        self.app.run(host=host, port=port, debug=debug)


def start_dashboard(
    host: str = "127.0.0.1", port: int = 5000, debug: bool = False
):  # pragma: no cover
    config = None
    try:
        from src.config.settings import AppConfig as _Cfg

        config = _Cfg.load()
    except Exception:  # noqa: BLE001
        config = None
    app = DashboardApp(config)
    app.run(host=host, port=port, debug=debug)
