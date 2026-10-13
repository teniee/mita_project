"""ChatGPT app: setup state per user, and idempotency records for writes.

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-11

Additive only: two new tables, no change to any existing table. Both are
written by the MCP service's tools (app/mcp); the MCP service never runs
migrations itself.

* ``mcp_user_profiles`` — what the ChatGPT app knows beyond ``users``:
  household size, which profile fields the user actually confirmed (the
  ``users`` defaults USD / UTC / 0 cannot be told apart from a choice), and
  the user's usage-statistics choice. Income, currency, timezone and monthly
  savings stay canonical on ``users``.
* ``mcp_idempotency_keys`` — one row per completed create operation, so a
  retried tool call returns the original result instead of writing twice.
  Holds a digest of the client key and of the request plus the ids of the
  rows created; no amounts, merchants or other values.

Both cascade with the user.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mcp_user_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("household_size", sa.SmallInteger(), nullable=True),
        sa.Column("income_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("currency_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("savings_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "usage_analytics_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "usage_analytics_updated_at", sa.DateTime(timezone=True), nullable=True
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
        sa.CheckConstraint(
            "household_size IS NULL OR household_size BETWEEN 1 AND 20",
            name="ck_mcp_user_profiles_household_size",
        ),
    )

    op.create_table(
        "mcp_idempotency_keys",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # sha256(operation | hashed ChatGPT session | client key)
        sa.Column("scope_hash", sa.String(64), primary_key=True),
        sa.Column("operation", sa.String(40), nullable=False),
        # sha256 of the canonical request, to refuse a reused key with new data
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "resource_ids",
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
    )
    op.create_index(
        "ix_mcp_idempotency_keys_user_created",
        "mcp_idempotency_keys",
        ["user_id", "created_at"],
    )


def downgrade():
    op.drop_index(
        "ix_mcp_idempotency_keys_user_created", table_name="mcp_idempotency_keys"
    )
    op.drop_table("mcp_idempotency_keys")
    op.drop_table("mcp_user_profiles")
