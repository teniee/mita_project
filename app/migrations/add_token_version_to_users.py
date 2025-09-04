"""Add token_version field to users table for enhanced token security

Revision ID: add_token_version
Revises: [previous_revision]
Create Date: 2025-01-18 12:00:00.000000

This migration adds a token_version field to the users table to support
user-level token revocation through version-based invalidation.
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    """Add token_version column to users table"""
    # Add token_version column with default value of 1
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, default=1))
    
    # Update existing users to have token_version = 1
    op.execute('UPDATE users SET token_version = 1 WHERE token_version IS NULL')
    
    # Create index for better performance on token version queries
    op.create_index('idx_users_token_version', 'users', ['token_version'])


def downgrade():
    """Remove token_version column from users table"""
    # Drop the index first
    op.drop_index('idx_users_token_version', 'users')
    
    # Remove the column
    op.drop_column('users', 'token_version')