"""add goals table"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_goals"
down_revision = "0002_mood"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("target_amount", sa.Numeric(), nullable=False),
        sa.Column(
            "saved_amount",
            sa.Numeric(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("goals")
