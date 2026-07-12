"""Regression: subscription reads must not reference a column production lacks.

Production's `subscriptions` table has no `deleted_at` column. The model used
to declare `deleted_at = Column(...)` anyway (migration 0022 adds it, but that
add was appended to 0022 *after* prod had already stamped past 0022, so the
live table never got the column). Every `db.query(Subscription)` therefore
emitted `SELECT ... subscriptions.deleted_at` and 500'd in production
(psycopg2 UndefinedColumn) on:

  * GET /api/iap/status                       (app restore / entitlement check)
  * GET /api/users/{id}/premium-status
  * GET /api/users/{id}/premium-features
  * GET /api/users/{id}/subscription-history

This test drops the column to reproduce the production schema exactly, then
exercises the read path and asserts a real 200 with correct entitlement
content. It fails (500) against the pre-fix model and passes once the model
stops mapping `deleted_at`.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.models import User
from app.db.models.subscription import Subscription


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db_session():
    import app.core.session as session_module

    gen = session_module.get_db()
    db = next(gen)
    try:
        yield db
    finally:
        gen.close()


@pytest.fixture
def prod_like_subscriptions(db_session):
    """Match the live schema: subscriptions without a deleted_at column."""
    db_session.execute(
        text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS deleted_at")
    )
    db_session.commit()
    yield
    # Restore for any later test that provisioned against head.
    db_session.execute(
        text(
            "ALTER TABLE subscriptions "
            "ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL"
        )
    )
    db_session.commit()


@pytest.fixture
def premium_user(db_session):
    u = User(
        id=uuid4(),
        email=f"iapdrift_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        timezone="UTC",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

    sub = Subscription(
        id=uuid4(),
        user_id=u.id,
        platform="ios",
        plan="annual",
        receipt={"token": "stub"},
        status="active",
        product_id="com.mita.premium.annual",
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(sub)
    db_session.commit()

    yield u

    db_session.query(Subscription).filter_by(user_id=u.id).delete()
    db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


def test_deleted_at_not_mapped_on_subscription_model():
    """Guard: the column that does not exist in production must stay unmapped."""
    cols = {c.name for c in Subscription.__table__.columns}
    assert "deleted_at" not in cols, (
        "Subscription must not map deleted_at — production's subscriptions "
        "table lacks it and every query would 500 (UndefinedColumn)."
    )


def test_iap_status_200_without_deleted_at_column(
    client, prod_like_subscriptions, premium_user
):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: premium_user
    try:
        resp = client.get("/api/iap/status")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    data = body.get("data", body)
    assert data["subscription"] is not None
    assert data["subscription"]["platform"] == "ios"
    assert data["subscription"]["plan"] == "annual"
