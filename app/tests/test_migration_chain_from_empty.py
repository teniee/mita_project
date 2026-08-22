"""An empty PostgreSQL database must reach the supported head automatically.

Production's schema diverged from its own migration history: alembic_version
read 0035 while several of 0022's constraints were absent. Nothing in CI would
have noticed, because no test ever built a database the way a new environment
would. This does.

It also pins the two properties that make the divergence detectable:
  - the chain reaches head unaided, from nothing
  - the resulting schema carries the constraints the migrations promise

Needs CREATE DATABASE. A schema with search_path is NOT a substitute: migration
0008 probes information_schema.columns for table_name='users' without a
table_schema filter, so under a non-public search_path it sees another schema's
users table, skips adding has_onboarded, and the next create_index fails. That
false failure is what made this look like a broken chain in the first place.
"""

import os
import subprocess
import sys
import uuid

import psycopg2
import pytest
import sqlalchemy as sa

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _repo_head() -> str:
    """The single head in alembic/versions.

    Derived, never hardcoded: a literal here goes stale the moment a migration
    lands and turns a correct chain into a red test (it already did once).
    """
    import re

    versions = os.path.join(REPO, "alembic", "versions")
    revisions, down = {}, set()
    for name in os.listdir(versions):
        if not name.endswith(".py"):
            continue
        text = open(
            os.path.join(versions, name), encoding="utf-8", errors="ignore"
        ).read()
        m = re.search(r"^revision\s*=\s*[\"']([^\"']+)", text, re.M)
        d = re.search(r"^down_revision\s*=\s*[\"']([^\"']+)", text, re.M)
        if m:
            revisions[m.group(1)] = name
        if d:
            down.add(d.group(1))
    heads = [r for r in revisions if r not in down]
    assert len(heads) == 1, f"expected exactly one head, found {sorted(heads)}"
    return heads[0]


EXPECTED_HEAD = _repo_head()


def _admin_url():
    url = os.environ.get("DATABASE_URL", "")
    for prefix in ("postgresql+asyncpg://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix) :]
    return url.split("?")[0].rsplit("/", 1)[0] + "/postgres"


def _can_create_database():
    try:
        conn = psycopg2.connect(_admin_url(), connect_timeout=5)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "select usesuper or usecreatedb from pg_user where usename=current_user"
        )
        allowed = bool(cur.fetchone()[0])
        conn.close()
        return allowed
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(
        "postgres" not in os.environ.get("DATABASE_URL", ""),
        reason="migration chain is PostgreSQL-only",
    ),
    pytest.mark.skipif(
        not _can_create_database(),
        reason="needs a role with CREATE DATABASE; a schema is not a substitute",
    ),
]


@pytest.fixture
def empty_database():
    name = f"mita_chain_{uuid.uuid4().hex[:10]}"
    admin = psycopg2.connect(_admin_url())
    admin.autocommit = True
    admin.cursor().execute(f'CREATE DATABASE "{name}"')
    url = _admin_url().rsplit("/", 1)[0] + "/" + name
    try:
        yield url
    finally:
        admin.cursor().execute(
            "select pg_terminate_backend(pid) from pg_stat_activity where datname=%s",
            (name,),
        )
        admin.cursor().execute(f'DROP DATABASE IF EXISTS "{name}"')
        admin.close()


def _alembic(url, *args):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": url},
        timeout=900,
    )


def _inspect(url):
    engine = sa.create_engine(url)
    insp = sa.inspect(engine)
    return engine, insp


def test_empty_database_reaches_head_unaided(empty_database):
    result = _alembic(empty_database, "upgrade", "head")
    assert result.returncode == 0, (
        "a new environment cannot be built from migration history:\n"
        + (result.stdout + result.stderr)[-3000:]
    )

    engine, insp = _inspect(empty_database)
    try:
        tables = set(insp.get_table_names())
        assert "alembic_version" in tables
        assert len(tables) > 25, f"suspiciously few tables: {sorted(tables)}"
        with engine.connect() as conn:
            head = conn.execute(
                sa.text("select version_num from alembic_version")
            ).scalar()
        assert head == EXPECTED_HEAD, f"reached {head}, expected {EXPECTED_HEAD}"
    finally:
        engine.dispose()


def test_the_chain_delivers_the_constraints_it_promises(empty_database):
    """The specific constraints production was missing must exist here.

    If this passes while production lacks them, the difference is operational,
    not a defect in the migrations - which is exactly the distinction that took
    an audit to establish the first time.
    """
    assert _alembic(empty_database, "upgrade", "head").returncode == 0
    engine, _ = _inspect(empty_database)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    """select s.relname, con.conname, con.confdeltype
                   from pg_constraint con
                   join pg_class s on s.oid = con.conrelid
                   join pg_class t on t.oid = con.confrelid
                   where con.contype='f' and t.relname='users'"""
                )
            ).all()
        by_table = {r[0]: (r[1], r[2]) for r in rows}

        # from 0022, absent in production - the drift this all started with
        assert by_table["daily_plan"][1] == "c", "daily_plan.user_id must CASCADE"
        assert by_table["goals"][1] == "c", "goals.user_id must CASCADE"
        # NOTE: transactions deliberately not asserted here. A chain-built
        # database has NO transactions->users FK at all, while production has
        # one (NO ACTION, from create_all via the model). That three-way
        # divergence is owned by test_schema_equivalence.py, which compares
        # models / chain-built / production-shaped rather than spot-checking.

        with engine.connect() as conn:
            has_deleted_at = conn.execute(
                sa.text(
                    "select count(*) from information_schema.columns "
                    "where table_schema='public' and table_name='subscriptions' "
                    "and column_name='deleted_at'"
                )
            ).scalar()
        assert has_deleted_at == 1, "0022's subscriptions.deleted_at is missing"
    finally:
        engine.dispose()


def test_chain_is_idempotent_at_head(empty_database):
    assert _alembic(empty_database, "upgrade", "head").returncode == 0
    again = _alembic(empty_database, "upgrade", "head")
    assert again.returncode == 0
    assert "Running upgrade" not in (again.stdout + again.stderr)
