"""ChatGPT app: budget lines the user names and sets (F-11).

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-28

Additive only: one new table, no change to any existing table. Written by the
MCP service (``save_monthly_budget``); the MCP service never runs migrations.

* ``mcp_budget_lines`` — per user, each budget line they named in ChatGPT
  ("Fuel", "Cigarettes", …). The line's amounts are ordinary ``daily_plan``
  rows under ``line_key`` (``"my:<label>"``) and its expenses ordinary
  transactions with that category; this row keeps only ``replaces``, the
  engine lines (e.g. ``transport gas``) the user's line takes the place of,
  so a month rebuilt later never budgets the same spending twice.

Cascades with the user. Downgrade drops the table: the lines stay in the
plans and the ledger as amounts; only the "replaces" choice is lost.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mcp_budget_lines",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("line_key", sa.String(length=50), primary_key=True),
        sa.Column(
            "replaces",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
    )


def downgrade():
    op.drop_table("mcp_budget_lines")
