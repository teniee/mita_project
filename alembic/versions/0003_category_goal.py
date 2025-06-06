"""add category goals table"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_category_goal"
down_revision = "0002_mood"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "category_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("target_amount", sa.Numeric(), nullable=False),
    )


def downgrade():
    op.drop_table("category_goals")
