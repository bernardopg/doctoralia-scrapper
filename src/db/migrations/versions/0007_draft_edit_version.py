"""Track the draft edit version last accepted from published snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0007_draft_edit_version"
down_revision = "0006_draft_resolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Published snapshots carry ``draft_edit.version``, incremented by every
    # dashboard edit and requested generation. A higher version than the one
    # recorded here is an intentional edit, not a conflicting observation.
    with op.batch_alter_table("snapshot_draft_state") as batch:
        batch.add_column(
            sa.Column("edit_version", sa.Integer, nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("snapshot_draft_state") as batch:
        batch.drop_column("edit_version")
