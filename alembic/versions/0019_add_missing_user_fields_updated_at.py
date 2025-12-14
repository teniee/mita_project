"""add_missing_user_fields_updated_at_premium_until_token_version

Revision ID: 0019_add_missing_user_fields
Revises: 0018_add_soft_deletes
Create Date: 2025-09-07 21:04:30.252625

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0019_add_missing_user_fields'
down_revision = '0018_add_soft_deletes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing fields to users table"""
    
    # Add updated_at column with default value and auto-update trigger
    op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    
    # Add token_version column if not exists (for JWT security)
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='1'))
    
    # Create indexes for performance
    op.create_index('idx_users_updated_at', 'users', ['updated_at'])
    op.create_index('idx_users_token_version', 'users', ['token_version'])
    
    # Create trigger to automatically update updated_at column on row updates
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Remove added fields from users table"""
    
    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop indexes
    op.drop_index('idx_users_token_version', 'users')
    op.drop_index('idx_users_updated_at', 'users')
    
    # Drop columns
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'updated_at')
