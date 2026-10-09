"""Persist real last-seen time without changing existing data."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("last_seen_at")
