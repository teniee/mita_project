"""Add soft delete support for financial data compliance

Revision ID: 0018_add_soft_deletes
Revises: 0017_add_account_security_fields
Create Date: 2025-11-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0018_add_soft_deletes'
down_revision = '0017_add_account_security_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add deleted_at column to financial data tables for compliance"""

    # Add deleted_at column to transactions table
    op.add_column('transactions',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add deleted_at column to goals table
    op.add_column('goals',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add deleted_at column to installments table
    op.add_column('installments',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Create partial indexes for performance (index only non-deleted records)
    # PostgreSQL partial indexes are faster for filtering WHERE deleted_at IS NULL
    op.create_index(
        'idx_transactions_deleted_at',
        'transactions',
        ['deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    op.create_index(
        'idx_goals_deleted_at',
        'goals',
        ['deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL')
    )

    op.create_index(
        'idx_installments_deleted_at',
        'installments',
        ['deleted_at'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL')
    )


def downgrade():
    """Remove soft delete support - WARNING: This will make data deletions permanent again"""

    # Drop indexes first
    op.drop_index('idx_installments_deleted_at', table_name='installments')
    op.drop_index('idx_goals_deleted_at', table_name='goals')
    op.drop_index('idx_transactions_deleted_at', table_name='transactions')

    # Drop columns
    op.drop_column('installments', 'deleted_at')
    op.drop_column('goals', 'deleted_at')
    op.drop_column('transactions', 'deleted_at')
