"""Inspect and resolve imported draft conflicts with an append-only audit trail.

Snapshot reconciliation (``src.db.snapshot_reconcile``) never overwrites a
draft when observations disagree; it records a ``draft`` rejection instead.
This module lets an operator review every pending conflict of a review and
record an explicit decision:

* ``keep``: keep the current draft (or its absence);
* ``choose``: replace it with the draft proposed by one pending conflict;
* ``clear``: remove the draft.

Each decision requires the actor and the revision the operator looked at.
A decision taken on an outdated revision is rejected, so two operators can
never silently overwrite each other. Later conflicting observations create new
pending rejections and reopen the review. Rejections that could not be linked
to a review (missing, legacy or ambiguous identities) stay pending: no
association is inferred.

The application runtime still reads drafts from JSON snapshots. Use
:func:`draft_for_review` from future database repositories: it never reports a
draft with unresolved conflicts as approved.
"""

import argparse
import asyncio
import json
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from src.db.base import database_url

DECISIONS = ("keep", "choose", "clear")


class ResolutionError(ValueError):
    """The requested decision is invalid for the current pending conflicts."""


class StaleDecisionError(RuntimeError):
    """The draft changed after the operator inspected it."""


async def _execute(conn: AsyncConnection, sql: str, **params: Any) -> Any:
    return await conn.execute(text(sql), params)


