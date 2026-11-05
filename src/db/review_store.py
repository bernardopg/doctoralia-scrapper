"""PostgreSQL review storage used by the opt-in ``postgres`` backend.

Source of truth and transition
------------------------------
With ``STORAGE_BACKEND=postgres`` collections are still published as JSON
snapshots first; the JSON directory keeps working as the rollback copy. Each
publication then stages every snapshot of the directory (idempotent by
checksum) and reconciles it into the database. The dashboard reads profiles,
runs, observed reviews and drafts from PostgreSQL. Draft edits are checked
against pending conflicts, written to JSON with a new ``draft_edit`` version
and then to the database, so both copies agree and a database failure is
healed by the next synchronisation.

Reviews without a stable ``doctoralia:<n>`` identity are rejected by
reconciliation and are therefore absent from database reads; the number of
rejected reviews is reported per run.
"""

import argparse
import asyncio
import json
import threading
from collections import defaultdict
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from src.db.base import database_url
from src.db.draft_resolution import draft_for_review
from src.db.snapshot_import import inspect_snapshots, stage_snapshots
from src.db.snapshot_reconcile import reconcile_staged

T = TypeVar("T")


class StorageError(RuntimeError):
    """The database backend cannot serve the request."""


class PendingDraftConflict(StorageError):
    """A draft has unresolved conflicts and must not be edited or approved."""


async def _execute(conn: AsyncConnection, sql: str, **params: Any) -> Any:
    return await conn.execute(text(sql), params)


async def workspace_id_for(engine: AsyncEngine, slug: str) -> str:
    async with engine.connect() as conn:
        found = (
            await _execute(
                conn,
                "SELECT id FROM workspaces WHERE slug=:slug OR id=:slug",
                slug=slug,
            )
        ).scalar_one_or_none()
    if found is None:
        raise StorageError(f"workspace '{slug}' does not exist")
    return str(found)


async def sync_directory(
    engine: AsyncEngine, workspace_id: str, data_dir: Path
) -> dict[str, Any]:
    """Stage every snapshot of a directory and reconcile the workspace."""
    candidates, rejected = inspect_snapshots(Path(data_dir))
    staged = await stage_snapshots(engine, workspace_id, candidates)
    report = await reconcile_staged(engine, workspace_id)
    return {"staged": staged, "unreadable": len(rejected), "reconciled": report}


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


async def load_snapshot_payloads(
    engine: AsyncEngine, workspace_id: str
) -> list[dict[str, Any]]:
    """Rebuild one snapshot payload per scrape run from database rows.

    Payloads follow the JSON snapshot format so the workspace aggregation is
    shared by both backends. The newest run of each profile carries the current
    drafts: approved drafts are returned, pending ones are withheld and marked
    with ``draft_status: "pending"``.
    """
    async with engine.connect() as conn:
        runs = (
            await _execute(
                conn,
                "SELECT r.id, r.profile_id, r.status, r.started_at, r.expected_count, "
                "r.extracted_count, r.stop_reason, p.name, p.source_url, "
                "o.report FROM scrape_runs r JOIN profiles p ON p.id = r.profile_id "
                "LEFT JOIN snapshot_reconciliations o ON o.run_id = r.id "
                "WHERE p.workspace_id=:w ORDER BY r.started_at, r.id",
                w=workspace_id,
            )
        ).all()
        observations = (
            await _execute(
                conn,
                "SELECT o.run_id, o.review_id, o.payload, v.reviewed_at "
                "FROM review_observations o JOIN reviews v ON v.id = o.review_id "
                "JOIN profiles p ON p.id = v.profile_id WHERE p.workspace_id=:w "
                "ORDER BY v.reviewed_at DESC NULLS LAST, v.source_id",
                w=workspace_id,
            )
        ).all()
        by_run: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for row in observations:
            payload = row.payload if isinstance(row.payload, dict) else {}
            by_run[row.run_id].append((row.review_id, dict(payload)))

        latest: dict[str, str] = {}
        for run in runs:
            latest[run.profile_id] = run.id

        payloads = []
        for run in runs:
            reviews = []
            for review_id, payload in by_run.get(run.id, []):
                if latest[run.profile_id] == run.id:
                    draft = await draft_for_review(conn, review_id)
                    payload["generated_response"] = draft["body"] or ""
                    payload["draft_status"] = draft["status"]
                    payload["draft_revision"] = draft["revision"]
                reviews.append(payload)
            report = run.report if isinstance(run.report, dict) else {}
            payloads.append(
                {
                    "doctor_name": run.name,
                    "url": run.source_url,
                    "extraction_timestamp": _iso(run.started_at),
                    "collection": {
                        "status": run.status,
                        "expected_count": run.expected_count,
                        "extracted_count": run.extracted_count,
                        "stop_reason": run.stop_reason,
                        "rejected_reviews": report.get("rejected", 0),
                    },
                    "reviews": reviews,
                    "_storage": {"backend": "postgres", "run_id": run.id},
                }
            )
        return payloads


