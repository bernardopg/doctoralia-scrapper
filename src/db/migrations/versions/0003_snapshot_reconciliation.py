"""Record reconciliation outcomes without altering staged originals."""

import sqlalchemy as sa
from alembic import op

revision = "0003_snapshot_reconciliation"
down_revision = "0002_snapshot_staging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snapshot_reconciliations",
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("snapshot_imports.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("scrape_runs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("report", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "snapshot_rejections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("snapshot_reconciliations.snapshot_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("item_index", sa.Integer, nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("snapshot_rejections")
    op.drop_table("snapshot_reconciliations")
