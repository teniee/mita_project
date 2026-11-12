"""Which expense paid which saved regular payment (obligation identity).

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-03

Additive only: one new table, no change to any existing table or row.

Until now MITA could not tell which bill an expense paid, so the bills
reserve and the calendar counted EVERY expense in a bill's category as paying
it: a EUR 60 car part under Transport paid EUR 60 of a EUR 270 car loan.
``obligation_payments`` records the user's own statement "this expense paid
that due date of that saved payment"; from now on only such a link settles a
fixed obligation (docs/chatgpt-app/behavioral-budget.md).

* one expense pays at most one due date (``uq_obligation_payments_transaction``);
  one due date may be paid in parts;
* cascades with the user, the saved payment and the expense (a hard delete);
  a soft-deleted expense is ignored by every reader;
* existing expenses are NOT linked: nothing proves which of them paid a bill.

Written by the MCP service; read by the ledger rebuild, the forecast (MCP and
the mobile API) and the calendar. The MCP role needs
``GRANT SELECT, INSERT, DELETE ON obligation_payments TO mita_mcp``.

Downgrade drops the table: every bill goes back to "not paid in MITA" (the
expenses themselves are untouched).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "obligation_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scheduled_expense_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_expenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "transaction_id", name="uq_obligation_payments_transaction"
        ),
    )
    op.create_index(
        "ix_obligation_payments_user_due",
        "obligation_payments",
        ["user_id", "due_date"],
    )
    op.create_index(
        "ix_obligation_payments_obligation_due",
        "obligation_payments",
        ["scheduled_expense_id", "due_date"],
    )


def downgrade():
    op.drop_index(
        "ix_obligation_payments_obligation_due", table_name="obligation_payments"
    )
    op.drop_index("ix_obligation_payments_user_due", table_name="obligation_payments")
    op.drop_table("obligation_payments")
