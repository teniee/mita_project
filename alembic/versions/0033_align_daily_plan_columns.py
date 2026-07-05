"""Align daily_plan (and transactions.description) with the ORM models.

The daily_plan table was originally created around a single plan_json blob,
but the DailyPlan model evolved to per-category budget columns
(category, planned_amount, spent_amount, daily_budget, status). No migration
ever added them, so on a freshly-migrated database onboarding/calendar
generation crashes with 'column daily_plan.category does not exist'. This
brings the migrated schema in line with the model (and with what
create_all() produces), and relaxes plan_json to nullable to match.

Also adds transactions.description, which the Transaction model declares but
no migration ever created (a full-schema drift check found it).

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("daily_plan"):
        return

    if not _has_column("daily_plan", "category"):
        op.add_column(
            "daily_plan", sa.Column("category", sa.String(length=100), nullable=True)
        )
        op.create_index(
            "ix_daily_plan_category", "daily_plan", ["category"], unique=False
        )
    if not _has_column("daily_plan", "planned_amount"):
        op.add_column(
            "daily_plan",
            sa.Column(
                "planned_amount",
                sa.Numeric(precision=12, scale=2),
                nullable=True,
                server_default="0.00",
            ),
        )
    if not _has_column("daily_plan", "spent_amount"):
        op.add_column(
            "daily_plan",
            sa.Column(
                "spent_amount",
                sa.Numeric(precision=12, scale=2),
                nullable=True,
                server_default="0.00",
            ),
        )
    if not _has_column("daily_plan", "daily_budget"):
        op.add_column(
            "daily_plan",
            sa.Column("daily_budget", sa.Numeric(precision=12, scale=2), nullable=True),
        )
    if not _has_column("daily_plan", "status"):
        op.add_column(
            "daily_plan",
            sa.Column(
                "status", sa.String(length=20), nullable=True, server_default="green"
            ),
        )

    # The model declares plan_json nullable; the original table made it NOT NULL,
    # which would reject rows the ORM inserts without a plan_json payload.
    if _has_column("daily_plan", "plan_json"):
        op.alter_column("daily_plan", "plan_json", nullable=True)

    # transactions.description exists in the model but no migration created it.
    if sa.inspect(op.get_bind()).has_table("transactions") and not _has_column(
        "transactions", "description"
    ):
        op.add_column(
            "transactions",
            sa.Column("description", sa.String(length=500), nullable=True),
        )


def downgrade():
    if _has_column("transactions", "description"):
        op.drop_column("transactions", "description")
    if not sa.inspect(op.get_bind()).has_table("daily_plan"):
        return
    for col in ("status", "daily_budget", "spent_amount", "planned_amount"):
        if _has_column("daily_plan", col):
            op.drop_column("daily_plan", col)
    if _has_column("daily_plan", "category"):
        op.drop_index("ix_daily_plan_category", table_name="daily_plan")
        op.drop_column("daily_plan", "category")
