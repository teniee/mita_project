"""add notifications table

Revision ID: 0014_add_notifications_table
Revises: 0013_add_analytics_tables
Create Date: 2025-10-27 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0014_add_notifications_table"
down_revision = "0013_add_analytics_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Content
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False, server_default="info"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        # Rich content
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("action_url", sa.String(length=500), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        # Delivery tracking
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("channel", sa.String(length=20), nullable=True),
        # Read tracking
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        # Scheduling
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        # Error tracking
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.String(), nullable=False, server_default="0"),
        # Metadata
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # Grouping
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("group_key", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        op.f("ix_notifications_user_id"),
        "notifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_is_read"),
        "notifications",
        ["is_read"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_scheduled_for"),
        "notifications",
        ["scheduled_for"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_created_at"),
        "notifications",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_group_key"),
        "notifications",
        ["group_key"],
        unique=False,
    )
    # Composite index for common query pattern: user's unread notifications
    op.create_index(
        "ix_notifications_user_id_is_read_created_at",
        "notifications",
        ["user_id", "is_read", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_notifications_user_id_is_read_created_at", table_name="notifications")
    op.drop_index(op.f("ix_notifications_group_key"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_scheduled_for"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_is_read"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")

    # Drop table
    op.drop_table("notifications")
