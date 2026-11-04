"""Preserve original snapshots as an idempotent import staging area."""

import sqlalchemy as sa
from alembic import op

revision = "0002_snapshot_staging"
down_revision = "0001_review_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "snapshot_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("original_bytes", sa.LargeBinary, nullable=False),
        sa.Column("issue_summary", sa.Text, nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workspace_id", "sha256", name="uq_snapshot_imports_workspace_sha256"
        ),
    )


def downgrade() -> None:
    op.drop_table("snapshot_imports")
