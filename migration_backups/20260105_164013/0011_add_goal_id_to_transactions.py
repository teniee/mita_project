"""add goal_id to transactions for goal integration

Revision ID: 0011_add_goal_id
Revises: 0010_enhance_goals
Create Date: 2025-10-23

MODULE 5: Budgeting Goals - Transaction Integration
Links transactions to goals for automatic progress tracking
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011_add_goal_id"
down_revision = "0010_enhance_goals"
branch_labels = None
depends_on = None


def upgrade():
    """Add goal_id foreign key to transactions table"""

    # Add goal_id column
    op.add_column(
        "transactions",
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Create foreign key constraint
    op.create_foreign_key(
        "fk_transactions_goal_id",
        "transactions",
        "goals",
        ["goal_id"],
        ["id"],
        ondelete="SET NULL"  # If goal is deleted, don't delete transactions
    )

    # Create index for faster goal-based queries
    op.create_index(
        "ix_transactions_goal_id",
        "transactions",
        ["goal_id"],
        unique=False
    )


def downgrade():
    """Remove goal_id from transactions table"""

    # Drop index
    op.drop_index("ix_transactions_goal_id", table_name="transactions")

    # Drop foreign key
    op.drop_constraint("fk_transactions_goal_id", "transactions", type_="foreignkey")

    # Drop column
    op.drop_column("transactions", "goal_id")
