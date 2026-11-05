"""Track the newest draft observation for each review."""

import sqlalchemy as sa
from alembic import op

revision = "0004_snapshot_draft_state"
down_revision = "0003_snapshot_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snapshot_draft_state",
        sa.Column(
            "review_id",
            sa.String(36),
            sa.ForeignKey("reviews.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("snapshot_imports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("snapshot_draft_state")
