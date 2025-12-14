"""add challenges tables

Revision ID: 0012_add_challenges
Revises: 0011_add_goal_id_to_transactions
Create Date: 2025-10-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '0012_add_challenges'
down_revision = '0011_add_goal_id'
branch_labels = None
depends_on = None


def upgrade():
    """Create challenges and challenge_participations tables"""

    # Create challenges table
    op.create_table(
        'challenges',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),  # streak, category_restriction, category_reduction
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('reward_points', sa.Integer(), default=0),
        sa.Column('difficulty', sa.String(20), nullable=False),  # easy, medium, hard
        sa.Column('start_month', sa.String(7), nullable=False),  # "2025-01"
        sa.Column('end_month', sa.String(7), nullable=False),  # "2025-12"
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create challenge_participations table
    op.create_table(
        'challenge_participations',
        sa.Column('id', UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('challenge_id', sa.String(), nullable=False),
        sa.Column('month', sa.String(7), nullable=False),  # "2025-10"
        sa.Column('status', sa.String(20), default='active'),  # active, completed, failed, abandoned
        sa.Column('progress_percentage', sa.Integer(), default=0),
        sa.Column('days_completed', sa.Integer(), default=0),
        sa.Column('current_streak', sa.Integer(), default=0),
        sa.Column('best_streak', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE')
    )

    # Create indexes for better query performance
    op.create_index('ix_challenge_participations_user_id', 'challenge_participations', ['user_id'])
    op.create_index('ix_challenge_participations_challenge_id', 'challenge_participations', ['challenge_id'])
    op.create_index('ix_challenge_participations_month', 'challenge_participations', ['month'])
    op.create_index('ix_challenge_participations_status', 'challenge_participations', ['status'])

    # Insert sample challenges
    op.execute("""
        INSERT INTO challenges (id, name, description, type, duration_days, reward_points, difficulty, start_month, end_month)
        VALUES
        ('savings_streak_7', '7-Day Savings Streak', 'Save money every day for 7 consecutive days', 'streak', 7, 100, 'easy', '2025-01', '2025-12'),
        ('savings_streak_30', '30-Day Savings Challenge', 'Build a monthly savings habit by saving every day', 'streak', 30, 500, 'medium', '2025-01', '2025-12'),
        ('no_coffee_challenge', 'Skip the Coffee', 'Reduce coffee shop expenses for 14 days', 'category_restriction', 14, 200, 'medium', '2025-01', '2025-12'),
        ('dining_reduction', 'Cook at Home Challenge', 'Reduce dining out expenses by 50% this month', 'category_reduction', 30, 300, 'medium', '2025-01', '2025-12'),
        ('transportation_saver', 'Commute Smart', 'Save on transportation costs for 21 days', 'category_reduction', 21, 250, 'easy', '2025-01', '2025-12'),
        ('budget_master', 'Budget Master', 'Stay within budget for all categories for 30 days', 'streak', 30, 1000, 'hard', '2025-01', '2025-12'),
        ('impulse_free', 'Impulse-Free Zone', 'Avoid impulse purchases for 14 days', 'category_restriction', 14, 300, 'medium', '2025-01', '2025-12'),
        ('weekly_saver', 'Weekly Savings Goal', 'Save a specific amount every week for 4 weeks', 'streak', 28, 400, 'medium', '2025-01', '2025-12')
    """)


def downgrade():
    """Drop challenges tables"""

    # Drop indexes first
    op.drop_index('ix_challenge_participations_status', 'challenge_participations')
    op.drop_index('ix_challenge_participations_month', 'challenge_participations')
    op.drop_index('ix_challenge_participations_challenge_id', 'challenge_participations')
    op.drop_index('ix_challenge_participations_user_id', 'challenge_participations')

    # Drop tables
    op.drop_table('challenge_participations')
    op.drop_table('challenges')
