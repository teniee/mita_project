"""add plan and dates to subscription

Revision ID: 0002_subscription_plan_dates
Revises: 0001_initial
Create Date: 2025-06-01 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_subscription_plan_dates"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "subscriptions",
        sa.Column("plan", sa.String(), server_default="standard"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("starts_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.drop_column("subscriptions", "current_period_end")


def downgrade():
    op.add_column(
        "subscriptions",
        sa.Column("current_period_end", sa.DateTime()),
    )
    op.drop_column("subscriptions", "expires_at")
    op.drop_column("subscriptions", "starts_at")
    op.drop_column("subscriptions", "plan")
