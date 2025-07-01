"""add push tokens table"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0005_push_tokens"
down_revision = "0004_user_premium_until"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "push_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("token", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("push_tokens")
