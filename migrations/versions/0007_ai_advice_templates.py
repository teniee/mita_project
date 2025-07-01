"""create ai_advice_templates table

Revision ID: 0007_ai_advice_templates
Revises: 0006_transactions_user_created_at_idx
Create Date: 2025-10-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0007_ai_advice_templates"
down_revision = "0006_transactions_user_created_at_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_advice_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("text", sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table("ai_advice_templates")

