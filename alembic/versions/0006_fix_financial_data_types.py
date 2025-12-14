"""fix critical financial data types for compliance

Revision ID: 0006_fix_financial_data_types
Revises: a0d5ecc53667
Create Date: 2025-08-11

CRITICAL: This migration fixes financial data integrity issues:
1. Converts Float to Numeric(precision=12, scale=2) for expenses.amount
2. Adds proper precision to existing Numeric columns
3. Adds foreign key constraints for data integrity
4. Ensures all monetary values use appropriate decimal precision

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_fix_financial_data_types"
down_revision = "0005_push_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Apply financial data type fixes with proper error handling
    """
    # Create backup of affected data before migration
    op.execute("CREATE TEMP TABLE expenses_backup AS SELECT * FROM expenses")
    
    # Fix expenses table - critical financial data type issue
    # Convert Float to Numeric for precise decimal handling
    op.alter_column(
        'expenses',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
        comment='Fixed: Float to Numeric(12,2) for financial precision'
    )
    
    # Fix user_id type inconsistency in expenses table
    op.alter_column(
        'expenses',
        'user_id',
        existing_type=sa.String(),
        type_=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using='user_id::uuid'
    )
    
    # Add missing foreign key constraints for data integrity
    with op.batch_alter_table('expenses') as batch_op:
        batch_op.create_foreign_key(
            'fk_expenses_user_id',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE'
        )
    
    # Fix goals table - ensure proper precision for target_amount and saved_amount
    op.alter_column(
        'goals',
        'target_amount',
        existing_type=sa.Numeric(),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
        comment='Added precision(12,2) for financial accuracy'
    )
    
    op.alter_column(
        'goals',
        'saved_amount',
        existing_type=sa.Numeric(),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
        comment='Added precision(12,2) for financial accuracy'
    )
    
    # Add foreign key constraint for goals table
    with op.batch_alter_table('goals') as batch_op:
        batch_op.create_foreign_key(
            'fk_goals_user_id',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE'
        )
    
    # Fix users table - ensure annual_income has proper precision
    op.alter_column(
        'users',
        'annual_income',
        existing_type=sa.Numeric(),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=True,
        comment='Added precision(12,2) for financial accuracy'
    )
    
    # Fix user_answers table - make user_id consistent with UUID type
    op.alter_column(
        'user_answers',
        'user_id',
        existing_type=sa.String(),
        type_=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using='user_id::uuid'
    )
    
    # Add foreign key constraint for user_answers table
    with op.batch_alter_table('user_answers') as batch_op:
        batch_op.create_foreign_key(
            'fk_user_answers_user_id',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE'
        )
    
    # Fix user_profiles table - make user_id consistent with UUID type
    op.alter_column(
        'user_profiles',
        'user_id',
        existing_type=sa.String(),
        type_=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using='user_id::uuid'
    )
    
    # Add foreign key constraint for user_profiles table
    with op.batch_alter_table('user_profiles') as batch_op:
        batch_op.create_foreign_key(
            'fk_user_profiles_user_id',
            'users',
            ['user_id'],
            ['id'],
            ondelete='CASCADE'
        )
    
    # Add critical indexes for financial queries
    op.create_index(
        'ix_expenses_user_id_date',
        'expenses',
        ['user_id', 'date'],
        unique=False
    )
    
    op.create_index(
        'ix_transactions_user_id_spent_at',
        'transactions',
        ['user_id', 'spent_at'],
        unique=False
    )
    
    # Validate data integrity after migration
    op.execute("""
        DO $$
        BEGIN
            -- Verify no data loss in expenses table
            IF (SELECT COUNT(*) FROM expenses) != (SELECT COUNT(*) FROM expenses_backup) THEN
                RAISE EXCEPTION 'Data loss detected in expenses migration';
            END IF;
            
            -- Verify no negative amounts in financial tables
            IF EXISTS (SELECT 1 FROM expenses WHERE amount < 0) THEN
                RAISE WARNING 'Negative amounts found in expenses table';
            END IF;
            
            IF EXISTS (SELECT 1 FROM transactions WHERE amount < 0) THEN
                RAISE WARNING 'Negative amounts found in transactions table';
            END IF;
            
            -- Verify foreign key constraints are working
            IF EXISTS (SELECT 1 FROM expenses e LEFT JOIN users u ON e.user_id = u.id WHERE u.id IS NULL) THEN
                RAISE EXCEPTION 'Orphaned records found in expenses table';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """
    Reverse financial data type fixes
    WARNING: This may result in precision loss for financial data
    """
    # Drop created indexes
    op.drop_index('ix_transactions_user_id_spent_at', table_name='transactions')
    op.drop_index('ix_expenses_user_id_date', table_name='expenses')
    
    # Remove foreign key constraints
    with op.batch_alter_table('user_profiles') as batch_op:
        batch_op.drop_constraint('fk_user_profiles_user_id', type_='foreignkey')
    
    with op.batch_alter_table('user_answers') as batch_op:
        batch_op.drop_constraint('fk_user_answers_user_id', type_='foreignkey')
    
    with op.batch_alter_table('goals') as batch_op:
        batch_op.drop_constraint('fk_goals_user_id', type_='foreignkey')
    
    with op.batch_alter_table('expenses') as batch_op:
        batch_op.drop_constraint('fk_expenses_user_id', type_='foreignkey')
    
    # Revert column types (WARNING: May cause precision loss)
    op.alter_column(
        'user_profiles',
        'user_id',
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(),
        existing_nullable=False
    )
    
    op.alter_column(
        'user_answers',
        'user_id',
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(),
        existing_nullable=False
    )
    
    op.alter_column(
        'users',
        'annual_income',
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Numeric(),
        existing_nullable=True
    )
    
    op.alter_column(
        'goals',
        'saved_amount',
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Numeric(),
        existing_nullable=False
    )
    
    op.alter_column(
        'goals',
        'target_amount',
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Numeric(),
        existing_nullable=False
    )
    
    op.alter_column(
        'expenses',
        'user_id',
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(),
        existing_nullable=False
    )
    
    # WARNING: Converting back to Float loses financial precision
    op.alter_column(
        'expenses',
        'amount',
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Float(),
        existing_nullable=False
    )