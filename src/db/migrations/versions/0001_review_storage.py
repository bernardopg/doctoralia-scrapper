"""Create review storage alongside existing user and workspace tables.

Revision ID: 0001_review_storage
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_review_storage"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workspace_id", "source_url", name="uq_profiles_workspace_url"
        ),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "profile_id",
            sa.String(36),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("identity_status", sa.String(20), nullable=False),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("reviewed_at", sa.Date, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("doctor_reply", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "profile_id", "source_id", name="uq_reviews_profile_source"
        ),
        sa.UniqueConstraint("id", "profile_id", name="uq_reviews_id_profile"),
        sa.CheckConstraint(
            "identity_status IN ('source', 'fingerprint', 'ambiguous')",
            name="ck_reviews_identity_status",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_reviews_rating"
        ),
    )
    op.create_index(
        "ix_reviews_profile_reviewed_at", "reviews", ["profile_id", "reviewed_at"]
    )
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "profile_id",
            sa.String(36),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_count", sa.Integer, nullable=True),
        sa.Column("extracted_count", sa.Integer, nullable=True),
        sa.Column("stop_reason", sa.String(100), nullable=True),
        sa.UniqueConstraint("id", "profile_id", name="uq_scrape_runs_id_profile"),
        sa.CheckConstraint(
            "status IN ('running', 'complete', 'partial', 'unknown', 'failed')",
            name="ck_scrape_runs_status",
        ),
        sa.CheckConstraint(
            "expected_count IS NULL OR expected_count >= 0",
            name="ck_scrape_runs_expected",
        ),
        sa.CheckConstraint(
            "extracted_count IS NULL OR extracted_count >= 0",
            name="ck_scrape_runs_extracted",
        ),
    )
    op.create_index(
        "ix_scrape_runs_profile_started_at", "scrape_runs", ["profile_id", "started_at"]
    )
    op.create_table(
        "review_observations",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id", "profile_id"],
            ["scrape_runs.id", "scrape_runs.profile_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "profile_id"],
            ["reviews.id", "reviews.profile_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "review_drafts",
        sa.Column(
            "review_id",
            sa.String(36),
            sa.ForeignKey("reviews.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.CheckConstraint("revision >= 1", name="ck_review_drafts_revision"),
    )


def downgrade() -> None:
    op.drop_table("review_drafts")
    op.drop_table("review_observations")
    op.drop_index("ix_scrape_runs_profile_started_at", table_name="scrape_runs")
    op.drop_table("scrape_runs")
    op.drop_index("ix_reviews_profile_reviewed_at", table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("profiles")
