"""enhance goals table with full budgeting features

Revision ID: 0010_enhance_goals
Revises: 0009_add_transaction_extended_fields
Create Date: 2025-10-23

MODULE 5: Budgeting Goals - Enhanced Goal Tracking
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010_enhance_goals"
down_revision = "0009_add_transaction_extended_fields"
branch_labels = None
depends_on = None


def upgrade():
    """Add new fields to goals table for comprehensive goal tracking"""

    # Add description field
    op.add_column(
        "goals",
        sa.Column("description", sa.Text(), nullable=True)
    )

    # Add category field with index
    op.add_column(
        "goals",
        sa.Column("category", sa.String(50), nullable=True)
    )
    op.create_index(
        "ix_goals_category",
        "goals",
        ["category"],
        unique=False
    )

    # Add monthly_contribution field
    op.add_column(
        "goals",
        sa.Column("monthly_contribution", sa.Numeric(precision=10, scale=2), nullable=True)
    )

    # Add status field with index and default value
    op.add_column(
        "goals",
        sa.Column("status", sa.String(20), nullable=False, server_default="active")
    )
    op.create_index(
        "ix_goals_status",
        "goals",
        ["status"],
        unique=False
    )

    # Add progress field with default value
    op.add_column(
        "goals",
        sa.Column("progress", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0")
    )

    # Add target_date field
    op.add_column(
        "goals",
        sa.Column("target_date", sa.Date(), nullable=True)
    )

    # Add last_updated field with default
    op.add_column(
        "goals",
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.func.now())
    )

    # Add completed_at field
    op.add_column(
        "goals",
        sa.Column("completed_at", sa.DateTime(), nullable=True)
    )

    # Add priority field with default
    op.add_column(
        "goals",
        sa.Column("priority", sa.String(10), nullable=True, server_default="medium")
    )

    # Update precision for existing numeric fields
    op.alter_column(
        "goals",
        "target_amount",
        existing_type=sa.Numeric(),
        type_=sa.Numeric(precision=10, scale=2),
        nullable=False
    )

    op.alter_column(
        "goals",
        "saved_amount",
        existing_type=sa.Numeric(),
        type_=sa.Numeric(precision=10, scale=2),
        nullable=False,
        server_default="0"
    )

    # Update title with max length
    op.alter_column(
        "goals",
        "title",
        existing_type=sa.String(),
        type_=sa.String(200),
        nullable=False
    )


def downgrade():
    """Remove added fields from goals table"""

    # Drop indexes
    op.drop_index("ix_goals_status", table_name="goals")
    op.drop_index("ix_goals_category", table_name="goals")

    # Drop columns in reverse order
    op.drop_column("goals", "priority")
    op.drop_column("goals", "completed_at")
    op.drop_column("goals", "last_updated")
    op.drop_column("goals", "target_date")
    op.drop_column("goals", "progress")
    op.drop_column("goals", "status")
    op.drop_column("goals", "monthly_contribution")
    op.drop_column("goals", "category")
    op.drop_column("goals", "description")

    # Revert column types
    op.alter_column(
        "goals",
        "title",
        existing_type=sa.String(200),
        type_=sa.String(),
        nullable=False
    )

    op.alter_column(
        "goals",
        "saved_amount",
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(),
        nullable=False
    )

    op.alter_column(
        "goals",
        "target_amount",
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(),
        nullable=False
    )
