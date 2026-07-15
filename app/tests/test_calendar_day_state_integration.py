"""POST /api/calendar/day_state with REAL DailyPlan rows.

The route-contract suite exercises this endpoint with a data-less user, so
it always took the early "calendar not found" return. With saved rows the
old implementation iterated get_calendar_for_user()'s {date: {category:
planned}} dict as a LIST of shell-day maps and called .get on the string
keys — AttributeError -> 500 for exactly the users who had data.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import DailyPlan, User


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
        email=f"daystate_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.query(DailyPlan).filter_by(user_id=u.id).delete()
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


TODAY = datetime.now(timezone.utc).date()


def _seed_plan(db_session, user, category, planned, spent, day=None):
    row = DailyPlan(
        user_id=user.id,
        date=day or TODAY,
        category=category,
        planned_amount=Decimal(planned),
        daily_budget=Decimal(planned),
        spent_amount=Decimal(spent),
    )
    db_session.add(row)
    db_session.commit()
    return row


def _post_day_state(authed, day: date):
    return authed.post(
        "/api/calendar/day_state",
        json={"year": day.year, "month": day.month, "day": day.day},
    )


class TestDayStateWithRealRows:
    def test_returns_planned_actual_and_green_status(
        self, authed, db_session, user
    ):
        _seed_plan(db_session, user, "coffee", "5.40", "0.00")
        _seed_plan(db_session, user, "groceries", "12.52", "3.00")

        resp = _post_day_state(authed, TODAY)

        assert resp.status_code == 200, resp.text
        state = resp.json()["data"]["state"]
        assert state.get("error") is None
        assert state["planned"] == {"coffee": 5.4, "groceries": 12.52}
        assert state["actual"] == {"coffee": 0.0, "groceries": 3.0}
        assert state["status"] == "green"

    def test_overspent_day_reports_red(self, authed, db_session, user):
        _seed_plan(db_session, user, "food", "10.00", "25.00")

        resp = _post_day_state(authed, TODAY)

        assert resp.status_code == 200, resp.text
        state = resp.json()["data"]["state"]
        assert state["status"] == "red"
        # yellow/red paths attach the advisor comment (or its fallback) —
        # the key must exist even when the AI service is unavailable.
        assert "advisor_comment" in state

    def test_day_without_rows_reports_day_not_found(
        self, authed, db_session, user
    ):
        _seed_plan(db_session, user, "coffee", "5.40", "0.00")
        other_day = TODAY.replace(day=1 if TODAY.day != 1 else 2)

        resp = _post_day_state(authed, other_day)

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["state"] == {"error": "day not found"}

    def test_month_without_rows_reports_calendar_not_found(self, authed):
        resp = authed.post(
            "/api/calendar/day_state",
            json={"year": 2001, "month": 1, "day": 15},
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["state"] == {"error": "calendar not found"}
