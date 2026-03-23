"""add ignored_alerts table

Replaces the in-memory _ignored_alerts list that was lost on every
Railway restart. Budget alerts ignored by the user are now persisted
to PostgreSQL so the 3-day follow-up reminder cron survives restarts.

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ignored_alerts',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('overspend_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('goal_title', sa.String(255), nullable=True),
        sa.Column(
            'alert_date',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('reminded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Primary lookup: pending reminders for a user ordered by alert date
    op.create_index(
        'ix_ignored_alerts_user_reminded',
        'ignored_alerts',
        ['user_id', 'reminded', 'alert_date'],
    )


def downgrade() -> None:
    op.drop_index('ix_ignored_alerts_user_reminded', table_name='ignored_alerts')
    op.drop_table('ignored_alerts')
