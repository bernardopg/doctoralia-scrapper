"""Rebuild draft provenance and expose unresolved legacy observations."""

import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0005_repair_draft_provenance"
down_revision = "0004_snapshot_draft_state"
branch_labels = None
depends_on = None


def _tables():
    definitions: dict[str, dict[str, Any]] = {
        "profiles": {"id": sa.String, "workspace_id": sa.String},
        "reviews": {"id": sa.String, "profile_id": sa.String, "source_id": sa.String},
        "scrape_runs": {"id": sa.String, "started_at": sa.DateTime(timezone=True)},
        "review_observations": {
            "review_id": sa.String,
            "run_id": sa.String,
            "payload": sa.JSON,
        },
        "review_drafts": {"review_id": sa.String, "body": sa.Text},
        "snapshot_imports": {"id": sa.String, "original_bytes": sa.LargeBinary},
        "snapshot_reconciliations": {
            "snapshot_id": sa.String,
            "run_id": sa.String,
            "report": sa.JSON,
        },
        "snapshot_rejections": {
            "id": sa.String,
            "snapshot_id": sa.String,
            "item_index": sa.Integer,
            "kind": sa.String,
            "reason": sa.Text,
            "payload": sa.JSON,
        },
        "snapshot_draft_state": {
            "review_id": sa.String,
            "snapshot_id": sa.String,
            "observed_at": sa.DateTime(timezone=True),
            "body": sa.Text,
        },
    }
    return {
        name: sa.table(name, *(sa.column(key, kind) for key, kind in columns.items()))
        for name, columns in definitions.items()
    }


def _uncertain_time(raw):
    try:
        snapshot = json.loads(raw)
        value = snapshot.get("extraction_timestamp") or snapshot.get("scraped_at")
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return timestamp.tzinfo is None or timestamp.utcoffset() is None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return True


def _matches_original(raw, source_id, payload):
    """An observation is trustworthy only when the staged item agrees exactly."""
    try:
        snapshot = json.loads(raw)
        items = snapshot.get("reviews")
        if not isinstance(items, list):
            return False
        matches = [
            item
            for item in items
            if isinstance(item, dict) and item.get("id") == source_id
        ]
        return len(matches) == 1 and matches[0] == payload
    except (ValueError, TypeError, AttributeError):
        return False


def _repair_workspace(connection, tables, workspace_id):
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:w, 0))"),
            {"w": workspace_id},
        )
    profiles = tables["profiles"]
    reviews = tables["reviews"]
    runs = tables["scrape_runs"]
    observations = tables["review_observations"]
    drafts = tables["review_drafts"]
    imports = tables["snapshot_imports"]
    outcomes = tables["snapshot_reconciliations"]
    rejections = tables["snapshot_rejections"]
    states = tables["snapshot_draft_state"]
    source = (
        observations.join(reviews, reviews.c.id == observations.c.review_id)
        .join(profiles, profiles.c.id == reviews.c.profile_id)
        .join(runs, runs.c.id == observations.c.run_id)
        .join(outcomes, outcomes.c.run_id == runs.c.id)
        .join(imports, imports.c.id == outcomes.c.snapshot_id)
    )
    rows = connection.execute(
        sa.select(
            reviews.c.id.label("review_id"),
            reviews.c.source_id,
            outcomes.c.snapshot_id,
            observations.c.payload,
            runs.c.started_at.label("observed_at"),
            imports.c.original_bytes,
        )
        .select_from(source)
        .where(profiles.c.workspace_id == workspace_id)
    ).mappings()
    histories = defaultdict(list)
    for row in rows:
        histories[row["review_id"]].append(row)
    for review_id, history in histories.items():
        latest = max(history, key=lambda row: (row["observed_at"], row["snapshot_id"]))
        values = []
        invalid = False
        for row in history:
            payload = row["payload"]
            if not isinstance(payload, dict) or payload.get("id") != row["source_id"]:
                invalid = True
            if not _matches_original(row["original_bytes"], row["source_id"], payload):
                invalid = True
            body = (
                payload.get("generated_response") if isinstance(payload, dict) else None
            )
            if body is not None and not isinstance(body, str):
                invalid = True
                body = None
            values.append(body or None)
        latest_values = {
            values[index]
            for index, row in enumerate(history)
            if row["observed_at"] == latest["observed_at"]
        }
        latest_body = next(iter(latest_values)) if len(latest_values) == 1 else None
        existing_state = connection.execute(
            sa.select(states.c.review_id).where(states.c.review_id == review_id)
        ).scalar_one_or_none()
        if existing_state is None:
            connection.execute(
                sa.insert(states).values(
                    review_id=review_id,
                    snapshot_id=latest["snapshot_id"],
                    observed_at=latest["observed_at"],
                    body=latest_body,
                )
            )
        active = connection.execute(
            sa.select(drafts.c.body).where(drafts.c.review_id == review_id)
        ).scalar_one_or_none()
        uncertain = any(_uncertain_time(row["original_bytes"]) for row in history)
        if not (invalid or uncertain or len(set(values)) > 1 or active != latest_body):
            continue
        snapshots = {row["snapshot_id"] for row in history}
        prior = connection.execute(
            sa.select(rejections.c.payload).where(
                rejections.c.snapshot_id.in_(snapshots), rejections.c.kind == "draft"
            )
        ).scalars()
        if any(
            isinstance(payload, dict)
            and (
                payload.get("review_id") == review_id
                or (
                    latest["source_id"] is not None
                    and payload.get("id") == latest["source_id"]
                )
            )
            for payload in prior
        ):
            continue
        repair_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, "doctoralia:legacy-draft:" + review_id)
        )
        # A deterministic marker also protects downgrade/re-upgrade retries.
        if connection.execute(
            sa.select(rejections.c.id).where(rejections.c.id == repair_id)
        ).scalar_one_or_none():
            continue
        connection.execute(
            sa.insert(rejections).values(
                id=repair_id,
                snapshot_id=latest["snapshot_id"],
                item_index=None,
                kind="draft",
                reason="legacy draft provenance requires review",
                payload={
                    "review_id": review_id,
                    "source_id": latest["source_id"],
                    "observation_count": len(history),
                    "latest_observed_at": latest["observed_at"].isoformat(),
                    "time_uncertain": uncertain,
                    "observation_integrity_uncertain": invalid,
                    "requires_human_resolution": True,
                },
            )
        )
        report = dict(
            connection.execute(
                sa.select(outcomes.c.report).where(
                    outcomes.c.snapshot_id == latest["snapshot_id"]
                )
            ).scalar_one()
        )
        report["pending"] = report.get("pending", 0) + 1
        connection.execute(
            sa.update(outcomes)
            .where(outcomes.c.snapshot_id == latest["snapshot_id"])
            .values(report=report)
        )


def upgrade() -> None:
    connection = op.get_bind()
    tables = _tables()
    workspaces = (
        connection.execute(
            sa.select(tables["profiles"].c.workspace_id)
            .distinct()
            .order_by(tables["profiles"].c.workspace_id)
        )
        .scalars()
        .all()
    )
    for workspace_id in workspaces:
        _repair_workspace(connection, tables, workspace_id)


def downgrade() -> None:
    # Repair audit records and pending counts must survive a schema downgrade.
    # Restoring the pre-repair data requires the verified database backup.
    pass
