"""Regression guards for the TASK-18 schema-cleanup branch.

These assert the ORM models declare the corrected shapes and that migration
0036 is present and chained. They fail against the pre-cleanup models, so
they pin the fix without needing a live database.

The migration itself (0036) is owner-gated and applied in a migration
window; a full apply/round-trip test belongs in the DB-backed suite.
"""

import re
from pathlib import Path

import sqlalchemy as sa

from app.db.models.notification import Notification
from app.db.models.push_token import PushToken

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _column(model, name):
    return model.__table__.columns[name]


def test_notification_retry_count_is_integer_with_server_default():
    col = _column(Notification, "retry_count")
    assert isinstance(col.type, sa.Integer), (
        "retry_count must be Integer, not String — it is a numeric retry counter"
    )
    assert col.server_default is not None, "retry_count needs a DB server_default"
    assert col.server_default.arg == "0"


def test_push_token_platform_has_server_default():
    col = _column(PushToken, "platform")
    assert col.server_default is not None, (
        "push_tokens.platform needs a DB-level default so raw inserts that omit "
        "it do not violate NOT NULL"
    )
    assert col.server_default.arg == "fcm"


def test_migration_0036_present_and_chained():
    files = list(VERSIONS.glob("0036_*.py"))
    assert len(files) == 1, "exactly one 0036 migration expected"
    text = files[0].read_text()
    assert re.search(r"^revision\s*=\s*['\"]0036['\"]", text, re.M)
    assert re.search(r"^down_revision\s*=\s*['\"]0035['\"]", text, re.M)


def test_migration_0036_covers_all_three_items():
    text = (VERSIONS / "0036_task18_schema_cleanup.py").read_text()
    # push_tokens.platform default
    assert "push_tokens" in text and 'server_default="fcm"' in text
    # retry_count String -> Integer
    assert "retry_count" in text and "TYPE INTEGER" in text
    # enum CHECK constraints named per column and created in a loop
    assert 'ck_notifications_{column}_enum' in text
    assert "create_check_constraint" in text
    for column in ("type", "priority", "status"):
        assert f'"{column}"' in text
