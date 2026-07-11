"""TASK-7: add user_id FK + ON DELETE CASCADE to five user-scoped tables.

`moods`, `budget_advice`, `notification_logs`, `push_tokens` and
`ignored_alerts` carry a `user_id uuid` column with NO foreign key
(confirmed against the live schema). Orphan rows survive user deletion, and
`push_tokens` orphans could push to a deleted user's device.

This migration mirrors 0022 (clean orphans first, THEN add the constraint):
1. For each table it logs the orphan count and DELETES rows whose user_id
   has no matching users.id (a dangling FK add would otherwise fail).
2. Adds `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`.

*** PRODUCTION DATA IMPACT ***
Upgrade DELETES orphaned rows in these five tables. Run the preflight in
scripts/migrations/task_7_8_9_preflight.sql against production FIRST to see
the exact counts; deleting orphans is safe (they reference no live user)
but the counts must be reviewed in the owner's maintenance window before
this is applied. Downgrade drops the FK only — deleted orphans are not
resurrected.

Revision ID: 0036
Revises: 0035
"""

import logging

from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

_TABLES = (
    "moods",
    "budget_advice",
    "notification_logs",
    "push_tokens",
    "ignored_alerts",
)


def _fk_name(table: str) -> str:
    return f"fk_{table}_user_id_users"


def upgrade():
    conn = op.get_bind()
    insp = op.get_context().dialect.get_columns  # noqa: F841 (kept for clarity)

    for table in _TABLES:
        # Skip tables that don't exist on this DB (defensive for partial envs).
        exists = conn.exec_driver_sql(
            "SELECT to_regclass(%(t)s)", {"t": f"public.{table}"}
        ).scalar()
        if exists is None:
            logger.info("TASK-7: table %s absent; skipping", table)
            continue

        orphans = conn.exec_driver_sql(
            f"SELECT count(*) FROM {table} t "  # nosec B608 - fixed identifier
            "LEFT JOIN users u ON u.id = t.user_id "
            "WHERE t.user_id IS NOT NULL AND u.id IS NULL"
        ).scalar()
        logger.info("TASK-7: %s has %s orphaned row(s); deleting", table, orphans)

        if orphans:
            conn.exec_driver_sql(
                f"DELETE FROM {table} "  # nosec B608 - fixed identifier
                "WHERE user_id IS NOT NULL "
                "AND user_id NOT IN (SELECT id FROM users)"
            )

        op.create_foreign_key(
            _fk_name(table),
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade():
    for table in _TABLES:
        op.drop_constraint(_fk_name(table), table, type_="foreignkey")
