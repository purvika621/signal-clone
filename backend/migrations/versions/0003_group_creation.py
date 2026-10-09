"""Persist idempotent group creation intents without changing existing records."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("group_creations",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("client_group_id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False, unique=True),
        sa.Column("fingerprint", sa.String(64), nullable=False))

def downgrade():
    op.drop_table("group_creations")
