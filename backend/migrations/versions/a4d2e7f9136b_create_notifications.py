"""Create notifications.

Revision ID: a4d2e7f9136b
Revises: 8c6c2ab17d42
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a4d2e7f9136b"
down_revision: str | None = "8c6c2ab17d42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.String(5000), nullable=False),
        sa.Column("channel", sa.String(5), nullable=False),
        sa.CheckConstraint("channel IN ('email', 'sms', 'push')", name="ck_notifications_channel"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user_id_users"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
