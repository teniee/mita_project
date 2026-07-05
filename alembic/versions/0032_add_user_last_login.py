"""Add users.last_login — referenced by the repository layer and the Google
OAuth login flow (update_last_login), but the column never existed, so those
paths raised AttributeError.

Revision ID: 0032
Revises: 0031
"""

import sqlalchemy as sa

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("users", "last_login")
