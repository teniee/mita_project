"""Add user profile fields to users table

Revision ID: 0008_add_user_profile_fields
Revises: f8e0108e3527
Create Date: 2025-10-22 20:00:00.000000

This migration adds comprehensive user profile fields including:
- name: User's full name
- savings_goal: Monthly savings target
- budget_method: Budgeting methodology (e.g., 50/30/20 Rule)
- currency: User's preferred currency (e.g., USD, EUR)
- region: User's region/location
- notifications_enabled: Push notifications preference
- dark_mode_enabled: Dark mode UI preference
- monthly_income: Monthly income tracking
- has_onboarded: Onboarding completion status
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '0008_add_user_profile_fields'
down_revision = 'f8e0108e3527'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user profile and preference columns to users table"""

    # Add profile fields (guarded to avoid duplicate-column errors on pre-patched DBs)
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS name VARCHAR,
            ADD COLUMN IF NOT EXISTS savings_goal NUMERIC NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS budget_method VARCHAR NOT NULL DEFAULT '50/30/20 Rule',
            ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'USD',
            ADD COLUMN IF NOT EXISTS region VARCHAR;
    """)

    # Add preference fields with IF NOT EXISTS safeguards
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT true,
            ADD COLUMN IF NOT EXISTS dark_mode_enabled BOOLEAN NOT NULL DEFAULT false;
    """)

    # Add monthly income field (if not already present)
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS monthly_income NUMERIC DEFAULT 0;
    """)

    # Add has_onboarded field (if not already present)
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS has_onboarded BOOLEAN NOT NULL DEFAULT false;
    """)

    # Create indexes for commonly queried fields
    op.create_index('idx_users_currency', 'users', ['currency'])
    op.create_index('idx_users_region', 'users', ['region'])
    op.create_index('idx_users_has_onboarded', 'users', ['has_onboarded'])


def downgrade() -> None:
    """Remove user profile and preference columns from users table"""

    # Drop indexes
    op.drop_index('idx_users_has_onboarded', table_name='users')
    op.drop_index('idx_users_region', table_name='users')
    op.drop_index('idx_users_currency', table_name='users')

    # Drop preference fields
    op.drop_column('users', 'dark_mode_enabled')
    op.drop_column('users', 'notifications_enabled')

    # Drop profile fields
    op.drop_column('users', 'region')
    op.drop_column('users', 'currency')
    op.drop_column('users', 'budget_method')
    op.drop_column('users', 'savings_goal')
    op.drop_column('users', 'name')

    # Note: We don't drop monthly_income and has_onboarded as they may be used elsewhere
    # and were conditionally added in upgrade()
