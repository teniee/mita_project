"""add habit target_frequency field

Revision ID: 0023_add_habit_target_frequency
Revises: 0022_add_missing_fk_constraints
Create Date: 2026-01-12 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0023_add_habit_target_frequency'
down_revision = '0022_add_missing_fk_constraints'
branch_labels = None
depends_on = None


def upgrade():
    # Add target_frequency column to habits table
    op.add_column('habits', sa.Column('target_frequency', sa.String(), nullable=False, server_default='daily'))

    # Remove server_default after adding the column (so new rows don't get default)
    op.alter_column('habits', 'target_frequency', server_default=None)


def downgrade():
    # Remove target_frequency column
    op.drop_column('habits', 'target_frequency')
