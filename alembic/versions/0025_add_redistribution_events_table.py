"""add redistribution_events table

Replaces the in-memory audit log (_audit_log dict) that was lost on
every Railway restart. All budget redistribution transfers are now
persisted to PostgreSQL.

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'redistribution_events',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('from_category', sa.String(100), nullable=False),
        sa.Column('to_category',   sa.String(100), nullable=False),
        sa.Column('amount',        sa.Numeric(12, 2), nullable=False),
        sa.Column('reason',        sa.String(50),  nullable=False),
        sa.Column('from_day',      sa.Date(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    # Primary lookup: user history ordered by newest first
    op.create_index(
        'ix_redistribution_events_user_created',
        'redistribution_events',
        ['user_id', sa.text('created_at DESC')],
    )
    # Secondary: filter by month for monthly reports
    op.create_index(
        'ix_redistribution_events_user_day',
        'redistribution_events',
        ['user_id', 'from_day'],
    )


def downgrade() -> None:
    op.drop_index('ix_redistribution_events_user_day',     table_name='redistribution_events')
    op.drop_index('ix_redistribution_events_user_created', table_name='redistribution_events')
    op.drop_table('redistribution_events')
