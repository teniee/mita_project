"""add scheduled_expenses table

Problem 6 fix: users can now schedule future expenses so MITA
pre-adjusts safe_daily_limit, sends proactive reminders 3 days
before, and auto-creates the transaction + triggers rebalancing
on the scheduled date.

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_expenses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("merchant", sa.String(200), nullable=True),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("recurrence", sa.String(20), nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # user_id — base index for all user-scoped queries
    op.create_index("ix_scheduled_expenses_user_id", "scheduled_expenses", ["user_id"])

    # scheduled_date — cron "give me everything due today"
    op.create_index(
        "ix_scheduled_expenses_scheduled_date",
        "scheduled_expenses",
        ["scheduled_date"],
    )

    # status — filter pending only
    op.create_index(
        "ix_scheduled_expenses_status", "scheduled_expenses", ["status"]
    )

    # Composite: main query pattern for API + cron
    # "pending expenses for user X between date A and date B"
    op.create_index(
        "ix_scheduled_expenses_user_date_status",
        "scheduled_expenses",
        ["user_id", "scheduled_date", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduled_expenses_user_date_status", table_name="scheduled_expenses"
    )
    op.drop_index("ix_scheduled_expenses_status", table_name="scheduled_expenses")
    op.drop_index(
        "ix_scheduled_expenses_scheduled_date", table_name="scheduled_expenses"
    )
    op.drop_index("ix_scheduled_expenses_user_id", table_name="scheduled_expenses")
    op.drop_table("scheduled_expenses")
