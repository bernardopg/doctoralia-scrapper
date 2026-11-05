"""Record auditable resolutions of imported draft conflicts."""

from typing import Any, Optional

import sqlalchemy as sa
from alembic import op

revision = "0006_draft_resolution"
down_revision = "0005_repair_draft_provenance"
branch_labels = None
depends_on = None


def _review_for(connection: Any, row: Any) -> Optional[str]:
    """Link a draft rejection to its review only through stable identifiers."""
    payload = row.payload if isinstance(row.payload, dict) else {}
    direct = payload.get("review_id")
    if isinstance(direct, str):
        found = connection.execute(
            sa.text("SELECT id FROM reviews WHERE id=:id"), {"id": direct}
        ).scalar_one_or_none()
        if found is not None:
            return str(found)
    source = payload.get("id")
    if not isinstance(source, str):
        return None
    found = connection.execute(
        sa.text(
            "SELECT r.id FROM snapshot_reconciliations o "
            "JOIN scrape_runs s ON s.id = o.run_id "
            "JOIN reviews r ON r.profile_id = s.profile_id AND r.source_id = :source "
            "WHERE o.snapshot_id = :snapshot"
        ),
        {"source": source, "snapshot": row.snapshot_id},
    ).scalar_one_or_none()
    return None if found is None else str(found)


def upgrade() -> None:
    op.create_table(
        "draft_resolutions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "review_id",
            sa.String(36),
            sa.ForeignKey("reviews.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column(
            "chosen_rejection_id",
            sa.String(36),
            sa.ForeignKey("snapshot_rejections.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("previous_body", sa.Text, nullable=True),
        sa.Column("resolved_body", sa.Text, nullable=True),
        sa.Column("expected_revision", sa.Integer, nullable=False),
        sa.Column("resulting_revision", sa.Integer, nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("resolved_rejection_ids", sa.JSON, nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('keep', 'choose', 'clear')",
            name="ck_draft_resolutions_decision",
        ),
        sa.CheckConstraint(
            "(decision = 'choose') = (chosen_rejection_id IS NOT NULL)",
            name="ck_draft_resolutions_choice",
        ),
        sa.CheckConstraint(
            "resulting_revision = expected_revision + 1",
            name="ck_draft_resolutions_revision",
        ),
        sa.CheckConstraint(
            "length(trim(actor)) > 0", name="ck_draft_resolutions_actor"
        ),
    )
    op.create_index(
        "ix_draft_resolutions_review_decided_at",
        "draft_resolutions",
        ["review_id", "decided_at"],
    )
    # Batch mode keeps the migration portable to SQLite, which cannot add
    # foreign keys with ALTER TABLE.
    with op.batch_alter_table("snapshot_rejections") as batch:
        batch.add_column(sa.Column("review_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("resolution_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_snapshot_rejections_review_id",
            "reviews",
            ["review_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_snapshot_rejections_resolution_id",
            "draft_resolutions",
            ["resolution_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_snapshot_rejections_review_pending", ["review_id", "resolution_id"]
        )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, snapshot_id, payload FROM snapshot_rejections "
            "WHERE kind = 'draft' AND review_id IS NULL"
        )
    ).all()
    for row in rows:
        review_id = _review_for(connection, row)
        if review_id is not None:
            connection.execute(
                sa.text(
                    "UPDATE snapshot_rejections SET review_id=:review WHERE id=:id"
                ),
                {"review": review_id, "id": row.id},
            )

    if connection.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION draft_resolutions_append_only() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'draft_resolutions is append-only'; END $$"
        )
        op.execute(
            "CREATE TRIGGER draft_resolutions_append_only "
            "BEFORE UPDATE OR DELETE ON draft_resolutions "
            "FOR EACH ROW EXECUTE FUNCTION draft_resolutions_append_only()"
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS draft_resolutions_append_only ON draft_resolutions"
        )
        op.execute("DROP FUNCTION IF EXISTS draft_resolutions_append_only()")
    with op.batch_alter_table("snapshot_rejections") as batch:
        batch.drop_index("ix_snapshot_rejections_review_pending")
        batch.drop_constraint(
            "fk_snapshot_rejections_resolution_id", type_="foreignkey"
        )
        batch.drop_constraint("fk_snapshot_rejections_review_id", type_="foreignkey")
        batch.drop_column("resolution_id")
        batch.drop_column("review_id")
    op.drop_index(
        "ix_draft_resolutions_review_decided_at", table_name="draft_resolutions"
    )
    op.drop_table("draft_resolutions")
