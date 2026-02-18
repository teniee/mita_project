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
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0008_add_user_profile_fields'
down_revision = 'f8e0108e3527'
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    # Add monthly income field (if not already present)
    # Note: This field may already exist in some deployments, so we use a conditional approach
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='monthly_income'
            ) THEN
                ALTER TABLE users ADD COLUMN monthly_income NUMERIC DEFAULT 0;
            END IF;
        END $$;
    """)

    # Add has_onboarded field (if not already present)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='has_onboarded'
            ) THEN
                ALTER TABLE users ADD COLUMN has_onboarded BOOLEAN NOT NULL DEFAULT false;
            END IF;
        END $$;
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
