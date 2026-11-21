"""How the user buys for each budget line (behavioral budget).

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-03

Additive only: one new table, no change to any existing table or row.

``spending_patterns`` keeps, per user and budget line, what the user said
about how they buy for it (docs/chatgpt-app/behavioral-budget.md):

* ``planned`` — on known days: groceries every Wednesday (``weekly`` +
  ``weekdays``), twice a month (``times_per_month``), on the 1st and 15th
  (``dates`` + ``days_of_month``), every other Friday (``biweekly`` +
  ``anchor_date``)… MITA splits the line's monthly amount exactly over those
  real dates of each month;
* ``flexible`` — no fixed purchase days (coffee, cigarettes, walks): a
  monthly envelope with daily guidance, never invented purchases;
* ``not_applicable`` — one of MITA's suggested lines the user does not have
  (no medical insurance): left out of the plan.

``source`` is ``user_confirmed`` only: MITA never stores an inferred pattern.
Written by the MCP service (``save_spending_patterns``, ``save_monthly_budget``);
read by the reviewed budget and the month rollover. Cascades with the user.
The MCP role needs ``GRANT SELECT, INSERT, UPDATE, DELETE ON spending_patterns
TO mita_mcp``.

Downgrade drops the table: plans already saved keep their dates; new months
fall back to flexible lines (no purchase dates).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "spending_patterns",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("line_key", sa.String(length=50), primary_key=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=True),
        sa.Column(
            "weekdays",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "days_of_month",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("times_per_month", sa.SmallInteger(), nullable=True),
        sa.Column("anchor_date", sa.Date(), nullable=True),
        sa.Column("typical_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "source",
            sa.String(length=20),
            nullable=False,
            server_default="user_confirmed",
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('planned', 'flexible', 'not_applicable')",
            name="ck_spending_patterns_kind",
        ),
        sa.CheckConstraint(
            "frequency IS NULL OR frequency IN ('daily', 'weekdays', 'weekly', "
            "'biweekly', 'times_per_month', 'monthly', 'dates')",
            name="ck_spending_patterns_frequency",
        ),
        sa.CheckConstraint(
            "(kind = 'planned') = (frequency IS NOT NULL)",
            name="ck_spending_patterns_planned_has_frequency",
        ),
        sa.CheckConstraint(
            "times_per_month IS NULL OR times_per_month BETWEEN 1 AND 31",
            name="ck_spending_patterns_times",
        ),
        sa.CheckConstraint(
            "typical_amount IS NULL OR typical_amount > 0",
            name="ck_spending_patterns_typical_amount",
        ),
        sa.CheckConstraint(
            "source IN ('user_confirmed')", name="ck_spending_patterns_source"
        ),
    )


def downgrade():
    op.drop_table("spending_patterns")
