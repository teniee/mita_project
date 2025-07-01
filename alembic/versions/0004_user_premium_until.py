"""add premium_until field to user"""

import sqlalchemy as sa

from alembic import op

revision = "0004_user_premium_until"
down_revision = "0003_goals"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("premium_until", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("users", "premium_until")
