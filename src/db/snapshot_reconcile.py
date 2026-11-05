"""Explicit, conservative reconciliation of staged snapshots.

Each staged snapshot is one transaction; PostgreSQL serializes by workspace.
"""

import argparse
import asyncio
import hashlib
import json
import math
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
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("collection timestamp has no timezone")
    try:
        return result.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("collection timestamp outside supported UTC range") from exc


def _date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("invalid review date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            # Preserve the civil date expressed by the source, without UTC conversion.
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ValueError("invalid review date") from exc


def _safe_json(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        return not any(ord(c) == 0 or 0xD800 <= ord(c) <= 0xDFFF for c in value)
    if isinstance(value, list):
        return all(_safe_json(item) for item in value)
    if isinstance(value, dict):
        return all(_safe_json(key) and _safe_json(item) for key, item in value.items())
    return True


def _rejection_payload(value: Any) -> Any:
    return value if _safe_json(value) else {"original": "see staged snapshot bytes"}


def _count(value: Any, field: str, default: int | None) -> int | None:
    if value is None:
        return default
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= 2147483647
    ):
        raise ValueError("invalid " + field)
    return value


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
    # (item index, kind, reason, payload, review id for draft conflicts)
    rejections: list[tuple[int | None, str, str, Any, str | None]] = []
    run_id = None
    try:
        timestamp = _timestamp(
            data.get("extraction_timestamp") or data.get("scraped_at")
        )
        doctor = data.get("doctor") or {}
        url = data.get("url") or doctor.get("profile_url")
        name = data.get("doctor_name") or doctor.get("name") or "Unknown"
        collection = data.get("collection") or {}
        if not isinstance(collection, dict):
            raise ValueError("invalid collection")
        metadata = {k: v for k, v in data.items() if k != "reviews"}
        if not _safe_json(metadata):
            raise ValueError("invalid snapshot characters")
        expected = _count(collection.get("expected_count"), "expected_count", None)
        extracted = _count(
            collection.get("extracted_count"), "extracted_count", len(reviews)
        )
        if (
            not isinstance(url, str)
            or not url.strip()
            or len(url) > 1024
            or not isinstance(name, str)
            or len(name) > 255
        ):
            raise ValueError("invalid profile")
        url = url.strip()
    except (ValueError, AttributeError, TypeError) as exc:
        rejections.append((None, "snapshot", str(exc), data, None))
        report["rejected"] = len(reviews)
    else:
        candidates = (
            await _execute(
                conn,
                "SELECT id,source_url FROM profiles WHERE workspace_id=:w",
                w=workspace,
            )
        ).all()
        matches = [
            (pid, source)
            for pid, source in candidates
            if source.strip().lower() == url.lower()
        ]
        # Case differences in paths may identify different resources.
        if len(matches) > 1 or (matches and matches[0][1].strip() != url):
            rejections.append((None, "snapshot", "ambiguous profile URL", data, None))
            report["rejected"] = len(reviews)
            matches = []
            profile = None
        else:
            profile = matches[0][0] if matches else _id()
            if not matches:
                await _execute(
                    conn,
                    "INSERT INTO profiles (id, workspace_id, source_url, name) VALUES (:id,:w,:url,:name)",
                    id=profile,
                    w=workspace,
                    url=url,
                    name=name,
                )
        if profile is None:
            await _record_outcome(conn, snapshot_id, None, report, rejections)
            return report
        status = collection.get("status", "unknown")
        if status not in ("complete", "partial", "unknown", "failed", "running"):
            status = "unknown"
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
                if not _safe_json(item):
                    raise ValueError("invalid review characters")
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
                rejections.append((index, "review", str(exc), item, None))
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
            valid = draft is None or isinstance(draft, str)
            if not valid:
                rejections.append((index, "draft", "invalid draft", item, review_id))
                report["pending"] += 1
                continue
            # Empty and missing responses are both authoritative absence.
            draft = draft or None
            edit_version = _edit_version(item)
            state = (
                await _execute(
                    conn,
                    "SELECT observed_at,body,edit_version FROM snapshot_draft_state WHERE review_id=:id",
                    id=review_id,
                )
            ).one_or_none()
            existing = (
                await _execute(
                    conn,
                    "SELECT body FROM review_drafts WHERE review_id=:id",
                    id=review_id,
                )
            ).scalar_one_or_none()
            if state is None:
                if existing is None and draft is not None:
                    prior_observation = (
                        await _execute(
                            conn,
                            "SELECT 1 FROM review_observations WHERE review_id=:id AND run_id<>:run LIMIT 1",
                            id=review_id,
                            run=run_id,
                        )
                    ).scalar_one_or_none()
                    if prior_observation:
                        rejections.append(
                            (
                                index,
                                "draft",
                                "unknown earlier draft provenance",
                                item,
                                review_id,
                            )
                        )
                        report["pending"] += 1
                    else:
                        await _execute(
                            conn,
                            "INSERT INTO review_drafts (review_id,body,updated_at) VALUES (:id,:body,:ts)",
                            id=review_id,
                            body=draft,
                            ts=timestamp,
                        )
                elif existing is not None and existing != draft:
                    rejections.append(
                        (index, "draft", "conflicting existing draft", item, review_id)
                    )
                    report["pending"] += 1
                await _execute(
                    conn,
                    "INSERT INTO snapshot_draft_state (review_id,snapshot_id,observed_at,body,edit_version) VALUES (:id,:snapshot,:ts,:body,:version)",
                    snapshot=snapshot_id,
                    id=review_id,
                    ts=timestamp,
                    body=draft,
                    version=edit_version,
                )
            else:
                previous_time, previous_body, previous_version = state
                if (
                    edit_version > previous_version
                    and timestamp >= previous_time
                    and not await _has_pending_draft_conflict(conn, review_id)
                ):
                    # A newer versioned edit published by the dashboard or by a
                    # requested generation replaces the draft explicitly.
                    await _apply_versioned_edit(conn, review_id, draft, timestamp)
                    await _execute(
                        conn,
                        "UPDATE snapshot_draft_state SET snapshot_id=:snapshot,observed_at=:ts,body=:body,edit_version=:version WHERE review_id=:id",
                        snapshot=snapshot_id,
                        id=review_id,
                        ts=timestamp,
                        body=draft,
                        version=edit_version,
                    )
                    continue
                if previous_body != draft:
                    rejections.append(
                        (
                            index,
                            "draft",
                            "conflicting draft observations",
                            item,
                            review_id,
                        )
                    )
                    report["pending"] += 1
                if timestamp > previous_time:
                    await _execute(
                        conn,
                        "UPDATE snapshot_draft_state SET snapshot_id=:snapshot,observed_at=:ts,body=:body WHERE review_id=:id",
                        snapshot=snapshot_id,
                        id=review_id,
                        ts=timestamp,
                        body=draft,
                    )
    await _record_outcome(conn, snapshot_id, run_id, report, rejections)
    return report


def _edit_version(item: dict[str, Any]) -> int:
    metadata = item.get("draft_edit")
    if not isinstance(metadata, dict):
        return 0
    version = metadata.get("version")
    return version if type(version) is int and version > 0 else 0


async def _has_pending_draft_conflict(conn: AsyncConnection, review_id: str) -> bool:
    found = await _execute(
        conn,
        "SELECT 1 FROM snapshot_rejections WHERE review_id=:id AND kind='draft' "
        "AND resolution_id IS NULL LIMIT 1",
        id=review_id,
    )
    return found.scalar_one_or_none() is not None


async def _apply_versioned_edit(
    conn: AsyncConnection, review_id: str, body: str | None, timestamp: datetime
) -> None:
    current = (
        await _execute(
            conn, "SELECT revision FROM review_drafts WHERE review_id=:id", id=review_id
        )
    ).scalar_one_or_none()
    if body is None:
        await _execute(
            conn, "DELETE FROM review_drafts WHERE review_id=:id", id=review_id
        )
    elif current is None:
        await _execute(
            conn,
            "INSERT INTO review_drafts (review_id,body,updated_at) VALUES (:id,:body,:ts)",
            id=review_id,
            body=body,
            ts=timestamp,
        )
    else:
        await _execute(
            conn,
            "UPDATE review_drafts SET body=:body,updated_at=:ts,revision=revision+1 "
            "WHERE review_id=:id",
            id=review_id,
            body=body,
            ts=timestamp,
        )


async def _record_outcome(
    conn: AsyncConnection,
    snapshot_id: str,
    run_id: str | None,
    report: dict[str, int],
    rejections: list[tuple[int | None, str, str, Any, str | None]],
) -> None:
    await _execute(
        conn,
        "INSERT INTO snapshot_reconciliations (snapshot_id,run_id,report) VALUES (:id,:run,CAST(:report AS JSON))",
        id=snapshot_id,
        run=run_id,
        report=json.dumps(report),
    )
    for item_index, kind, reason, payload, review_id in rejections:
        await _execute(
            conn,
            "INSERT INTO snapshot_rejections (id,snapshot_id,item_index,kind,reason,payload,review_id) VALUES (:id,:snapshot,:idx,:kind,:reason,CAST(:payload AS JSON),:review)",
            id=_id(),
            snapshot=snapshot_id,
            idx=item_index,
            kind=kind,
            reason=reason,
            payload=json.dumps(_rejection_payload(payload), ensure_ascii=False),
            review=review_id,
        )


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
                    # Files staged together share imported_at; snapshot file names start
                    # with the collection timestamp, so they keep chronological order.
                    "SELECT id FROM snapshot_imports WHERE workspace_id=:w ORDER BY imported_at,filename,id",
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
