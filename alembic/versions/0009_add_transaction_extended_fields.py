"""add_transaction_extended_fields

Revision ID: 0009_add_transaction_extended_fields
Revises: f8e0108e3527
Create Date: 2025-10-22 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0009_add_transaction_extended_fields'
down_revision = '0008_add_user_profile_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add extended fields to transactions table"""

    # Add merchant column
    op.add_column('transactions', sa.Column('merchant', sa.String(200), nullable=True))

    # Add location column
    op.add_column('transactions', sa.Column('location', sa.String(200), nullable=True))

    # Add tags array column
    op.add_column('transactions', sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True))

    # Add is_recurring column
    op.add_column('transactions', sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'))

    # Add confidence_score column (for OCR-based transactions)
    op.add_column('transactions', sa.Column('confidence_score', sa.Float(), nullable=True))

    # Add receipt_url column
    op.add_column('transactions', sa.Column('receipt_url', sa.String(500), nullable=True))

    # Add notes column for extended information
    op.add_column('transactions', sa.Column('notes', sa.Text(), nullable=True))

    # Add updated_at column with auto-update trigger
    op.add_column('transactions', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

    # Create indexes for better query performance
    op.create_index('idx_transactions_merchant', 'transactions', ['merchant'])
    op.create_index('idx_transactions_is_recurring', 'transactions', ['is_recurring'])
    op.create_index('idx_transactions_updated_at', 'transactions', ['updated_at'])

    # Create trigger to automatically update updated_at column on row updates
    op.execute("""
        CREATE TRIGGER update_transactions_updated_at BEFORE UPDATE ON transactions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Remove added fields from transactions table"""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_transactions_updated_at ON transactions")

    # Drop indexes
    op.drop_index('idx_transactions_updated_at', 'transactions')
    op.drop_index('idx_transactions_is_recurring', 'transactions')
    op.drop_index('idx_transactions_merchant', 'transactions')

    # Drop columns
    op.drop_column('transactions', 'updated_at')
    op.drop_column('transactions', 'notes')
    op.drop_column('transactions', 'receipt_url')
    op.drop_column('transactions', 'confidence_score')
    op.drop_column('transactions', 'is_recurring')
    op.drop_column('transactions', 'tags')
    op.drop_column('transactions', 'location')
    op.drop_column('transactions', 'merchant')
