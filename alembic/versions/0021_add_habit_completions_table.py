"""add habit_completions table

Revision ID: 0021_add_habit_completions
Revises: 0020_fix_daily_plan_uuid_default
Create Date: 2026-01-05 02:00:00.000000

CRITICAL FIX: Creates the habit_completions table that was missing from database.

Issue: The HabitCompletion model was added to app/db/models/habit.py but the
corresponding database migration was never created. This caused the Habits API
to fail with "relation 'habit_completions' does not exist" errors.

This migration creates the table with proper foreign keys, indexes, and UUID defaults.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '0021_add_habit_completions'
down_revision = '0020_fix_daily_plan_uuid_default'
branch_labels = None
depends_on = None


def upgrade():
    """Create habit_completions table"""
    op.create_table(
        'habit_completions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('habit_id', UUID(as_uuid=True), sa.ForeignKey('habits.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create indexes for performance
    op.create_index('ix_habit_completions_habit_id', 'habit_completions', ['habit_id'])
    op.create_index('ix_habit_completions_user_id', 'habit_completions', ['user_id'])
    op.create_index('ix_habit_completions_completed_at', 'habit_completions', ['completed_at'])

    # Composite index for common queries (user habits completed on specific dates)
    op.create_index('ix_habit_completions_user_date', 'habit_completions', ['user_id', 'completed_at'])


def downgrade():
    """Drop habit_completions table"""
    op.drop_index('ix_habit_completions_user_date', table_name='habit_completions')
    op.drop_index('ix_habit_completions_completed_at', table_name='habit_completions')
    op.drop_index('ix_habit_completions_user_id', table_name='habit_completions')
    op.drop_index('ix_habit_completions_habit_id', table_name='habit_completions')
    op.drop_table('habit_completions')
