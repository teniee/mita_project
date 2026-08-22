"""Guard the three definitions of "the schema" against drifting further apart.

Production ran for months with alembic_version reading 0035 while several of
migration 0022's constraints were absent, and no test noticed. The reason is
structural: three artifacts each claim to define the schema, and nothing
compared them.

    1. the SQLAlchemy models   -> what create_all() builds
    2. the migration chain     -> what `alembic upgrade head` builds
    3. the live database       -> what actually exists

In this project 1 and 2 currently differ in 187 ways, mostly server defaults
and ON DELETE clauses the models never declared. Fixing all of that at once
would be a large, risky change unrelated to any current defect, so this file
does the useful thing instead: it FREEZES the known difference set and fails
when a NEW one appears. Legacy drift is tolerated; fresh drift is not.

Requires a role with CREATE DATABASE. A schema with search_path is not a
substitute - migration 0008 queries information_schema without a table_schema
filter, so under a non-public search_path it reads another schema's tables.
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg2
import pytest
import sqlalchemy as sa

from app.tests.schema_equivalence import (
    diff,
    fingerprint_inspector,
    fingerprint_metadata,
)

REPO = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).parent / "schema_drift_baseline.json"


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
        reason="schema comparison is PostgreSQL-only",
    ),
    pytest.mark.skipif(
        not _can_create_database(),
        reason="needs a role with CREATE DATABASE",
    ),
]


class _Scratch:
    """A throwaway database, dropped on exit."""

    def __init__(self, tag):
        self.name = f"mita_schema_{tag}_{uuid.uuid4().hex[:8]}"
        self.admin = psycopg2.connect(_admin_url())
        self.admin.autocommit = True
        self.admin.cursor().execute(f'CREATE DATABASE "{self.name}"')
        self.url = _admin_url().rsplit("/", 1)[0] + "/" + self.name

    def close(self):
        self.admin.cursor().execute(
            "select pg_terminate_backend(pid) from pg_stat_activity where datname=%s",
            (self.name,),
        )
        self.admin.cursor().execute(f'DROP DATABASE IF EXISTS "{self.name}"')
        self.admin.close()


@pytest.fixture(scope="module")
def built_schemas():
    """(model-built fingerprint, migration-built fingerprint)."""
    import app.db.models  # noqa: F401  registers every mapper
    from app.db.models.base import Base

    model_db = _Scratch("model")
    chain_db = _Scratch("chain")
    engines = []
    try:
        eng = sa.create_engine(model_db.url)
        engines.append(eng)
        Base.metadata.create_all(eng)

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=REPO,
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": chain_db.url},
            timeout=900,
        )
        assert result.returncode == 0, (
            "migration chain failed:\n" + (result.stdout + result.stderr)[-2500:]
        )
        eng2 = sa.create_engine(chain_db.url)
        engines.append(eng2)

        yield (
            fingerprint_inspector(sa.inspect(eng)),
            fingerprint_inspector(sa.inspect(eng2)),
            Base.metadata,
        )
    finally:
        for e in engines:
            e.dispose()
        model_db.close()
        chain_db.close()


def test_models_round_trip_through_create_all(built_schemas):
    """The comparator's own correctness gate.

    metadata -> create_all -> inspect must be the identity. If this drifts, the
    tool is producing false positives and no other result here can be trusted.
    """
    model_fp, _chain_fp, metadata = built_schemas
    problems = diff(fingerprint_metadata(metadata), model_fp, "metadata", "created")
    assert problems == [], (
        "the fingerprint is not stable across create_all, so it cannot be used "
        "to judge anything else:\n  " + "\n  ".join(problems[:20])
    )


def test_no_new_drift_between_models_and_migrations(built_schemas):
    """Legacy drift is frozen; new drift fails.

    If this fails after a model or migration change, the two definitions have
    moved apart in a way nobody recorded. Either make them agree, or - if the
    difference is deliberate - regenerate the baseline and say why in the
    commit message.
    """
    model_fp, chain_fp, _ = built_schemas
    current = set(diff(model_fp, chain_fp, "create_all", "migrations"))
    known = set(json.loads(BASELINE.read_text())["differences"])

    new = sorted(current - known)
    assert (
        not new
    ), f"{len(new)} NEW model/migration difference(s) appeared:\n  " + "\n  ".join(
        new[:25]
    )


def test_baseline_does_not_silently_rot(built_schemas):
    """Differences that got fixed must leave the baseline.

    Without this the baseline only ever grows and stops meaning anything.
    """
    model_fp, chain_fp, _ = built_schemas
    current = set(diff(model_fp, chain_fp, "create_all", "migrations"))
    known = set(json.loads(BASELINE.read_text())["differences"])

    resolved = sorted(known - current)
    assert not resolved, (
        f"{len(resolved)} baselined difference(s) no longer exist - good news. "
        "Regenerate app/tests/schema_drift_baseline.json:\n  "
        + "\n  ".join(resolved[:25])
    )


def test_foreign_keys_to_users_are_explicitly_accounted_for(built_schemas):
    """ON DELETE decides what happens to a user's data. Nothing here by accident.

    Every users FK difference between the models and the migrations must be in
    the baseline with a recorded intent, because these are the constraints that
    determine whether deleting a user destroys financial history or leaves
    orphans behind.
    """
    model_fp, chain_fp, _ = built_schemas
    fk_diffs = [
        d
        for d in diff(model_fp, chain_fp, "create_all", "migrations")
        if ": fk in" in d and "'users'" in d
    ]
    known = set(json.loads(BASELINE.read_text())["differences"])
    unaccounted = sorted(set(fk_diffs) - known)
    assert not unaccounted, (
        "users foreign key differs between models and migrations without a "
        "recorded decision:\n  " + "\n  ".join(unaccounted)
    )
