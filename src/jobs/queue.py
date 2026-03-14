"""
Redis Queue configuration for async jobs.
"""

import os

import redis
from rq import Queue


def get_redis_connection():
    """Get Redis connection."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        from config.settings import AppConfig

        redis_url = AppConfig.load().integrations.redis_url or redis_url
    except Exception:
        pass
    return redis.from_url(redis_url)


def get_queue(name: str = "doctoralia") -> Queue:
    """Get RQ queue instance."""
    return Queue(name, connection=get_redis_connection(), default_timeout=1800)
