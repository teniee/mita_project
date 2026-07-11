"""TASK-9: enforce subscription idempotency at the DB level.

`subscriptions.original_transaction_id` (the store purchase identity /
webhook match key) has only a NON-unique index today, so the app-level
find-or-create in iap/routes.py is not race-safe: two concurrent store
notifications can both insert. This adds a partial UNIQUE index on
(platform, original_transaction_id) WHERE original_transaction_id IS NOT
NULL.

*** PRODUCTION DATA IMPACT ***
Creating the unique index FAILS if duplicate (platform,
original_transaction_id) pairs already exist. The preflight
(scripts/migrations/task_7_8_9_preflight.sql) lists any such duplicates so
the owner can reconcile them BEFORE applying (this migration deliberately
does NOT auto-delete subscription rows — money records must be reconciled by
hand). No rows are changed by this migration. Downgrade drops the unique
index and restores the plain index.

Revision ID: 0038
Revises: 0037
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

_UNIQUE = "uq_subscriptions_platform_original_txn"
_PLAIN = "ix_subscriptions_original_transaction_id"


def upgrade():
    conn = op.get_bind()
    exists = conn.exec_driver_sql("SELECT to_regclass('public.subscriptions')").scalar()
    if exists is None:
        logger.info("TASK-9: subscriptions table absent; skipping")
        return

    dupes = conn.exec_driver_sql(
        "SELECT count(*) FROM ("
        "  SELECT platform, original_transaction_id "
        "  FROM subscriptions "
        "  WHERE original_transaction_id IS NOT NULL "
        "  GROUP BY platform, original_transaction_id "
        "  HAVING count(*) > 1"
        ") d"
    ).scalar()
    if dupes:
        # Fail loudly rather than silently dropping money rows.
        raise RuntimeError(
            f"TASK-9: {dupes} duplicate (platform, original_transaction_id) "
            "group(s) exist in subscriptions. Reconcile them by hand "
            "(see scripts/migrations/task_7_8_9_preflight.sql) before "
            "applying this migration — it will not delete subscription rows."
        )

    op.create_index(
        _UNIQUE,
        "subscriptions",
        ["platform", "original_transaction_id"],
        unique=True,
        postgresql_where=sa.text("original_transaction_id IS NOT NULL"),
    )


def downgrade():
    conn = op.get_bind()
    exists = conn.exec_driver_sql("SELECT to_regclass('public.subscriptions')").scalar()
    if exists is None:
        return
    op.drop_index(_UNIQUE, table_name="subscriptions")
