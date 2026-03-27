"""
Redis-backed metrics storage for the API.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import redis


class RedisAPIMetricsStore:
    """Persist lightweight API metrics in Redis for multi-process visibility."""

    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str = "doctoralia:api:metrics",
        max_samples: int = 500,
        active_request_ttl_s: int = 3600,
    ) -> None:
        self.redis = redis_client
        self.prefix = prefix
        self.max_samples = max_samples
        self.active_request_ttl_s = active_request_ttl_s

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        prefix: str = "doctoralia:api:metrics",
        max_samples: int = 500,
        active_request_ttl_s: int = 3600,
    ) -> "RedisAPIMetricsStore":
        return cls(
            redis.Redis.from_url(redis_url),
            prefix=prefix,
            max_samples=max_samples,
            active_request_ttl_s=active_request_ttl_s,
        )

    @property
    def counters_key(self) -> str:
        return f"{self.prefix}:counters"

    @property
    def durations_key(self) -> str:
        return f"{self.prefix}:request_durations_ms"

    @property
    def active_requests_key(self) -> str:
        return f"{self.prefix}:active_requests"

    @staticmethod
    def _as_int(value: Any) -> int:
        if value in (None, ""):
            return 0
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return int(value)

    @staticmethod
    def _normalize_hash(raw_hash: dict[Any, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in raw_hash.items():
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            normalized[str(key)] = value
        return normalized

    def _increment_counter(self, field: str, amount: int = 1) -> None:
        self.redis.hincrby(self.counters_key, field, amount)

    def record_request_start(
        self, request_id: str, started_at_s: Optional[float] = None
    ) -> None:
        started_at_s = started_at_s or time.time()
        pipeline = self.redis.pipeline()
        pipeline.hincrby(self.counters_key, "requests_total", 1)
        pipeline.zadd(self.active_requests_key, {request_id: started_at_s})
        pipeline.execute()

    def record_request_end(
        self, request_id: str, duration_ms: int, failed: bool = False
    ) -> None:
        pipeline = self.redis.pipeline()
        pipeline.zrem(self.active_requests_key, request_id)
        pipeline.lpush(self.durations_key, int(duration_ms))
        pipeline.ltrim(self.durations_key, 0, self.max_samples - 1)
        if failed:
            pipeline.hincrby(self.counters_key, "requests_failed_total", 1)
        pipeline.execute()

    def increment_scrapes(self, amount: int = 1) -> None:
        self._increment_counter("scrapes_total", amount)

    def increment_scrapes_failed(self, amount: int = 1) -> None:
        self._increment_counter("scrapes_failed_total", amount)

    def increment_generation(self, amount: int = 1) -> None:
        self._increment_counter("generation_total", amount)

    def increment_analysis(self, amount: int = 1) -> None:
        self._increment_counter("analysis_total", amount)

    def cleanup_stale_active_requests(self, now_s: Optional[float] = None) -> None:
        now_s = now_s or time.time()
        cutoff = now_s - self.active_request_ttl_s
        self.redis.zremrangebyscore(self.active_requests_key, "-inf", cutoff)

    def snapshot(self, now_s: Optional[float] = None) -> dict[str, Any]:
        self.cleanup_stale_active_requests(now_s)
        counters = self._normalize_hash(self.redis.hgetall(self.counters_key) or {})
        durations_raw = self.redis.lrange(self.durations_key, 0, self.max_samples - 1)
        durations = [self._as_int(value) for value in durations_raw]

        return {
            "requests_total": self._as_int(counters.get("requests_total")),
            "requests_in_progress": self._as_int(
                self.redis.zcard(self.active_requests_key)
            ),
            "requests_failed_total": self._as_int(
                counters.get("requests_failed_total")
            ),
            "scrapes_total": self._as_int(counters.get("scrapes_total")),
            "scrapes_failed_total": self._as_int(counters.get("scrapes_failed_total")),
            "generation_total": self._as_int(counters.get("generation_total")),
            "analysis_total": self._as_int(counters.get("analysis_total")),
            "request_durations_ms": durations,
        }
