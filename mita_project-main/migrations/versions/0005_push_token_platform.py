"""add platform column to push tokens

Revision ID: 0005_push_token_platform
Revises: 0004_user_timezone
Create Date: 2025-09-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_push_token_platform"
down_revision = "0004_user_timezone"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "push_tokens",
        sa.Column("platform", sa.String(), nullable=False, server_default="fcm"),
    )


def downgrade():
    op.drop_column("push_tokens", "platform")
