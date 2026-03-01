"""Add email verification and password reset fields to users table

Revision ID: 0007_email_password_reset_fields
Revises: 0006_fix_financial_data_types
Create Date: 2024-12-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0007_email_password_reset_fields'
down_revision = '0006_fix_financial_data_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add email verification and password reset fields"""
    
    # Add password reset fields
    op.add_column('users', sa.Column('password_reset_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_reset_attempts', sa.Integer(), nullable=False, server_default='0'))
    
    # Add email verification fields
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('email_verification_expires', sa.DateTime(timezone=True), nullable=True))
    
    # Create indexes for performance
    op.create_index('idx_users_password_reset_token', 'users', ['password_reset_token'])
    op.create_index('idx_users_email_verification_token', 'users', ['email_verification_token'])
    op.create_index('idx_users_email_verified', 'users', ['email_verified'])


def downgrade() -> None:
    """Remove email verification and password reset fields"""
    
    # Drop indexes
    op.drop_index('idx_users_email_verified', table_name='users')
    op.drop_index('idx_users_email_verification_token', table_name='users')
    op.drop_index('idx_users_password_reset_token', table_name='users')
    
    # Drop email verification fields
    op.drop_column('users', 'email_verification_expires')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
    
    # Drop password reset fields
    op.drop_column('users', 'password_reset_attempts')
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'password_reset_token')