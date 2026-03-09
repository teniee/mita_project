"""add waitlist table

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'waitlist',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('ref_code', sa.String(12), nullable=False),
        sa.Column('referred_by_code', sa.String(12), nullable=True),
        sa.Column('referral_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('position_boost', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confirmed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confirm_token', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_waitlist_email', 'waitlist', ['email'], unique=True)
    op.create_index('ix_waitlist_ref_code', 'waitlist', ['ref_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_waitlist_ref_code', table_name='waitlist')
    op.drop_index('ix_waitlist_email', table_name='waitlist')
    op.drop_table('waitlist')