def _proposed_body(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    body = payload.get("generated_response")
    return body if isinstance(body, str) and body else None


async def _current(conn: AsyncConnection, review_id: str) -> tuple[Optional[str], int]:
    """Return the active draft body and its revision (0 when never set)."""
    row = (
        await _execute(
            conn,
            "SELECT body, revision FROM review_drafts WHERE review_id=:id",
            id=review_id,
        )
    ).one_or_none()
    if row is not None:
        return row.body, int(row.revision)
    last = (
        await _execute(
            conn,
            "SELECT max(resulting_revision) FROM draft_resolutions "
            "WHERE review_id=:id",
            id=review_id,
        )
    ).scalar_one()
    return None, int(last or 0)


async def _pending(conn: AsyncConnection, review_id: str) -> list[dict[str, Any]]:
    rows = (
        await _execute(
            conn,
            "SELECT r.id, r.snapshot_id, r.item_index, r.reason, r.payload, "
            "i.imported_at FROM snapshot_rejections r "
            "JOIN snapshot_imports i ON i.id = r.snapshot_id "
            "WHERE r.review_id=:id AND r.kind='draft' AND r.resolution_id IS NULL "
            "ORDER BY i.imported_at, r.id",
            id=review_id,
        )
    ).all()
    return [
        {
            "rejection_id": row.id,
            "snapshot_id": row.snapshot_id,
            "item_index": row.item_index,
            "reason": row.reason,
            "proposed_body": _proposed_body(row.payload),
            "staged_at": row.imported_at.isoformat() if row.imported_at else None,
        }
        for row in rows
    ]


async def _observations(conn: AsyncConnection, review_id: str) -> list[dict[str, Any]]:
    rows = (
        await _execute(
            conn,
            "SELECT o.run_id, s.started_at, o.payload FROM review_observations o "
            "JOIN scrape_runs s ON s.id = o.run_id WHERE o.review_id=:id "
            "ORDER BY s.started_at, o.run_id",
            id=review_id,
        )
    ).all()
    return [
        {
            "run_id": row.run_id,
            "observed_at": row.started_at.isoformat() if row.started_at else None,
            "draft": _proposed_body(row.payload),
        }
        for row in rows
    ]


async def _review_in_workspace(
    conn: AsyncConnection, workspace_id: str, review_id: str, lock: bool = False
) -> Any:
    sql = (
        "SELECT r.id, r.source_id, r.profile_id FROM reviews r "
        "JOIN profiles p ON p.id = r.profile_id "
        "WHERE r.id=:review AND p.workspace_id=:workspace"
    )
    if lock and conn.dialect.name == "postgresql":
        sql += " FOR UPDATE OF r"
    return (
        await _execute(conn, sql, review=review_id, workspace=workspace_id)
    ).one_or_none()


async def _describe(
    conn: AsyncConnection, workspace_id: str, review_id: str
) -> dict[str, Any]:
    review = await _review_in_workspace(conn, workspace_id, review_id)
    if review is None:
        raise ResolutionError("review not found in workspace")
    body, revision = await _current(conn, review_id)
    pending = await _pending(conn, review_id)
    history = (
        await _execute(
            conn,
            "SELECT id, decision, actor, expected_revision, resulting_revision, "
            "resolved_body, decided_at FROM draft_resolutions WHERE review_id=:id "
            "ORDER BY decided_at, id",
            id=review_id,
        )
    ).all()
    return {
        "review_id": review_id,
        "source_id": review.source_id,
        "profile_id": review.profile_id,
        "current_draft": body,
        "revision": revision,
        "status": "pending" if pending else ("approved" if body else "absent"),
        "pending": pending,
        "observations": await _observations(conn, review_id),
        "resolutions": [
            {
                "resolution_id": row.id,
                "decision": row.decision,
                "actor": row.actor,
                "expected_revision": row.expected_revision,
                "resulting_revision": row.resulting_revision,
                "resolved_body": row.resolved_body,
                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            }
            for row in history
        ],
    }


async def list_pending(
    engine: AsyncEngine, workspace_id: str, review_id: Optional[str] = None
) -> dict[str, Any]:
    """List reviews with unresolved draft conflicts and unlinked conflicts."""
    async with engine.connect() as conn:
        exists = (
            await _execute(
                conn, "SELECT id FROM workspaces WHERE id=:w", w=workspace_id
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ResolutionError("workspace does not exist")
        if review_id is not None:
            return {"reviews": [await _describe(conn, workspace_id, review_id)]}
        ids = (
            (
                await _execute(
                    conn,
                    "SELECT DISTINCT r.review_id FROM snapshot_rejections r "
                    "JOIN reviews v ON v.id = r.review_id "
                    "JOIN profiles p ON p.id = v.profile_id "
                    "WHERE p.workspace_id=:w AND r.kind='draft' "
                    "AND r.resolution_id IS NULL ORDER BY r.review_id",
                    w=workspace_id,
                )
            )
            .scalars()
            .all()
        )
        unlinked = (
            await _execute(
                conn,
                "SELECT r.id, r.snapshot_id, r.item_index, r.reason "
                "FROM snapshot_rejections r "
                "JOIN snapshot_imports i ON i.id = r.snapshot_id "
                "WHERE i.workspace_id=:w AND r.kind='draft' AND r.review_id IS NULL "
                "ORDER BY i.imported_at, r.id",
                w=workspace_id,
            )
        ).all()
        return {
            "reviews": [await _describe(conn, workspace_id, item) for item in ids],
            "unlinked": [
                {
                    "rejection_id": row.id,
                    "snapshot_id": row.snapshot_id,
                    "item_index": row.item_index,
                    "reason": row.reason,
                }
                for row in unlinked
            ],
        }


async def resolve(
    engine: AsyncEngine,
    workspace_id: str,
    review_id: str,
    decision: str,
    actor: str,
    expected_revision: int,
    rejection_id: Optional[str] = None,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Apply one decision to every pending draft conflict of a review."""
    if decision not in DECISIONS:
        raise ResolutionError(f"decision must be one of {', '.join(DECISIONS)}")
    if not actor or not actor.strip():
        raise ResolutionError("actor is required")
    if (decision == "choose") != (rejection_id is not None):
        raise ResolutionError("rejection_id is required only for 'choose'")

    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            # Same lock as reconciliation: imports and decisions never interleave.
            await _execute(
                conn,
                "SELECT pg_advisory_xact_lock(hashtextextended(:w, 0))",
                w=workspace_id,
            )
        review = await _review_in_workspace(conn, workspace_id, review_id, lock=True)
        if review is None:
            raise ResolutionError("review not found in workspace")
        body, revision = await _current(conn, review_id)
        if revision != expected_revision:
            raise StaleDecisionError(
                f"draft revision is {revision}, decision expected {expected_revision}"
            )
        pending = await _pending(conn, review_id)
        if not pending:
            raise ResolutionError("review has no pending draft conflict")

        new_body: Optional[str]
        if decision == "keep":
            new_body = body
        elif decision == "clear":
            new_body = None
        else:
            chosen = next(
                (item for item in pending if item["rejection_id"] == rejection_id),
                None,
            )
            if chosen is None:
                raise ResolutionError("rejection is not a pending conflict of review")
            if chosen["proposed_body"] is None:
                raise ResolutionError("chosen conflict has no usable draft")
            new_body = chosen["proposed_body"]

        new_revision = revision + 1
        exists = (
            await _execute(
                conn, "SELECT 1 FROM review_drafts WHERE review_id=:id", id=review_id
            )
        ).scalar_one_or_none()
        if new_body is None:
            await _execute(
                conn, "DELETE FROM review_drafts WHERE review_id=:id", id=review_id
            )
        elif exists:
            await _execute(
                conn,
                "UPDATE review_drafts SET body=:body, revision=:rev, "
                "updated_at=CURRENT_TIMESTAMP WHERE review_id=:id",
                body=new_body,
                rev=new_revision,
                id=review_id,
            )
        else:
            await _execute(
                conn,
                "INSERT INTO review_drafts (review_id, body, revision) "
                "VALUES (:id, :body, :rev)",
                id=review_id,
                body=new_body,
                rev=new_revision,
            )

        resolution_id = str(uuid.uuid4())
        resolved_ids = [item["rejection_id"] for item in pending]
        await _execute(
            conn,
            "INSERT INTO draft_resolutions (id, review_id, decision, "
            "chosen_rejection_id, previous_body, resolved_body, expected_revision, "
            "resulting_revision, actor, note, resolved_rejection_ids) VALUES "
            "(:id, :review, :decision, :chosen, :previous, :resolved, :expected, "
            ":resulting, :actor, :note, CAST(:ids AS JSON))",
            id=resolution_id,
            review=review_id,
            decision=decision,
            chosen=rejection_id,
            previous=body,
            resolved=new_body,
            expected=expected_revision,
            resulting=new_revision,
            actor=actor.strip(),
            note=note,
            ids=json.dumps(resolved_ids),
        )
        for item in resolved_ids:
            await _execute(
                conn,
                "UPDATE snapshot_rejections SET resolution_id=:res "
                "WHERE id=:id AND resolution_id IS NULL",
                res=resolution_id,
                id=item,
            )
        return {
            "resolution_id": resolution_id,
            "review_id": review_id,
            "decision": decision,
            "previous_body": body,
            "resolved_body": new_body,
            "revision": new_revision,
            "resolved_rejections": resolved_ids,
        }


async def draft_for_review(conn: AsyncConnection, review_id: str) -> dict[str, Any]:
    """Return a review draft without ever presenting a pending one as approved."""
    body, revision = await _current(conn, review_id)
    pending = await _pending(conn, review_id)
    if pending:
        return {
            "status": "pending",
            "body": None,
            "pending_body": body,
            "revision": revision,
            "pending_conflicts": len(pending),
        }
    return {
        "status": "approved" if body else "absent",
        "body": body,
        "revision": revision,
        "pending_conflicts": 0,
    }


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="show pending draft conflicts")
    listing.add_argument("--workspace-id", required=True)
    listing.add_argument("--review-id")
    decide = sub.add_parser("resolve", help="record a decision for one review")
    decide.add_argument("--workspace-id", required=True)
    decide.add_argument("--review-id", required=True)
    decide.add_argument("--decision", choices=DECISIONS, required=True)
    decide.add_argument("--actor", required=True)
    decide.add_argument("--expected-revision", type=int, required=True)
    decide.add_argument("--rejection-id")
    decide.add_argument("--note")
    args = parser.parse_args(argv)

    async def run() -> dict[str, Any]:
        engine = create_async_engine(database_url(), pool_pre_ping=True)
        try:
            if args.command == "list":
                return await list_pending(engine, args.workspace_id, args.review_id)
            return await resolve(
                engine,
                args.workspace_id,
                args.review_id,
                args.decision,
                args.actor,
                args.expected_revision,
                args.rejection_id,
                args.note,
            )
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(run())
    except (ResolutionError, StaleDecisionError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