async def save_draft(
    engine: AsyncEngine,
    workspace_id: str,
    profile_url: str,
    source_id: str,
    body: Optional[str],
    edit_version: int,
    check_only: bool = False,
) -> dict[str, Any]:
    """Record a dashboard edit; refuse while the review has pending conflicts."""
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await _execute(
                conn,
                "SELECT pg_advisory_xact_lock(hashtextextended(:w, 0))",
                w=workspace_id,
            )
        review_id = (
            await _execute(
                conn,
                "SELECT v.id FROM reviews v JOIN profiles p ON p.id = v.profile_id "
                "WHERE p.workspace_id=:w AND p.source_url=:url AND v.source_id=:source",
                w=workspace_id,
                url=profile_url,
                source=source_id,
            )
        ).scalar_one_or_none()
        if review_id is None:
            raise StorageError("review is not stored in the database")
        draft = await draft_for_review(conn, review_id)
        if draft["status"] == "pending":
            raise PendingDraftConflict(
                "draft has pending conflicts; resolve them before editing"
            )
        if check_only:
            return {"review_id": review_id, "revision": draft["revision"]}
        body = body or None
        if body is None:
            await _execute(
                conn, "DELETE FROM review_drafts WHERE review_id=:id", id=review_id
            )
        else:
            updated = await _execute(
                conn,
                "UPDATE review_drafts SET body=:body, revision=revision+1, "
                "updated_at=CURRENT_TIMESTAMP WHERE review_id=:id",
                id=review_id,
                body=body,
            )
            if updated.rowcount == 0:
                await _execute(
                    conn,
                    "INSERT INTO review_drafts (review_id, body, revision) "
                    "VALUES (:id, :body, :rev)",
                    id=review_id,
                    body=body,
                    rev=max(draft["revision"], 0) + 1,
                )
        # Keep the observation state aligned so the next published snapshot,
        # which carries this edit, is not reported as a conflict.
        await _execute(
            conn,
            "UPDATE snapshot_draft_state SET body=:body, "
            "edit_version=GREATEST(edit_version, :version) WHERE review_id=:id",
            body=body,
            version=edit_version,
            id=review_id,
        )
        return {"review_id": review_id, "status": "approved" if body else "absent"}


async def approved_drafts(
    engine: AsyncEngine, workspace_id: str
) -> dict[tuple[str, str], Optional[str]]:
    """Approved draft (or absence) per (profile URL, source ID); pending skipped."""
    async with engine.connect() as conn:
        rows = (
            await _execute(
                conn,
                "SELECT v.id, v.source_id, p.source_url FROM reviews v "
                "JOIN profiles p ON p.id = v.profile_id WHERE p.workspace_id=:w",
                w=workspace_id,
            )
        ).all()
        result: dict[tuple[str, str], Optional[str]] = {}
        for row in rows:
            draft = await draft_for_review(conn, row.id)
            if draft["status"] != "pending":
                result[(row.source_url, row.source_id)] = draft["body"]
        return result


class StorageRunner:
    """Run async storage calls from synchronous Flask, RQ and Selenium code.

    One event loop thread owns the engine, so its connection pool is reused
    across requests instead of being created per call.
    """

    def __init__(self, dsn: Optional[str] = None, timeout: float = 30.0) -> None:
        self._dsn = dsn
        self._timeout = timeout
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._engine: Optional[AsyncEngine] = None
        self._lock = threading.Lock()

    def _start(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever, name="storage-loop", daemon=True
                )
                thread.start()
                self._loop = loop
            return self._loop

    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self._dsn or database_url(), pool_pre_ping=True
            )
        return self._engine

    def run(self, factory: Callable[[AsyncEngine], Awaitable[T]]) -> T:
        loop = self._start()

        async def call() -> T:
            return await factory(self.engine())

        future: Future[T] = asyncio.run_coroutine_threadsafe(call(), loop)
        return future.result(timeout=self._timeout)

    def close(self) -> None:
        if self._loop is None:
            return
        if self._engine is not None:
            asyncio.run_coroutine_threadsafe(self._engine.dispose(), self._loop).result(
                timeout=self._timeout
            )
            self._engine = None
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop = None


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="stage and reconcile a snapshot directory")
    sync.add_argument("--workspace", default="default", help="workspace slug or id")
    sync.add_argument("--data-dir", type=Path, default=Path("data"))
    export = sub.add_parser(
        "export-drafts",
        help="write approved database drafts into the latest JSON snapshots",
    )
    export.add_argument("--workspace", default="default")
    export.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)

    async def run() -> dict[str, Any]:
        engine = create_async_engine(database_url(), pool_pre_ping=True)
        try:
            workspace = await workspace_id_for(engine, args.workspace)
            if args.command == "sync":
                return await sync_directory(engine, workspace, args.data_dir)
            drafts = await approved_drafts(engine, workspace)
            from src.services.storage_backend import export_drafts_to_json

            return export_drafts_to_json(args.data_dir, drafts)
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(run())
    except (StorageError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
