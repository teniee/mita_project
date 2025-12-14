"""add analytics tables

Revision ID: 0013_add_analytics_tables
Revises: 0012_add_challenges
Create Date: 2025-10-24 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0013_add_analytics_tables"
down_revision = "0012_add_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create feature_usage_logs table
    op.create_table(
        "feature_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature", sa.String(length=100), nullable=False),
        sa.Column("screen", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("app_version", sa.String(length=20), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_feature_usage_logs_user_id"),
        "feature_usage_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feature_usage_logs_feature"),
        "feature_usage_logs",
        ["feature"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feature_usage_logs_screen"),
        "feature_usage_logs",
        ["screen"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feature_usage_logs_session_id"),
        "feature_usage_logs",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feature_usage_logs_timestamp"),
        "feature_usage_logs",
        ["timestamp"],
        unique=False,
    )

    # Create feature_access_logs table
    op.create_table(
        "feature_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature", sa.String(length=100), nullable=False),
        sa.Column("has_access", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_premium_feature", sa.Boolean(), nullable=False, default=False),
        sa.Column("converted_to_premium", sa.Boolean(), nullable=True, default=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("screen", sa.String(length=100), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_feature_access_logs_user_id"),
        "feature_access_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feature_access_logs_feature"),
        "feature_access_logs",
        ["feature"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feature_access_logs_timestamp"),
        "feature_access_logs",
        ["timestamp"],
        unique=False,
    )

    # Create paywall_impression_logs table
    op.create_table(
        "paywall_impression_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("screen", sa.String(length=100), nullable=False),
        sa.Column("feature", sa.String(length=100), nullable=True),
        sa.Column("resulted_in_purchase", sa.Boolean(), nullable=True, default=False),
        sa.Column("purchase_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("impression_context", sa.String(length=200), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_paywall_impression_logs_user_id"),
        "paywall_impression_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_paywall_impression_logs_screen"),
        "paywall_impression_logs",
        ["screen"],
        unique=False,
    )
    op.create_index(
        op.f("ix_paywall_impression_logs_timestamp"),
        "paywall_impression_logs",
        ["timestamp"],
        unique=False,
    )


def downgrade() -> None:
    # Drop paywall_impression_logs table
    op.drop_index(
        op.f("ix_paywall_impression_logs_timestamp"),
        table_name="paywall_impression_logs",
    )
    op.drop_index(
        op.f("ix_paywall_impression_logs_screen"), table_name="paywall_impression_logs"
    )
    op.drop_index(
        op.f("ix_paywall_impression_logs_user_id"), table_name="paywall_impression_logs"
    )
    op.drop_table("paywall_impression_logs")

    # Drop feature_access_logs table
    op.drop_index(
        op.f("ix_feature_access_logs_timestamp"), table_name="feature_access_logs"
    )
    op.drop_index(
        op.f("ix_feature_access_logs_feature"), table_name="feature_access_logs"
    )
    op.drop_index(
        op.f("ix_feature_access_logs_user_id"), table_name="feature_access_logs"
    )
    op.drop_table("feature_access_logs")

    # Drop feature_usage_logs table
    op.drop_index(
        op.f("ix_feature_usage_logs_timestamp"), table_name="feature_usage_logs"
    )
    op.drop_index(
        op.f("ix_feature_usage_logs_session_id"), table_name="feature_usage_logs"
    )
    op.drop_index(op.f("ix_feature_usage_logs_screen"), table_name="feature_usage_logs")
    op.drop_index(
        op.f("ix_feature_usage_logs_feature"), table_name="feature_usage_logs"
    )
    op.drop_index(
        op.f("ix_feature_usage_logs_user_id"), table_name="feature_usage_logs"
    )
    op.drop_table("feature_usage_logs")
