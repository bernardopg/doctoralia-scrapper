"""
Authentication and security dependencies for API v1.
"""

import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Depends(api_key_header)) -> bool:
    """
    Validate API key from header.
    Supports both X-API-Key and Authorization: Bearer formats.
    """
    expected = os.getenv("API_KEY")
    
    if not expected:
        # No API key configured, allow access (dev mode)
        return True
    
    if not api_key:
        # Check Authorization header as fallback
        raise HTTPException(status_code=401, detail="API key required")
    
    # Support Bearer token format
    if api_key.startswith("Bearer "):
        api_key = api_key[7:]
    
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True


async def verify_webhook_signature(
    request: Request,
    timestamp_header: Optional[str] = None,
    signature_header: Optional[str] = None
) -> bool:
    """
    Verify webhook HMAC signature.
    """
    secret = os.getenv("WEBHOOK_SIGNING_SECRET")
    
    if not secret:
        # No secret configured, skip verification
        return True
    
    # Get headers
    timestamp = timestamp_header or request.headers.get("X-Timestamp")
    signature = signature_header or request.headers.get("X-Signature")
    
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing signature headers")
    
    # Check timestamp freshness (5 minute window)
    try:
        ts = float(timestamp)
        if abs(time.time() - ts) > 300:
            raise HTTPException(status_code=401, detail="Request timestamp too old")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")
    
    # Get raw body
    body = await request.body()
    
    # Calculate expected signature
    message = f"{timestamp}.{body.decode('utf-8')}"
    expected_sig = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Remove "sha256=" prefix if present
    if signature.startswith("sha256="):
        signature = signature[7:]
    
    # Constant-time comparison
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return True


def create_webhook_signature(payload: str, timestamp: float) -> tuple[str, str]:
    """
    Create webhook signature for outbound callbacks.
    
    Returns:
        Tuple of (timestamp_str, signature)
    """
    secret = os.getenv("WEBHOOK_SIGNING_SECRET", "")
    
    if not secret:
        return str(timestamp), ""
    
    message = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return str(timestamp), f"sha256={signature}"
