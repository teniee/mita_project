"""TASK-8: bind money columns to Numeric(12,2).

Confirmed against the live schema:
- users.monthly_income  = unbounded numeric  -> Numeric(12,2)
- users.savings_goal    = unbounded numeric  -> Numeric(12,2)
- expenses.amount       = double precision   -> Numeric(12,2)
(users.annual_income is already Numeric(12,2); the model drift is fixed in
app/db/models/user.py in the same batch.)

*** PRODUCTION DATA IMPACT ***
This ALTERs column types. Values already at <=2 decimal places are
unaffected; any value with >2 dp is ROUNDED to the cent by the USING cast
(expenses.amount is the only real risk — it was stored as binary float and
may carry sub-cent noise). The preflight
(scripts/migrations/task_7_8_9_preflight.sql) counts rows whose rounded
value differs from the stored value so the owner can review before applying.
No rows are deleted. Downgrade returns the columns to unbounded numeric /
double precision (rounding is NOT reversible).

Revision ID: 0037
Revises: 0036
"""

import logging

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def _log_precision_loss(conn, table, column):
    exists = conn.exec_driver_sql(
        "SELECT to_regclass(%(t)s)", {"t": f"public.{table}"}
    ).scalar()
    if exists is None:
        logger.info("TASK-8: table %s absent; skipping %s", table, column)
        return False
    affected = conn.exec_driver_sql(
        f"SELECT count(*) FROM {table} "  # nosec B608 - fixed identifiers
        f"WHERE {column} IS NOT NULL "
        f"AND round({column}::numeric, 2) <> {column}::numeric"
    ).scalar()
    logger.info(
        "TASK-8: %s.%s has %s row(s) that will be rounded to the cent",
        table,
        column,
        affected,
    )
    return True


def upgrade():
    conn = op.get_bind()

    for table, column in (
        ("users", "monthly_income"),
        ("users", "savings_goal"),
        ("expenses", "amount"),
    ):
        if not _log_precision_loss(conn, table, column):
            continue
        op.execute(
            f"ALTER TABLE {table} "  # nosec B608 - fixed identifiers
            f"ALTER COLUMN {column} TYPE NUMERIC(12,2) "
            f"USING round({column}::numeric, 2)"
        )


def downgrade():
    conn = op.get_bind()
    for table, column, target in (
        ("users", "monthly_income", "NUMERIC"),
        ("users", "savings_goal", "NUMERIC"),
        ("expenses", "amount", "DOUBLE PRECISION"),
    ):
        exists = conn.exec_driver_sql(
            "SELECT to_regclass(%(t)s)", {"t": f"public.{table}"}
        ).scalar()
        if exists is None:
            continue
        op.execute(
            f"ALTER TABLE {table} "  # nosec B608 - fixed identifiers
            f"ALTER COLUMN {column} TYPE {target} USING {column}::{target}"
        )
