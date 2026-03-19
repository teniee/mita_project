"""add goal_id to daily_plan

Problem 4 fix: goals were not connected to the daily budget.
This column lets the sync engine create per-goal SACRED rows in DailyPlan
and update / remove them when the goal changes.

ON DELETE SET NULL is a safety net — application-level code removes
future rows before a goal is soft-deleted.

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'daily_plan',
        sa.Column(
            'goal_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('goals.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    # Fast lookup: "give me all DailyPlan rows for goal X"
    op.create_index('ix_daily_plan_goal_id', 'daily_plan', ['goal_id'])
    # Fast lookup: "give me goal rows for user X in date range" (main query pattern)
    op.create_index(
        'ix_daily_plan_user_goal_date',
        'daily_plan',
        ['user_id', 'goal_id', 'date'],
    )


def downgrade() -> None:
    op.drop_index('ix_daily_plan_user_goal_date', table_name='daily_plan')
    op.drop_index('ix_daily_plan_goal_id',        table_name='daily_plan')
    op.drop_column('daily_plan', 'goal_id')
