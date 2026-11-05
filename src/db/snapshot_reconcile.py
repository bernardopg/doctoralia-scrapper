"""Explicit, conservative reconciliation of staged snapshots.

Each staged snapshot is one transaction; PostgreSQL serializes by workspace.
"""

import argparse
import asyncio
import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from src.db.base import database_url


def _id() -> str:
    return str(uuid.uuid4())


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid collection timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid collection timestamp") from exc
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


def _date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("invalid review date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid review date") from exc


async def _execute(conn: AsyncConnection, sql: str, **params: Any) -> Any:
    return await conn.execute(text(sql), params)


async def _reconcile_one(conn: AsyncConnection, row: Any) -> dict[str, int]:
    snapshot_id, workspace, digest, raw = row
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("staged checksum mismatch")
    data = json.loads(raw)
    reviews = data["reviews"]
    report = {
        "source": len(reviews),
        "imported": 0,
        "duplicates": 0,
        "rejected": 0,
        "pending": 0,
    }
    rejections: list[tuple[int | None, str, str, Any]] = []
    run_id = None
    try:
        timestamp = _timestamp(
            data.get("extraction_timestamp") or data.get("scraped_at")
        )
        doctor = data.get("doctor") or {}
        url = data.get("url") or doctor.get("profile_url")
        name = data.get("doctor_name") or doctor.get("name") or "Unknown"
        if (
            not isinstance(url, str)
            or not url
            or len(url) > 1024
            or not isinstance(name, str)
            or len(name) > 255
        ):
            raise ValueError("invalid profile")
    except (ValueError, AttributeError, TypeError) as exc:
        rejections.append((None, "snapshot", str(exc), data))
        report["rejected"] = len(reviews)
    else:
        result = await _execute(
            conn,
            "SELECT id FROM profiles WHERE workspace_id=:w AND source_url=:url",
            w=workspace,
            url=url,
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = _id()
            await _execute(
                conn,
                "INSERT INTO profiles (id, workspace_id, source_url, name) VALUES (:id,:w,:url,:name)",
                id=profile,
                w=workspace,
                url=url,
                name=name,
            )
        collection = (
            data.get("collection") if isinstance(data.get("collection"), dict) else {}
        )
        status = collection.get("status", "unknown")
        if status not in ("complete", "partial", "unknown", "failed", "running"):
            status = "unknown"
        expected = collection.get("expected_count")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            expected = None
        extracted = collection.get("extracted_count")
        if (
            not isinstance(extracted, int)
            or isinstance(extracted, bool)
            or extracted < 0
        ):
            extracted = len(reviews)
        reason = collection.get("stop_reason")
        if not isinstance(reason, str) or len(reason) > 100:
            reason = None
        run_id = _id()
        await _execute(
            conn,
            "INSERT INTO scrape_runs (id,profile_id,status,started_at,finished_at,expected_count,extracted_count,stop_reason) VALUES (:id,:profile,:status,:ts,:ts,:expected,:count,:reason)",
            id=run_id,
            profile=profile,
            status=status,
            ts=timestamp,
            expected=expected,
            count=extracted,
            reason=reason,
        )
        counts = Counter(
            item.get("id")
            for item in reviews
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )
        for index, item in enumerate(reviews):
            try:
                if not isinstance(item, dict):
                    raise ValueError("invalid review")
                source = item.get("id")
                if (
                    not isinstance(source, str)
                    or not re.fullmatch(r"doctoralia:[0-9]+", source)
                    or len(source) > 255
                ):
                    raise ValueError("missing or unsafe source identity")
                if counts[source] > 1:
                    raise ValueError("duplicate source identity in snapshot")
                body = item.get("comment", item.get("text"))
                if not isinstance(body, str) or not body:
                    raise ValueError("missing review body")
                author = item.get("author")
                reply = item.get("doctor_reply")
                if any(
                    value is not None and not isinstance(value, str)
                    for value in (author, reply)
                ):
                    raise ValueError("invalid review text fields")
                rating = item.get("rating")
                if rating is not None and (
                    not isinstance(rating, int)
                    or isinstance(rating, bool)
                    or not 1 <= rating <= 5
                ):
                    raise ValueError("invalid rating")
                reviewed = _date(item.get("date"))
            except ValueError as exc:
                report["rejected"] += 1
                rejections.append((index, "review", str(exc), item))
                continue
            result = await _execute(
                conn,
                "SELECT id FROM reviews WHERE profile_id=:profile AND source_id=:source",
                profile=profile,
                source=source,
            )
            review_id = result.scalar_one_or_none()
            if review_id is None:
                review_id = _id()
                await _execute(
                    conn,
                    "INSERT INTO reviews (id,profile_id,source_id,identity_status,author,body,reviewed_at,rating,doctor_reply) VALUES (:id,:profile,:source,'source',:author,:body,:reviewed,:rating,:reply)",
                    id=review_id,
                    profile=profile,
                    source=source,
                    author=author,
                    body=body,
                    reviewed=reviewed,
                    rating=rating,
                    reply=reply,
                )
                report["imported"] += 1
            else:
                report["duplicates"] += 1
            await _execute(
                conn,
                "INSERT INTO review_observations (run_id,review_id,profile_id,payload) VALUES (:run,:review,:profile,CAST(:payload AS JSON))",
                run=run_id,
                review=review_id,
                profile=profile,
                payload=json.dumps(item, ensure_ascii=False),
            )
            draft = item.get("generated_response")
            if draft is not None:
                if not isinstance(draft, str) or not draft:
                    rejections.append((index, "draft", "invalid draft", item))
                    report["pending"] += 1
                else:
                    existing = (
                        await _execute(
                            conn,
                            "SELECT body FROM review_drafts WHERE review_id=:id",
                            id=review_id,
                        )
                    ).scalar_one_or_none()
                    if existing is None:
                        await _execute(
                            conn,
                            "INSERT INTO review_drafts (review_id,body,updated_at) VALUES (:id,:body,:ts)",
                            id=review_id,
                            body=draft,
                            ts=timestamp,
                        )
                    elif existing != draft:
                        rejections.append(
                            (index, "draft", "conflicting existing draft", item)
                        )
                        report["pending"] += 1
    await _execute(
        conn,
        "INSERT INTO snapshot_reconciliations (snapshot_id,run_id,report) VALUES (:id,:run,CAST(:report AS JSON))",
        id=snapshot_id,
        run=run_id,
        report=json.dumps(report),
    )
    for item_index, kind, reason, payload in rejections:
        await _execute(
            conn,
            "INSERT INTO snapshot_rejections (id,snapshot_id,item_index,kind,reason,payload) VALUES (:id,:snapshot,:idx,:kind,:reason,CAST(:payload AS JSON))",
            id=_id(),
            snapshot=snapshot_id,
            idx=item_index,
            kind=kind,
            reason=reason,
            payload=json.dumps(payload, ensure_ascii=False),
        )
    return report


async def reconcile_staged(engine: AsyncEngine, workspace_id: str) -> dict[str, int]:
    """Reconcile each pending snapshot atomically and serialize its workspace."""
    if not workspace_id or not workspace_id.strip():
        raise ValueError("workspace is required")
    totals = {
        "source": 0,
        "imported": 0,
        "duplicates": 0,
        "rejected": 0,
        "pending": 0,
        "snapshots": 0,
    }
    async with engine.connect() as conn:
        rows = (
            (
                await _execute(
                    conn,
                    "SELECT id FROM snapshot_imports WHERE workspace_id=:w ORDER BY imported_at,id",
                    w=workspace_id,
                )
            )
            .scalars()
            .all()
        )
        exists = (
            await _execute(
                conn, "SELECT id FROM workspaces WHERE id=:w", w=workspace_id
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ValueError("workspace does not exist")
    for snapshot_id in rows:
        async with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                await _execute(
                    conn,
                    "SELECT pg_advisory_xact_lock(hashtextextended(:w, 0))",
                    w=workspace_id,
                )
            prior = (
                await _execute(
                    conn,
                    "SELECT report FROM snapshot_reconciliations WHERE snapshot_id=:id",
                    id=snapshot_id,
                )
            ).scalar_one_or_none()
            if prior is not None:
                report = prior
            else:
                row = (
                    await _execute(
                        conn,
                        "SELECT id,workspace_id,sha256,original_bytes FROM snapshot_imports WHERE id=:id AND workspace_id=:w",
                        id=snapshot_id,
                        w=workspace_id,
                    )
                ).one()
                report = await _reconcile_one(conn, row)
            for key in report:
                totals[key] += report[key]
            totals["snapshots"] += 1
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", required=True)
    args = parser.parse_args()

    async def run() -> dict[str, int]:
        engine = create_async_engine(database_url(), pool_pre_ping=True)
        try:
            return await reconcile_staged(engine, args.workspace_id)
        finally:
            await engine.dispose()

    print(json.dumps(asyncio.run(run()), indent=2))


if __name__ == "__main__":
    main()
