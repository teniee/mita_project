"""TASK-18 schema hygiene: push_tokens.platform default, notification
retry_count String->Integer, and notification enum CHECK constraints.

Three independent, low-risk items left over from TASK-18 after the safe
subset shipped in df9fbe7. Each is guarded so the migration is idempotent
and safe to run against a schema that already satisfies part of it.

1. push_tokens.platform — the model declares a Python-side default ("fcm")
   but the column has no server_default, so a raw INSERT that omits platform
   violates NOT NULL. Add a DB-level DEFAULT 'fcm'.

2. notifications.retry_count — stored as VARCHAR ("0") but semantically an
   integer retry counter. Convert to INTEGER (garbage/NULL coerced to 0) and
   give it a server_default of 0.

3. notifications.type / priority / status — free-form VARCHAR columns that
   should only ever hold their NotificationType/Priority/Status enum values.
   Add CHECK constraints so the DB rejects out-of-range values.

OWNER-GATED: schema-changing. Do not apply outside an owner migration
window. Prepared on branch migrations/task-18-schema-cleanup; not merged.

Revision ID: 0036
Revises: 0035
"""

import sqlalchemy as sa

from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


_NOTIFICATION_ENUMS = {
    "type": ["alert", "warning", "info", "tip", "achievement", "reminder",
             "recommendation"],
    "priority": ["low", "medium", "high", "critical"],
    "status": ["pending", "sent", "delivered", "read", "failed", "cancelled"],
}


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _column(table: str, column: str):
    insp = sa.inspect(op.get_bind())
    for c in insp.get_columns(table):
        if c["name"] == column:
            return c
    return None


def _has_check(table: str, name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(ck["name"] == name for ck in insp.get_check_constraints(table))


def upgrade():
    bind = op.get_bind()

    # 1. push_tokens.platform DB-level default.
    if _has_table("push_tokens") and _column("push_tokens", "platform"):
        op.alter_column(
            "push_tokens",
            "platform",
            existing_type=sa.String(),
            server_default="fcm",
            existing_nullable=False,
        )

    if _has_table("notifications"):
        # 2. retry_count VARCHAR -> INTEGER (coerce non-numeric/NULL to 0).
        col = _column("notifications", "retry_count")
        if col is not None and not isinstance(col["type"], sa.Integer):
            op.execute(
                "ALTER TABLE notifications "
                "ALTER COLUMN retry_count TYPE INTEGER "
                "USING CASE WHEN retry_count ~ '^[0-9]+$' "
                "THEN retry_count::integer ELSE 0 END"
            )
            op.alter_column(
                "notifications",
                "retry_count",
                existing_type=sa.Integer(),
                server_default="0",
                existing_nullable=True,
            )

        # 3. enum CHECK constraints on type / priority / status.
        for column, values in _NOTIFICATION_ENUMS.items():
            if _column("notifications", column) is None:
                continue
            name = f"ck_notifications_{column}_enum"
            if _has_check("notifications", name):
                continue
            allowed = ", ".join(f"'{v}'" for v in values)
            op.create_check_constraint(
                name, "notifications", f"{column} IN ({allowed})"
            )

    # Keep bind referenced for tooling that inspects the function body.
    _ = bind


def downgrade():
    if _has_table("notifications"):
        for column in _NOTIFICATION_ENUMS:
            name = f"ck_notifications_{column}_enum"
            if _has_check("notifications", name):
                op.drop_constraint(name, "notifications", type_="check")

        col = _column("notifications", "retry_count")
        if col is not None and isinstance(col["type"], sa.Integer):
            op.alter_column(
                "notifications",
                "retry_count",
                existing_type=sa.Integer(),
                server_default=None,
                existing_nullable=True,
            )
            op.execute(
                "ALTER TABLE notifications "
                "ALTER COLUMN retry_count TYPE VARCHAR "
                "USING retry_count::varchar"
            )

    if _has_table("push_tokens") and _column("push_tokens", "platform"):
        op.alter_column(
            "push_tokens",
            "platform",
            existing_type=sa.String(),
            server_default=None,
            existing_nullable=False,
        )
