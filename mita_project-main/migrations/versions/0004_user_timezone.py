"""add user timezone column and timezone aware timestamps"""

revision = "0004_user_timezone"
down_revision = "0003_budget_advice_table"
branch_labels = None
depends_on = None

import sqlalchemy as sa

from alembic import op


def upgrade():
    op.add_column("users", sa.Column("timezone", sa.String(), server_default="UTC"))
    op.alter_column("transactions", "spent_at", type_=sa.DateTime(timezone=True))
    op.alter_column("transactions", "created_at", type_=sa.DateTime(timezone=True))
    op.alter_column("daily_plan", "date", type_=sa.DateTime(timezone=True))
    op.alter_column("daily_plan", "created_at", type_=sa.DateTime(timezone=True))
    op.alter_column("subscriptions", "starts_at", type_=sa.DateTime(timezone=True))
    op.alter_column("subscriptions", "expires_at", type_=sa.DateTime(timezone=True))
    op.alter_column("subscriptions", "created_at", type_=sa.DateTime(timezone=True))
    op.alter_column("budget_advice", "date", type_=sa.DateTime(timezone=True))


def downgrade():
    op.alter_column("budget_advice", "date", type_=sa.DateTime())
    op.alter_column("subscriptions", "created_at", type_=sa.DateTime())
    op.alter_column("subscriptions", "expires_at", type_=sa.DateTime())
    op.alter_column("subscriptions", "starts_at", type_=sa.DateTime())
    op.alter_column("daily_plan", "created_at", type_=sa.DateTime())
    op.alter_column("daily_plan", "date", type_=sa.DateTime())
    op.alter_column("transactions", "created_at", type_=sa.DateTime())
    op.alter_column("transactions", "spent_at", type_=sa.DateTime())
    op.drop_column("users", "timezone")
