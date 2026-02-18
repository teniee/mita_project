"""Add account security fields for lockout mechanism

Revision ID: 0017_add_account_security_fields
Revises: f8e0108e3527
Create Date: 2025-11-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0017_add_account_security_fields'
down_revision = 'f8e0108e3527'
branch_labels = None
depends_on = None


def upgrade():
    """Add account security fields to users table"""
    # Add failed_login_attempts column
    op.add_column('users',
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0')
    )

    # Add account_locked_until column
    op.add_column('users',
        sa.Column('account_locked_until', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    """Remove account security fields from users table"""
    op.drop_column('users', 'account_locked_until')
    op.drop_column('users', 'failed_login_attempts')
