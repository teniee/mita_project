from types import SimpleNamespace

import pytest

from app.api.goals import routes as goals_routes
from app.api.plan import routes as plan_routes


class DummyDB:
    def __init__(self, record=None, rows=None):
        self.record = record
        self.rows = rows or []

    # For goals routes
    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.record

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed = obj

    def add(self, obj):
        self.added = obj

    def delete(self, obj):
        self.deleted = obj

    # For plan route
    def all(self):
        return self.rows


def test_update_goal_not_found(monkeypatch):
    monkeypatch.setattr(
        "app.api.goals.routes.success_response", lambda data=None, message="": data
    )
    db = DummyDB(record=None)
    user = SimpleNamespace(id="u1")
    with pytest.raises(goals_routes.HTTPException) as exc:
        goals_routes.update_goal("g1", goals_routes.GoalUpdate(), user=user, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_plan_month_not_found(monkeypatch):
    monkeypatch.setattr(
        "app.api.plan.routes.success_response", lambda data=None, message="": data
    )

    class DummyQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class DummyDB2:
        def query(self, model):
            return DummyQuery()

    user = SimpleNamespace(id="u1")
    with pytest.raises(plan_routes.HTTPException) as exc:
        await plan_routes.plan_month(2025, 1, user=user, db=DummyDB2())
    assert exc.value.status_code == 404


def test_create_goal_requires_premium(monkeypatch):
    monkeypatch.setattr(
        "app.api.goals.routes.success_response", lambda data=None, message="": data
    )

    class DummyGoal:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.id = "g1"
            self.saved_amount = 0

    monkeypatch.setattr("app.api.goals.routes.Goal", DummyGoal)
    user = SimpleNamespace(id="u1", is_premium=False)
    db = DummyDB(record=None)
    with pytest.raises(goals_routes.HTTPException) as exc:
        goals_routes.require_premium_user(user)
    assert exc.value.status_code == 402
