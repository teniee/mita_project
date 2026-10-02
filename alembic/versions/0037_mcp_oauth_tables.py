"""OAuth storage for the ChatGPT app (MCP service).

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-02

Additive only: three new tables, no change to any existing table. Written by
the MCP service's OAuth endpoints (app/mcp/auth); the MCP service never runs
migrations itself — mita-production's start.sh applies this on deploy.

Codes and refresh tokens are stored as SHA-256 digests. Rows cascade with the
user, so deleting an account also ends its ChatGPT connection.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mcp_oauth_clients",
        sa.Column("client_id", sa.String(64), primary_key=True),
        sa.Column("client_info", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "mcp_oauth_authorization_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column(
            "client_id",
            sa.String(64),
            sa.ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("redirect_uri_provided_explicitly", sa.Boolean(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_mcp_oauth_authorization_codes_client_id",
        "mcp_oauth_authorization_codes",
        ["client_id"],
    )
    op.create_index(
        "ix_mcp_oauth_authorization_codes_user_id",
        "mcp_oauth_authorization_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_mcp_oauth_authorization_codes_expires_at",
        "mcp_oauth_authorization_codes",
        ["expires_at"],
    )

    op.create_table(
        "mcp_oauth_refresh_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "client_id",
            sa.String(64),
            sa.ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("family_id", "client_id", "user_id", "expires_at"):
        op.create_index(
            f"ix_mcp_oauth_refresh_tokens_{column}",
            "mcp_oauth_refresh_tokens",
            [column],
        )


def downgrade():
    op.drop_table("mcp_oauth_refresh_tokens")
    op.drop_table("mcp_oauth_authorization_codes")
    op.drop_table("mcp_oauth_clients")
