"""add composite index for transactions user_id, created_at

Revision ID: 0006_transactions_user_created_at_idx
Revises: 0005_push_token_platform
Create Date: 2025-10-01 00:00:00.000000
"""


from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_transactions_user_created_at_idx"
down_revision = "0005_push_token_platform"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_transactions_user_created_at",
        "transactions",
        ["user_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_transactions_user_created_at", table_name="transactions")
