#!/usr/bin/env python3
"""Clean old RQ job metadata from Redis.

This keeps the dashboard queue views responsive and removes stale worker/job
records left behind by interrupted local containers.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from typing import Iterable

from rq import Queue, Worker
from rq.job import Job
from rq.registry import StartedJobRegistry

from src.jobs.queue import get_redis_connection


def _archive_job(connection, queue_name: str, job_id: str, status: str) -> None:
    try:
        job = Job.fetch(job_id, connection=connection)
        payload = {
            "job_id": job_id,
            "queue": queue_name,
            "status": status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            "description": job.description,
            "result_status": (
                job.result.get("status") if isinstance(job.result, dict) else None
            ),
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        payload = {
            "job_id": job_id,
            "queue": queue_name,
            "status": status,
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }
    connection.lpush(
        "doctoralia:rq:job_archive", json.dumps(payload, ensure_ascii=False)
    )


def _remove_job_keys(
    connection, queue_name: str, job_ids: Iterable[str], status: str
) -> int:
    deleted = 0
    for job_id in set(job_ids):
        _archive_job(connection, queue_name, job_id, status)
        keys = [
            f"rq:job:{job_id}",
            f"rq:results:{job_id}",
            f"rq:executions:{job_id}",
        ]
        keys.extend(connection.scan_iter(f"rq:execution:{job_id}:*"))
        deleted += int(connection.delete(*keys) or 0)
    return deleted


def cleanup_queue(queue_name: str, ttl_seconds: int, stale_worker_ttl: int) -> dict:
    connection = get_redis_connection()
    queue = Queue(queue_name, connection=connection)
    cutoff = time.time() - ttl_seconds

    started_registry = StartedJobRegistry(queue=queue)

    finished_key = f"rq:finished:{queue.name}"
    failed_key = f"rq:failed:{queue.name}"
    old_finished = [
        item.decode("utf-8") if isinstance(item, bytes) else str(item)
        for item in connection.zrangebyscore(finished_key, 0, cutoff)
    ]
    old_failed = [
        item.decode("utf-8") if isinstance(item, bytes) else str(item)
        for item in connection.zrangebyscore(failed_key, 0, cutoff)
    ]

    if old_finished:
        connection.zrem(finished_key, *old_finished)
    if old_failed:
        connection.zrem(failed_key, *old_failed)

    deleted_job_keys = _remove_job_keys(
        connection, queue.name, old_finished, "finished"
    )
    deleted_job_keys += _remove_job_keys(connection, queue.name, old_failed, "failed")
    started_registry.cleanup()

    stale_workers = []
    now = time.time()
    for worker in Worker.all(connection=connection):
        if queue.name not in [worker_queue.name for worker_queue in worker.queues]:
            continue
        last_heartbeat = worker.last_heartbeat
        if last_heartbeat is None:
            continue
        heartbeat_ts = last_heartbeat.timestamp()
        if now - heartbeat_ts > stale_worker_ttl:
            stale_workers.append(worker.name)
            worker.register_death()

    return {
        "queue": queue_name,
        "finished_jobs_removed": len(old_finished),
        "failed_jobs_removed": len(old_failed),
        "redis_keys_deleted": deleted_job_keys,
        "stale_workers_removed": stale_workers,
        "started_registry_cleaned": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean old RQ jobs from Redis")
    parser.add_argument("--queue", default="doctoralia")
    parser.add_argument("--ttl", type=int, default=86400)
    parser.add_argument("--stale-worker-ttl", type=int, default=3600)
    args = parser.parse_args()

    result = cleanup_queue(args.queue, args.ttl, args.stale_worker_ttl)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
