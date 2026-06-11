"""Auth blueprint — /login, /logout, /api/auth/*"""

from __future__ import annotations

from urllib.parse import urlparse

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from src.auth import verify_dashboard_login
from src.dashboard.services import DashboardServices


def _validate_redirect_target(candidate: str | None) -> str | None:
    """Return the target only if it is a safe same-site relative path, else None.

    Hardened against open-redirect bypasses:
    - rejects absolute URLs (scheme/netloc)
    - rejects protocol-relative (``//host``) and backslash tricks (``/\\host``)
      that browsers normalize to an external host
    - rejects control characters / whitespace that can smuggle a new target
    - requires a path rooted at a single ``/``
    """
    if not candidate:
        return None
    # Control chars / whitespace (incl. NUL, CR, LF, tab) can be used to smuggle
    # a different effective target; reject outright.
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in candidate):
        return None
    if candidate.strip() != candidate:
        return None
    # Backslashes are normalized to "/" by browsers -> "/\evil.com" becomes
    # "//evil.com". Treat them as forbidden.
    if "\\" in candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    # Must be a path rooted at exactly one slash. "//host" is protocol-relative.
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    return candidate


def create_blueprint(svc: DashboardServices) -> Blueprint:
    bp = Blueprint("auth", __name__)

    def _app_cfg() -> dict:
        return current_app.config  # type: ignore[return-value]

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        auth_state = svc.get_dashboard_auth_state()
        if not auth_state.enabled and request.method == "GET":
            return redirect(url_for("pages.index"))

        if svc.is_authenticated(_app_cfg()):
            next_raw = request.args.get("next")
            safe_next = _validate_redirect_target(next_raw)
            if safe_next:
                return redirect(safe_next)
            return redirect(url_for("pages.index"))

        error_message = None
        next_raw = request.values.get("next") or request.args.get("next")
        next_target = _validate_redirect_target(next_raw)

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            if verify_dashboard_login(svc._get_runtime_config(), username, password):
                svc.login_session_user()
                if next_target:
                    return redirect(next_target)
                return redirect(url_for("pages.index"))
            error_message = "Credenciais inválidas."

        return render_template(
            "login.html",
            login_error=error_message,
            next_target=next_target or "/",
            login_username_hint=auth_state.username,
            bootstrap_password_enabled=auth_state.bootstrap_password_enabled,
        )

    @bp.route("/logout", methods=["POST"])
    def logout():
        svc.logout_session_user()
        return redirect(url_for("pages.index"))

    # ------------------------------------------------------------------
    # JSON auth API
    # ------------------------------------------------------------------

    @bp.route("/api/auth/login", methods=["POST"])
    def login_api():
        try:
            data = request.get_json(force=True, silent=True) or {}
            payload, status_code = svc.request_api_with_status(
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
                svc.login_session_user()

            response_payload = dict(payload)
            response_payload["authenticated"] = svc.is_authenticated(_app_cfg())
            response_payload["username"] = session.get("dashboard_username")
            return jsonify(response_payload), status_code
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/auth/session")
    def get_session():
        auth_status = svc.call_api("/v1/auth/status") or {}
        cfg = _app_cfg()
        return jsonify(
            {
                "authenticated": svc.is_authenticated(cfg),
                "username": session.get("dashboard_username"),
                "auth_enabled": svc.is_auth_enabled(cfg),
                "password_configured": auth_status.get("password_configured", False),
                "bootstrap_password_enabled": auth_status.get(
                    "bootstrap_password_enabled", False
                ),
                "session_ttl_minutes": auth_status.get("session_ttl_minutes", 480),
            }
        )

    @bp.route("/api/auth/logout", methods=["POST"])
    def logout_api():
        svc.logout_session_user()
        return jsonify({"success": True, "message": "Logout successful"})

    @bp.route("/api/auth/change-password", methods=["POST"])
    def change_password():
        try:
            data = request.get_json(force=True, silent=True) or {}
            payload, status_code = svc.request_api_with_status(
                "/v1/auth/change-password", method="POST", json=data
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
            return svc.error_response("Erro interno do dashboard", exc=e)

    return bp
