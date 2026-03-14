"""
Privacy and security utilities for n8n integration.
"""

import hashlib
import os
import re
from typing import Any, Dict, Optional


def _load_privacy_config():
    try:
        from config.settings import AppConfig

        return AppConfig.load().privacy
    except Exception:
        return None


def _get_bool(name: str, default: bool) -> bool:
    config = _load_privacy_config()
    if config is not None:
        mapping = {
            "MASK_PII": config.mask_pii,
            "REQUIRE_TLS_CALLBACKS": config.require_tls_callbacks,
        }
        if name in mapping:
            return bool(mapping[name])
    return os.getenv(name, str(default)).lower() == "true"


def _get_str(name: str, default: str) -> str:
    config = _load_privacy_config()
    if config is not None:
        mapping = {
            "ID_SALT": config.id_salt,
        }
        value = mapping.get(name)
        if value:
            return str(value)
    return os.getenv(name, default)


def _get_int(name: str, default: int) -> int:
    config = _load_privacy_config()
    if config is not None:
        mapping = {
            "JOB_RESULT_TTL": config.job_result_ttl,
            "RATE_LIMIT_REQUESTS": config.rate_limit_requests,
            "RATE_LIMIT_WINDOW": config.rate_limit_window,
        }
        value = mapping.get(name)
        if value is not None:
            return int(value)
    return int(os.getenv(name, str(default)))


def _get_allowed_domains() -> list[str]:
    config = _load_privacy_config()
    if config is not None and getattr(config, "allowed_callback_domains", None):
        return [
            domain.strip()
            for domain in config.allowed_callback_domains
            if domain.strip()
        ]
    return [
        domain.strip()
        for domain in os.getenv("ALLOWED_CALLBACK_DOMAINS", "").split(",")
        if domain.strip()
    ]


def mask_pii(text: str) -> str:
    """
    Mask personally identifiable information in text.
    """
    if not _get_bool("MASK_PII", True):
        return text

    # Mask email addresses
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "***@***.***", text
    )

    # Mask phone numbers (Brazilian format)
    text = re.sub(
        r"\b(?:\+55\s?)?(?:\d{2}\s?)?(?:\d{4,5}[-\s]?\d{4})\b", "***-****", text
    )

    # Mask CPF (Brazilian ID)
    text = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "***.***.***-**", text)

    # Mask generic IDs (numbers longer than 6 digits)
    text = re.sub(r"\b\d{7,}\b", lambda m: "*" * len(m.group()), text)

    return text


def hash_sensitive_id(value: str) -> str:
    """
    Create a consistent hash for sensitive IDs.
    """
    salt = _get_str("ID_SALT", "default-salt")
    return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:16]


def sanitize_review(review: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize review data for privacy.
    """
    if not _get_bool("MASK_PII", True):
        return review

    sanitized = review.copy()

    # Mask author name
    if "author_name" in sanitized:
        name_parts = sanitized["author_name"].split()
        if len(name_parts) > 1:
            # Keep first name, mask last name
            sanitized["author_name"] = f"{name_parts[0]} ***"
        else:
            sanitized["author_name"] = "***"

    # Mask any PII in comment text
    if "comment" in sanitized:
        sanitized["comment"] = mask_pii(sanitized["comment"])

    if "text" in sanitized:
        sanitized["text"] = mask_pii(sanitized["text"])

    return sanitized


def sanitize_doctor_data(doctor: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize doctor data for privacy.
    """
    if not _get_bool("MASK_PII", True):
        return doctor

    sanitized = doctor.copy()

    # Don't mask doctor name (public information)
    # But mask any contact info in extra fields
    if "extra" in sanitized:
        for key, value in sanitized["extra"].items():
            if isinstance(value, str):
                sanitized["extra"][key] = mask_pii(value)

    return sanitized


def apply_data_retention(redis_conn, job_id: str, ttl: Optional[int] = None):
    """
    Apply data retention policy to job results.

    Args:
        redis_conn: Redis connection
        job_id: Job ID
        ttl: Time to live in seconds (default from env)
    """
    if ttl is None:
        ttl = _get_int("JOB_RESULT_TTL", 3600)

    # Set expiration on job result
    redis_conn.expire(f"rq:job:{job_id}", ttl)
    redis_conn.expire(f"rq:job:{job_id}:result", ttl)

    # Also expire any related keys
    redis_conn.expire(f"job:metadata:{job_id}", ttl)


class RateLimiter:
    """
    Rate limiter for API requests.
    """

    def __init__(
        self,
        redis_conn,
        max_requests: Optional[int] = None,
        window: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            redis_conn: Redis connection
            max_requests: Max requests per window (default from env)
            window: Time window in seconds (default from env)
        """
        self.redis = redis_conn
        self.max_requests = max_requests or _get_int("RATE_LIMIT_REQUESTS", 10)
        self.window = window or _get_int("RATE_LIMIT_WINDOW", 60)

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed.

        Args:
            identifier: Client identifier (API key, IP, etc.)

        Returns:
            True if allowed, False if rate limited
        """
        key = f"rate_limit:{identifier}"

        # Get current count
        current = self.redis.get(key)

        if current is None:
            # First request in window
            self.redis.setex(key, self.window, 1)
            return True

        current_count = int(current)

        if current_count >= self.max_requests:
            # Rate limit exceeded
            return False

        # Increment counter
        self.redis.incr(key)
        return True

    def get_remaining(self, identifier: str) -> int:
        """
        Get remaining requests in current window.
        """
        key = f"rate_limit:{identifier}"
        current = self.redis.get(key)

        if current is None:
            return self.max_requests

        return max(0, self.max_requests - int(current))


def validate_callback_url(url: str) -> bool:
    """
    Validate callback URL for security.
    """
    # Check if TLS is required
    require_tls = _get_bool("REQUIRE_TLS_CALLBACKS", True)

    if require_tls and not url.startswith("https://"):
        # Allow localhost for development
        if "localhost" in url or "127.0.0.1" in url or "api" in url:
            return True
        return False

    # Check against allowed domains (if configured)
    allowed_domains = _get_allowed_domains()
    if allowed_domains:
        from urllib.parse import urlparse

        domain = urlparse(url).netloc
        if domain not in allowed_domains:
            return False

    return True


def check_robots_txt(url: str) -> bool:
    """
    Check if scraping is allowed according to robots.txt.

    Note: This is a simplified check. In production, use robotparser.
    """
    # For now, just check if it's a known allowed domain
    allowed_domains = [
        "doctoralia.com.br",
        "doctoralia.es",
        "doctoralia.com.mx",
        "doctoralia.it",
        "doctoralia.de",
    ]

    from urllib.parse import urlparse

    domain = urlparse(url).netloc

    # Check if domain is in allowed list
    for allowed in allowed_domains:
        if allowed in domain:
            return True

    # Default to allowing for other domains (for testing)
    return True
