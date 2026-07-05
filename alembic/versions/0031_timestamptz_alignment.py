"""Align naive timestamp columns with timezone-aware model defaults.

Models set timezone-aware (UTC) datetimes on these columns, but the columns
were created as TIMESTAMP WITHOUT TIME ZONE. asyncpg refuses to bind aware
datetimes to naive columns, so inserts through async sessions (goals module,
repository layer) failed at runtime. Existing values were written as UTC.

Revision ID: 0031
Revises: 0030
"""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

_COLUMNS = {
    "goals": ["created_at", "last_updated", "completed_at", "deleted_at"],
    "ai_analysis_snapshots": ["created_at"],
    "habits": ["created_at"],
    "push_tokens": ["created_at"],
    "users": ["premium_until"],
}


def upgrade():
    for table, columns in _COLUMNS.items():
        for column in columns:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE TIMESTAMP WITH TIME ZONE "
                f"USING {column} AT TIME ZONE 'UTC'"
            )


def downgrade():
    for table, columns in _COLUMNS.items():
        for column in columns:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE TIMESTAMP WITHOUT TIME ZONE "
                f"USING {column} AT TIME ZONE 'UTC'"
            )
