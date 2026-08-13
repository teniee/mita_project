"""Migration 0036 must restore the users FKs without ever destroying data.

Migration 0022 was supposed to add these constraints. It is the only migration
in the chain whose effects are entirely absent from production while every
migration before and after it applied, so the database was advanced past it
without executing it. 0036 repairs that.

0022 also DELETED orphan rows to make its constraints apply. 0036 must not:
an orphan in a live database is a fact that needs a human decision, and silent
deletion inside a migration is how the original problem stayed invisible. The
refusal path is the most important test here.

Runs the migration's own upgrade()/downgrade() against a dedicated PostgreSQL
schema built from the ORM metadata, so it exercises the real code rather than a
paraphrase of it. Skipped on non-PostgreSQL backends, where ALTER TABLE ... ADD
CONSTRAINT is unavailable and these FKs come from create_all() anyway.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.models.base import Base
from app.db.models.daily_plan import DailyPlan
from app.db.models.user import User

SCHEMA = "test_mig0036"
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0036_restore_missing_user_fks.py"
)

pytestmark = pytest.mark.skipif(
    "postgres" not in os.environ.get("DATABASE_URL", ""),
    reason="migration 0036 only alters PostgreSQL schemas",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig0036", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sync_url():
    url = os.environ["DATABASE_URL"]
    for prefix in ("postgresql+asyncpg://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix) :]
    return url.split("?")[0]


@pytest.fixture
def pg():
    """A schema holding the ORM tables MINUS the two FKs production is missing.

    That is production's exact drifted shape: every table present, the
    daily_plan/goals user FKs absent.
    """
    engine = sa.create_engine(
        _sync_url(),
        connect_args={"options": f"-csearch_path={SCHEMA}"},
    )
    with engine.begin() as conn:
        conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        conn.execute(sa.text(f"CREATE SCHEMA {SCHEMA}"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table in ("daily_plan", "goals"):
            for (name,) in conn.execute(
                sa.text(
                    """SELECT con.conname FROM pg_constraint con
                       JOIN pg_class src ON src.oid = con.conrelid
                       JOIN pg_class tgt ON tgt.oid = con.confrelid
                       JOIN pg_namespace ns ON ns.oid = src.relnamespace
                       WHERE con.contype='f' AND src.relname=:t
                         AND tgt.relname='users' AND ns.nspname=:s"""
                ),
                {"t": table, "s": SCHEMA},
            ):
                conn.execute(sa.text(f'ALTER TABLE {table} DROP CONSTRAINT "{name}"'))
    try:
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        engine.dispose()


def _run(engine, direction="upgrade"):
    module = _load_migration()
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            getattr(module, direction)()


def _user_fks(engine, table):
    """{constraint name: confdeltype} for <table>.user_id -> users, in SCHEMA."""
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                """SELECT con.conname, con.confdeltype FROM pg_constraint con
                   JOIN pg_class src ON src.oid = con.conrelid
                   JOIN pg_class tgt ON tgt.oid = con.confrelid
                   JOIN pg_namespace ns ON ns.oid = src.relnamespace
                   WHERE con.contype='f' AND src.relname=:t
                     AND tgt.relname='users' AND ns.nspname=:s"""
            ),
            {"t": table, "s": SCHEMA},
        ).all()
    return {name: deltype for name, deltype in rows}


def _seed_user(engine):
    uid = uuid.uuid4()
    with Session(engine) as s:
        s.add(
            User(
                id=uid,
                email=f"mig0036_{uid.hex[:8]}@example.invalid",
                password_hash="x",
            )
        )
        s.commit()
    return uid


def _seed_plan_rows(engine, uid, days=5):
    from datetime import datetime
    from decimal import Decimal

    with Session(engine) as s:
        for day in range(1, days + 1):
            s.add(
                DailyPlan(
                    id=uuid.uuid4(),
                    user_id=uid,
                    date=datetime(2026, 3, day),
                    category="groceries",
                    planned_amount=Decimal("10.00"),
                    spent_amount=Decimal("0.00"),
                    daily_budget=Decimal("10.00"),
                    status="green",
                )
            )
        s.commit()


def _count(engine, table, **where):
    clause = " AND ".join(f"{k} = :{k}" for k in where) or "true"
    with engine.connect() as conn:
        return conn.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {clause}"),  # nosec B608
            {k: str(v) for k, v in where.items()},
        ).scalar()


class TestFixtureReproducesProductionDrift:
    def test_daily_plan_and_goals_start_without_a_users_fk(self, pg):
        assert _user_fks(pg, "daily_plan") == {}
        assert _user_fks(pg, "goals") == {}

    def test_transactions_keeps_its_no_action_fk(self, pg):
        fks = _user_fks(pg, "transactions")
        assert len(fks) == 1
        # 'a' = NO ACTION. The model declares ForeignKey("users.id") with no
        # ondelete, and production matches. This is not drift and 0036 must
        # not change it: transactions are the ledger of record, so a stray
        # user delete must fail loudly rather than cascade history away.
        assert list(fks.values())[0] == "a"


class TestUpgradeAddsTheIntendedConstraints:
    def test_adds_cascade_fks_and_preserves_every_row(self, pg):
        uid = _seed_user(pg)
        _seed_plan_rows(pg, uid)
        before = _count(pg, "daily_plan")

        _run(pg, "upgrade")

        assert _user_fks(pg, "daily_plan") == {"fk_daily_plan_user_id": "c"}
        assert _user_fks(pg, "goals") == {"fk_goals_user_id": "c"}
        assert _count(pg, "daily_plan") == before

    def test_transactions_fk_is_untouched_by_the_upgrade(self, pg):
        before = _user_fks(pg, "transactions")
        _run(pg, "upgrade")
        assert _user_fks(pg, "transactions") == before

    def test_the_cascade_actually_fires(self, pg):
        uid = _seed_user(pg)
        _seed_plan_rows(pg, uid)
        _run(pg, "upgrade")

        with pg.begin() as conn:
            conn.execute(sa.text("DELETE FROM users WHERE id = :i"), {"i": str(uid)})

        assert (
            _count(pg, "daily_plan", user_id=uid) == 0
        ), "plan rows must follow their user; leaving them is the exact bug"


class TestUpgradeRefusesRatherThanDeletingData:
    def test_orphans_abort_the_migration_and_survive_it(self, pg):
        uid = _seed_user(pg)
        _seed_plan_rows(pg, uid)
        orphan = uuid.uuid4()  # a user id that does not exist
        _seed_plan_rows(pg, orphan, days=2)
        total_before = _count(pg, "daily_plan")

        with pytest.raises(RuntimeError, match="refuses to add foreign keys"):
            _run(pg, "upgrade")

        assert (
            _count(pg, "daily_plan", user_id=orphan) == 2
        ), "0022 deleted orphans; 0036 must not"
        assert _count(pg, "daily_plan") == total_before
        assert _user_fks(pg, "daily_plan") == {}, "no constraint on the failure path"

    def test_the_error_reports_how_many_rows_are_orphaned(self, pg):
        _seed_plan_rows(pg, uuid.uuid4(), days=3)
        with pytest.raises(RuntimeError, match=r"daily_plan: 3 row\(s\)"):
            _run(pg, "upgrade")

    @pytest.mark.parametrize("table", ["daily_plan", "goals"])
    def test_user_id_is_not_nullable_so_nulls_need_no_handling(self, pg, table):
        """Why 0036 does not check for NULL user_id.

        A NULL foreign-key value never violates an FK constraint, so NULLs
        could not block the migration even if they existed. They also cannot
        exist: the column is NOT NULL in the models and in production. Pinned
        here because if that ever changes, the migration's reasoning changes
        with it.
        """
        with pg.connect() as conn:
            nullable = conn.execute(
                sa.text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_schema=:s AND table_name=:t "
                    "AND column_name='user_id'"
                ),
                {"s": SCHEMA, "t": table},
            ).scalar()
        assert nullable == "NO"


class TestReversibleAndIdempotent:
    def test_downgrade_removes_only_what_upgrade_added(self, pg):
        tx_before = _user_fks(pg, "transactions")
        _run(pg, "upgrade")
        _run(pg, "downgrade")
        assert _user_fks(pg, "daily_plan") == {}
        assert _user_fks(pg, "goals") == {}
        assert _user_fks(pg, "transactions") == tx_before

    def test_upgrade_twice_is_a_no_op(self, pg):
        _run(pg, "upgrade")
        first = _user_fks(pg, "daily_plan")
        _run(pg, "upgrade")
        assert _user_fks(pg, "daily_plan") == first

    def test_downgrade_twice_is_a_no_op(self, pg):
        _run(pg, "upgrade")
        _run(pg, "downgrade")
        _run(pg, "downgrade")
        assert _user_fks(pg, "daily_plan") == {}

    def test_an_existing_differently_named_fk_is_left_alone(self, pg):
        with pg.begin() as conn:
            conn.execute(
                sa.text(
                    "ALTER TABLE daily_plan ADD CONSTRAINT legacy_dp_user_fk "
                    "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
                )
            )
        _run(pg, "upgrade")
        assert set(_user_fks(pg, "daily_plan")) == {
            "legacy_dp_user_fk"
        }, "must not stack a duplicate FK on a column that already has one"
