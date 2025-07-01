"""add budget_advice table

Revision ID: 0003_budget_advice_table
Revises: 0002_subscription_plan_dates
Create Date: 2025-07-01 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_budget_advice_table"
down_revision = "0002_subscription_plan_dates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "budget_advice",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
    )
    op.create_index("ix_budget_advice_user_id", "budget_advice", ["user_id"])
    op.create_index("ix_budget_advice_date", "budget_advice", ["date"])


def downgrade():
    op.drop_index("ix_budget_advice_date", table_name="budget_advice")
    op.drop_index("ix_budget_advice_user_id", table_name="budget_advice")
    op.drop_table("budget_advice")
