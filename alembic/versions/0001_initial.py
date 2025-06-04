
"""initial unified migration

Revision ID: 0001_initial
Revises: 
Create Date: 2025-05-07

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('country', sa.String(length=2), default='US'),
        sa.Column('annual_income', sa.Numeric(), default=0),
        sa.Column('is_premium', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime())
    )

    op.create_table('transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('currency', sa.String(length=3), default='USD'),
        sa.Column('spent_at', sa.DateTime(), index=True),
        sa.Column('created_at', sa.DateTime())
    )

    op.create_table('daily_plan',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('date', sa.DateTime(), nullable=False, index=True),
        sa.Column('plan_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime())
    )

    op.create_table('subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('receipt', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(), default='active'),
        sa.Column('current_period_end', sa.DateTime()),
        sa.Column('created_at', sa.DateTime())
    )

    op.create_table('ai_analysis_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rating', sa.String(), nullable=True),
        sa.Column('risk', sa.String(), nullable=True),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('full_profile', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

def downgrade():
    op.drop_table('ai_analysis_snapshots')
    op.drop_table('subscriptions')
    op.drop_table('daily_plan')
    op.drop_table('transactions')
    op.drop_table('users')
