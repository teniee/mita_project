"""Add user profile fields to users table for complete profile management

Revision ID: add_user_profile_fields
Revises: add_has_onboarded
Create Date: 2025-10-22 12:00:00.000000

This migration adds comprehensive user profile fields including:
- name: User's full name
- savings_goal: Monthly savings target
- budget_method: Budgeting methodology (e.g., 50/30/20 Rule)
- currency: User's preferred currency (e.g., USD, EUR)
- region: User's region/location
- notifications_enabled: Push notifications preference
- dark_mode_enabled: Dark mode UI preference
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    """Add user profile and preference columns to users table"""

    # Add profile fields
    op.add_column('users', sa.Column('name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('savings_goal', sa.Numeric(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('budget_method', sa.String(), nullable=False, server_default='50/30/20 Rule'))
    op.add_column('users', sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'))
    op.add_column('users', sa.Column('region', sa.String(), nullable=True))

    # Add preference fields
    op.add_column('users', sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('dark_mode_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    """Remove user profile and preference columns from users table"""

    # Remove preference fields
    op.drop_column('users', 'dark_mode_enabled')
    op.drop_column('users', 'notifications_enabled')

    # Remove profile fields
    op.drop_column('users', 'region')
    op.drop_column('users', 'currency')
    op.drop_column('users', 'budget_method')
    op.drop_column('users', 'savings_goal')
    op.drop_column('users', 'name')
