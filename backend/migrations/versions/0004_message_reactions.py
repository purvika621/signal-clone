"""Add reactions without replacing existing messages or data."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("reaction_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("message_reactions",
        sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("emoji", sa.String(8), primary_key=True),
        sa.CheckConstraint("emoji IN ('❤️', '😂', '👍', '😮', '😢', '🎉')", name="ck_reaction_emoji"))


def downgrade():
    op.drop_table("message_reactions")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("reaction_version")
