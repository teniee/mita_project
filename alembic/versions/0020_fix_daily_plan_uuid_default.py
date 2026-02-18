"""fix daily_plan uuid default

Revision ID: 0020_fix_daily_plan_uuid_default
Revises: 0019_add_missing_user_fields
Create Date: 2025-12-24 15:45:00.000000

CRITICAL FIX: Adds database-level UUID default to daily_plan.id column
to fix calendar save failures during onboarding.

Issue: Calendar entries were not being saved because the id column had:
- is_nullable: NO (requires value)
- column_default: null (no default value)

This caused INSERT failures with "null value in column 'id' violates not-null constraint"
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0020_fix_daily_plan_uuid_default'
down_revision = '0019_add_missing_user_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add UUID default to daily_plan.id column"""
    # Add gen_random_uuid() as default for id column
    op.execute("""
        ALTER TABLE daily_plan
        ALTER COLUMN id SET DEFAULT gen_random_uuid();
    """)

    # Also ensure created_at has a default if missing
    op.execute("""
        ALTER TABLE daily_plan
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;
    """)


def downgrade():
    """Remove UUID default from daily_plan.id column"""
    op.execute("""
        ALTER TABLE daily_plan
        ALTER COLUMN id DROP DEFAULT;
    """)

    op.execute("""
        ALTER TABLE daily_plan
        ALTER COLUMN created_at DROP DEFAULT;
    """)
