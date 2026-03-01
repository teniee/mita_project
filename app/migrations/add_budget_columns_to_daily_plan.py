"""Add budget tracking columns to daily_plan table

Revision ID: add_budget_columns_to_daily_plan
Revises: add_token_version
Create Date: 2025-10-21 15:30:00.000000

This migration adds normalized budget tracking columns to the daily_plan table
to support efficient querying and aggregation of budget data. The plan_json
column is retained for backward compatibility and additional metadata.
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    """Add budget tracking columns to daily_plan table"""

    # Add category column with index for fast category-based queries
    op.add_column('daily_plan', sa.Column('category', sa.String(100), nullable=True))
    op.create_index('idx_daily_plan_category', 'daily_plan', ['category'])

    # Add planned_amount column for budgeted amounts
    op.add_column('daily_plan', sa.Column('planned_amount', sa.Numeric(12, 2), nullable=True))

    # Add spent_amount column for actual spending
    op.add_column('daily_plan', sa.Column('spent_amount', sa.Numeric(12, 2), nullable=True))

    # Add daily_budget column for total daily budget limit
    op.add_column('daily_plan', sa.Column('daily_budget', sa.Numeric(12, 2), nullable=True))

    # Add status column for budget status tracking (green/yellow/red)
    op.add_column('daily_plan', sa.Column('status', sa.String(20), nullable=True))

    # Set default values for existing rows
    op.execute("UPDATE daily_plan SET planned_amount = 0.00 WHERE planned_amount IS NULL")
    op.execute("UPDATE daily_plan SET spent_amount = 0.00 WHERE spent_amount IS NULL")
    op.execute("UPDATE daily_plan SET status = 'green' WHERE status IS NULL")

    # Make plan_json nullable for flexibility
    op.alter_column('daily_plan', 'plan_json', nullable=True)

    # Create composite index for common query patterns
    op.create_index('idx_daily_plan_user_date_category', 'daily_plan', ['user_id', 'date', 'category'])


def downgrade():
    """Remove budget tracking columns from daily_plan table"""

    # Drop composite index
    op.drop_index('idx_daily_plan_user_date_category', 'daily_plan')

    # Drop category index
    op.drop_index('idx_daily_plan_category', 'daily_plan')

    # Remove columns
    op.drop_column('daily_plan', 'category')
    op.drop_column('daily_plan', 'planned_amount')
    op.drop_column('daily_plan', 'spent_amount')
    op.drop_column('daily_plan', 'daily_budget')
    op.drop_column('daily_plan', 'status')

    # Restore plan_json to NOT NULL
    op.alter_column('daily_plan', 'plan_json', nullable=False)
