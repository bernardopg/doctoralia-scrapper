"""
Shared authentication helpers for the dashboard and API.
"""

from __future__ import annotations

import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Any, Optional

from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_SESSION_TTL_MINUTES = 8 * 60
MIN_PASSWORD_LENGTH = 8


@dataclass
class DashboardAuthState:
    enabled: bool
    username: str
    password_configured: bool
    bootstrap_password_enabled: bool
    session_ttl_minutes: int
    session_secret: str


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _get_attr(config: Any, path: str, default: Any = None) -> Any:
    current = config
    for part in path.split("."):
        if current is None or not hasattr(current, part):
            return default
        current = getattr(current, part)
    return current


def hash_dashboard_password(password: str) -> str:
    return generate_password_hash(password.strip())


def validate_new_password(password: str) -> Optional[str]:
    cleaned = (password or "").strip()
    if len(cleaned) < MIN_PASSWORD_LENGTH:
        return (
            f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    return None


def get_dashboard_auth_state(config: Any) -> DashboardAuthState:
    username = _clean_optional(_get_attr(config, "user_profile.username")) or "admin"
    explicit_secret = (
        _clean_optional(_get_attr(config, "security.dashboard_session_secret"))
        or _clean_optional(os.getenv("DASHBOARD_SESSION_SECRET"))
    )
    fallback_secret = (
        _clean_optional(_get_attr(config, "security.webhook_signing_secret"))
        or _clean_optional(_get_attr(config, "security.api_key"))
    )
    session_secret = explicit_secret or fallback_secret or secrets.token_urlsafe(32)

    password_hash = _clean_optional(_get_attr(config, "security.dashboard_password_hash"))
    bootstrap_password = _clean_optional(_get_attr(config, "security.api_key"))
    ttl_raw = _get_attr(
        config,
        "security.dashboard_session_ttl_minutes",
        DEFAULT_SESSION_TTL_MINUTES,
    )
    try:
        session_ttl_minutes = max(int(ttl_raw), 5)
    except (TypeError, ValueError):
        session_ttl_minutes = DEFAULT_SESSION_TTL_MINUTES

    enabled_raw = _get_attr(config, "security.dashboard_auth_enabled", True)
    enabled = bool(enabled_raw and (password_hash or bootstrap_password))

    return DashboardAuthState(
        enabled=enabled,
        username=username,
        password_configured=bool(password_hash or bootstrap_password),
        bootstrap_password_enabled=bool(bootstrap_password and not password_hash),
        session_ttl_minutes=session_ttl_minutes,
        session_secret=session_secret,
    )


def verify_dashboard_password(config: Any, password: str) -> bool:
    candidate = (password or "").strip()
    if not candidate:
        return False

    password_hash = _clean_optional(_get_attr(config, "security.dashboard_password_hash"))
    if password_hash:
        try:
            return check_password_hash(password_hash, candidate)
        except ValueError:
            return False

    bootstrap_password = _clean_optional(_get_attr(config, "security.api_key"))
    if bootstrap_password:
        return hmac.compare_digest(candidate, bootstrap_password)

    return False


def verify_dashboard_login(config: Any, identifier: str, password: str) -> bool:
    normalized_identifier = (identifier or "").strip().lower()
    username = (
        _clean_optional(_get_attr(config, "user_profile.username")) or "admin"
    ).lower()

    if normalized_identifier != username:
        return False

    return verify_dashboard_password(config, password)
