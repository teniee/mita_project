"""Add has_onboarded field to users table for onboarding completion tracking

Revision ID: add_has_onboarded
Revises: add_token_version
Create Date: 2025-10-21 12:00:00.000000

This migration adds a has_onboarded field to the users table to properly track
whether a user has completed the onboarding process.
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    """Add has_onboarded column to users table"""
    # Add has_onboarded column with default value of False
    op.add_column('users', sa.Column('has_onboarded', sa.Boolean(), nullable=False, server_default='false'))

    # Update existing users who have monthly_income set to be marked as onboarded
    # This handles users who completed onboarding before this migration
    op.execute('UPDATE users SET has_onboarded = true WHERE monthly_income > 0')


def downgrade():
    """Remove has_onboarded column from users table"""
    op.drop_column('users', 'has_onboarded')
