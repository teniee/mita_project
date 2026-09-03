"""Regression: cohort spending must not count transactions the user deleted.

Device-reproduced during the pre-launch pass. A user created a $5 food expense,
edited it to $8, then deleted it, leaving a single $200 transaction. The ledger,
dashboard and calendar all agreed the month's spend was $200.00 — but the Peer
Insights screen said "Your Spending $208", because
``app/api/cohort/routes.py`` summed ``Transaction.amount`` with no
``deleted_at`` filter, so the deleted $8 was still counted.

The peer-side sum had the same omission, which would inflate every other
user's average too.

Requires: PostgreSQL at DATABASE_URL with migrations at head.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Transaction, User


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
def user(db_session):
    u = User(
        id=uuid4(),
        email=f"cohortdel_{uuid4().hex[:10]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.query(Transaction).filter_by(user_id=u.id).delete()
    db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


@pytest.fixture
def authed(client, user):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def ledger(db_session, user):
    """One live $200 transaction and one deleted $8 transaction."""
    now = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.add(
        Transaction(
            id=uuid4(),
            user_id=user.id,
            category="transportation",
            amount=Decimal("200.00"),
            spent_at=now,
        )
    )
    db_session.add(
        Transaction(
            id=uuid4(),
            user_id=user.id,
            category="food",
            amount=Decimal("8.00"),
            spent_at=now,
            deleted_at=now,
        )
    )
    db_session.commit()


def test_peer_comparison_ignores_deleted_transactions(authed, ledger):
    resp = authed.get("/api/cohort/peer_comparison?year=2026&month=8")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["your_spending"] == pytest.approx(
        200.00
    ), "the deleted $8 expense must not be counted as spending"


def test_cohort_insights_ignores_deleted_transactions(authed, ledger):
    resp = authed.get("/api/cohort/insights")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["peer_comparison"]["user_spending"] == pytest.approx(200.00)


def test_peer_comparison_reports_insufficient_data_rather_than_zeros(authed, ledger):
    # With no other users in the income bracket the endpoint must say so
    # explicitly — the client relies on these exact fields to avoid rendering
    # a $0 peer average and a made-up percentile.
    resp = authed.get("/api/cohort/peer_comparison?year=2026&month=8")
    data = resp.json()["data"]
    if data["peer_count"] == 0:
        assert data["comparison"] == "insufficient_peer_data"
        assert data["peer_average"] is None
        assert data["percentile"] is None
