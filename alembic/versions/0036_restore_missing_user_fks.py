"""Restore the users foreign keys that migration 0022 never applied.

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-11

WHY THIS EXISTS
---------------
Migration 0022 ("add_missing_fk_constraints") is the only migration in the chain
whose effects are entirely absent from production, while every migration before
and after it applied:

    0021 habit_completions ............ PRESENT
    0022 subscriptions.deleted_at ..... ABSENT
    0022 ix_subscriptions_deleted_at .. ABSENT
    0022 fk_daily_plan_user_id ........ ABSENT
    0022 fk_subscriptions_user_id ..... ABSENT
    0022 fk_goals_user_id ............. ABSENT
    0023 habits.target_frequency ...... PRESENT
    0024 waitlist ..................... PRESENT
    0025 redistribution_events ........ PRESENT
    0026 daily_plan.goal_id (+ its FK)  PRESENT
    0030 user_preferences ............. PRESENT
    0035 uq_daily_plan_user_date_cat .. PRESENT

The version table nonetheless reads 0035, so alembic believes 0022 ran. The
database was advanced past it without executing it. The same root cause was
seen once before, from the other end: production's subscriptions table has no
deleted_at column (see f7dafff), which is also a 0022 effect.

The practical consequence: deleting a user leaves every one of that user's
daily_plan rows behind, silently, pointing at a user id that no longer exists.
0022 is left untouched -- rewriting an applied migration would desync any
environment that DID run it.

SCOPE -- deliberately narrow
----------------------------
Adds only the two FKs the ORM models actually declare:

    daily_plan.user_id -> users.id  ON DELETE CASCADE   (daily_plan.py:24)
    goals.user_id      -> users.id  ON DELETE CASCADE   (goal.py:26)

Explicitly NOT changed, and why:

  transactions.user_id
      The model declares ForeignKey("users.id") with no ondelete, which is
      NO ACTION, and production matches it exactly. This is not drift. It is
      also the safer semantic for a financial ledger: a stray user delete
      cannot silently destroy transaction history, it fails loudly instead.
      Changing it to CASCADE is a product decision, not a drift repair.

  subscriptions.user_id
      0022 wanted an FK here, but the ORM model declares user_id as a plain
      Column with no ForeignKey at all. Adding one would take the database
      PAST the model rather than into line with it.

  subscriptions.deleted_at
      Also a 0022 effect, but the model deliberately dropped that mapping in
      f7dafff to match production. Re-adding it would reopen a fixed bug.

SAFETY
------
Unlike 0022, this migration never deletes data. If it finds orphan rows it
raises and leaves the database untouched, because an orphan in a live database
is a fact that needs a human decision, not something a migration should quietly
destroy. Verified against production before writing this: daily_plan 6809 rows
/ 0 orphans / 0 nulls, goals 0 rows.
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


# (table, fk name, ondelete) -- ondelete mirrors the ORM model exactly.
_TARGETS = [
    ("daily_plan", "fk_daily_plan_user_id", "CASCADE"),
    ("goals", "fk_goals_user_id", "CASCADE"),
]


def _existing_user_fk(inspector, table):
    """Return the name of any existing user_id -> users FK on `table`."""
    for fk in inspector.get_foreign_keys(table):
        if fk.get("constrained_columns") == ["user_id"] and (
            fk.get("referred_table") == "users"
        ):
            return fk.get("name") or "<unnamed>"
    return None


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # ALTER TABLE ... ADD CONSTRAINT is not supported by SQLite; these FKs
        # exist in the metadata that create_all() builds for such backends.
        return

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())

    # --- pass 1: refuse to touch anything if real orphans exist -------------
    problems = []
    for table, _name, _ondelete in _TARGETS:
        if table not in tables:
            continue
        if _existing_user_fk(inspector, table):
            continue
        # Only rows pointing at a user that does not exist can block the
        # constraint. A NULL user_id cannot: SQL foreign keys do not constrain
        # NULLs. (Both columns are NOT NULL in the models and in production
        # anyway, so the case is doubly unreachable.)
        orphans = conn.execute(
            sa.text(
                f"SELECT count(*) FROM {table} c "  # nosec B608 - fixed identifiers
                "LEFT JOIN users u ON u.id = c.user_id "
                "WHERE c.user_id IS NOT NULL AND u.id IS NULL"
            )
        ).scalar()
        if orphans:
            problems.append(f"{table}: {orphans} row(s) reference a missing user")

    if problems:
        raise RuntimeError(
            "0036 refuses to add foreign keys while orphaned rows exist.\n  "
            + "\n  ".join(problems)
            + "\n\nNo change has been made. Decide what those rows are before "
            "re-running: they are either real data whose owner was deleted, or "
            "residue that should be removed deliberately. This migration will "
            "not delete them for you -- migration 0022 did exactly that, and "
            "silent data deletion inside a migration is how the original "
            "problem became invisible."
        )

    # --- pass 2: add the constraints ---------------------------------------
    for table, name, ondelete in _TARGETS:
        if table not in tables:
            print(f"  - {table} does not exist; skipping")
            continue
        existing = _existing_user_fk(inspector, table)
        if existing:
            print(f"  - {table}.user_id already has FK {existing!r}; skipping")
            continue
        op.create_foreign_key(
            name, table, "users", ["user_id"], ["id"], ondelete=ondelete
        )
        print(f"  + {name}: {table}.user_id -> users.id ON DELETE {ondelete}")


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    for table, name, _ondelete in _TARGETS:
        if table not in tables:
            continue
        names = {fk.get("name") for fk in inspector.get_foreign_keys(table)}
        if name in names:
            op.drop_constraint(name, table, type_="foreignkey")
            print(f"  - dropped {name}")
