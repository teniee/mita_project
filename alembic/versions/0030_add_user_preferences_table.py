"""add user_preferences table

Adds the user_preferences table required for storing per-user behavioral,
notification, and budget automation preferences.
Without this table the app crashes on any request that reads or writes user
preferences because INSERT/SELECT on "user_preferences" fails with
"relation user_preferences does not exist".

Revision ID: 0030
Revises: 0029
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_preferences',

        # --- Primary key ---
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),

        # --- Owner: one row per user ---
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id'),
            nullable=False,
        ),

        # --- Behavioral analysis preferences ---
        sa.Column('auto_insights', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('anomaly_detection', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('predictive_alerts', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('peer_comparison', sa.Boolean(), nullable=True, server_default=sa.false()),

        # --- Notification preferences ---
        sa.Column('anomaly_alerts', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('pattern_insights', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('weekly_summary', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('spending_warnings', sa.Boolean(), nullable=True, server_default=sa.true()),

        # --- Budget automation preferences ---
        sa.Column('auto_adapt_enabled', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('redistribution_enabled', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('ai_suggestions_enabled', sa.Boolean(), nullable=True, server_default=sa.true()),
        # Budget percentage threshold for notifications — {"value": 0.8} = 80%
        sa.Column(
            'notification_threshold',
            sa.JSON(),
            nullable=True,
            server_default=sa.text('\'{"value": 0.8}\''),
        ),

        # --- Budget mode ---
        # Allowed values: flexible | strict | goal-oriented
        sa.Column(
            'budget_mode',
            sa.String(20),
            nullable=True,
            server_default='flexible',
        ),

        # --- Flexible additional storage for future preferences ---
        sa.Column('additional_preferences', sa.JSON(), nullable=True),

        # --- Timestamps ---
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text('now()'),
        ),
    )

    # Unique constraint: exactly one preference row per user
    op.create_unique_constraint(
        'uq_user_preferences_user_id',
        'user_preferences',
        ['user_id'],
    )

    # Index: look up preferences by user_id (primary access pattern — always filtered by user)
    op.create_index(
        'ix_user_preferences_user_id',
        'user_preferences',
        ['user_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_user_preferences_user_id', table_name='user_preferences')
    op.drop_constraint('uq_user_preferences_user_id', 'user_preferences', type_='unique')
    op.drop_table('user_preferences')
