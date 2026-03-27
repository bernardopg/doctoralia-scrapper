import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.v1.deps import (
    _load_secret,
    create_webhook_signature,
    require_api_key,
    verify_webhook_signature,
)


def _build_request(body: bytes, headers: dict[str, str]) -> Request:
    normalized_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in headers.items()
    ]

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/hooks/n8n/scrape",
        "headers": normalized_headers,
    }
    return Request(scope, receive)


def test_load_secret_prefers_config_and_falls_back_to_env():
    config = SimpleNamespace(
        security=SimpleNamespace(
            api_key="config-api-key",
            webhook_signing_secret="config-webhook-secret",
        )
    )

    with patch("config.settings.AppConfig.load", return_value=config):
        with patch.dict("os.environ", {"API_KEY": "env-api-key"}, clear=True):
            assert _load_secret("api_key", "API_KEY") == "config-api-key"

    config_empty = SimpleNamespace(
        security=SimpleNamespace(api_key="", webhook_signing_secret="")
    )
    with patch("config.settings.AppConfig.load", return_value=config_empty):
        with patch.dict("os.environ", {"API_KEY": "env-api-key"}, clear=True):
            assert _load_secret("api_key", "API_KEY") == "env-api-key"

    with patch("config.settings.AppConfig.load", side_effect=RuntimeError("no config")):
        with patch.dict("os.environ", {"API_KEY": "env-api-key"}, clear=True):
            assert _load_secret("api_key", "API_KEY") == "env-api-key"


@pytest.mark.asyncio
async def test_require_api_key_allows_dev_mode_without_secret():
    with patch("src.api.v1.deps._load_secret", return_value=None):
        assert await require_api_key(None) is True


@pytest.mark.asyncio
async def test_require_api_key_rejects_missing_and_invalid_keys():
    with patch("src.api.v1.deps._load_secret", return_value="expected-secret"):
        with pytest.raises(HTTPException) as missing:
            await require_api_key(None)
        assert missing.value.status_code == 401
        assert missing.value.detail == "API key required"

        with pytest.raises(HTTPException) as invalid:
            await require_api_key("wrong-secret")
        assert invalid.value.status_code == 401
        assert invalid.value.detail == "Invalid API key"


@pytest.mark.asyncio
async def test_require_api_key_accepts_bearer_token():
    with patch("src.api.v1.deps._load_secret", return_value="expected-secret"):
        assert await require_api_key("Bearer expected-secret") is True


def test_create_webhook_signature_returns_empty_when_secret_missing():
    with patch("src.api.v1.deps._load_secret", return_value=""):
        ts, signature = create_webhook_signature('{"ok":true}', 123.0)

    assert ts == "123.0"
    assert signature == ""


def test_create_webhook_signature_hashes_payload_when_secret_exists():
    with patch("src.api.v1.deps._load_secret", return_value="secret123"):
        ts, signature = create_webhook_signature('{"ok":true}', 123.0)

    expected = hmac.new(b"secret123", b'123.0.{"ok":true}', hashlib.sha256).hexdigest()
    assert ts == "123.0"
    assert signature == f"sha256={expected}"


@pytest.mark.asyncio
async def test_verify_webhook_signature_allows_when_secret_missing():
    request = _build_request(b'{"doctor_url":"https://example.com"}', {})

    with patch("src.api.v1.deps._load_secret", return_value=""):
        assert await verify_webhook_signature(request) is True


@pytest.mark.asyncio
async def test_verify_webhook_signature_rejects_missing_headers():
    request = _build_request(b'{"doctor_url":"https://example.com"}', {})

    with patch("src.api.v1.deps._load_secret", return_value="secret123"):
        with pytest.raises(HTTPException) as exc:
            await verify_webhook_signature(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Missing signature headers"


@pytest.mark.asyncio
async def test_verify_webhook_signature_rejects_invalid_or_stale_timestamp():
    body = b'{"doctor_url":"https://example.com"}'

    invalid_request = _build_request(
        body,
        {"X-Timestamp": "not-a-number", "X-Signature": "sha256=abc"},
    )
    with patch("src.api.v1.deps._load_secret", return_value="secret123"):
        with pytest.raises(HTTPException) as invalid:
            await verify_webhook_signature(invalid_request)
    assert invalid.value.detail == "Invalid timestamp"

    stale_ts = str(time.time() - 301)
    stale_request = _build_request(
        body,
        {"X-Timestamp": stale_ts, "X-Signature": "sha256=abc"},
    )
    with patch("src.api.v1.deps._load_secret", return_value="secret123"):
        with pytest.raises(HTTPException) as stale:
            await verify_webhook_signature(stale_request)
    assert stale.value.detail == "Request timestamp too old"


@pytest.mark.asyncio
async def test_verify_webhook_signature_rejects_invalid_signature():
    body = b'{"doctor_url":"https://example.com"}'
    timestamp = str(time.time())
    request = _build_request(
        body,
        {"X-Timestamp": timestamp, "X-Signature": "sha256=invalid"},
    )

    with patch("src.api.v1.deps._load_secret", return_value="secret123"):
        with pytest.raises(HTTPException) as exc:
            await verify_webhook_signature(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid signature"


@pytest.mark.asyncio
async def test_verify_webhook_signature_accepts_valid_signature():
    body = b'{"doctor_url":"https://example.com"}'
    timestamp = str(time.time())
    expected = hmac.new(
        b"secret123", f"{timestamp}.{body.decode('utf-8')}".encode(), hashlib.sha256
    ).hexdigest()
    request = _build_request(
        body,
        {"X-Timestamp": timestamp, "X-Signature": f"sha256={expected}"},
    )

    with patch("src.api.v1.deps._load_secret", return_value="secret123"):
        assert await verify_webhook_signature(request) is True
