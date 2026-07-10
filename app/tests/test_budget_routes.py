import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.budget import routes as budget_routes


def make_async_db():
    """Mock AsyncSession whose run_sync executes the bridged sync callable.

    /spent and /remaining now wrap the sync BudgetTracker services in
    db.run_sync(lambda s: fetch(...)); the mock must run that lambda with a
    stand-in sync session so the test exercises the real bridge.
    """
    db = create_autospec(AsyncSession, instance=True)
    db.run_sync = AsyncMock(side_effect=lambda fn: fn(MagicMock()))
    return db


@pytest.mark.asyncio
async def test_spent_defaults_to_current_date(monkeypatch):
    captured = {}

    def dummy_fetch(db, user_id, year, month):
        captured["args"] = (year, month)
        return {"ok": True}

    monkeypatch.setattr(budget_routes, "fetch_spent_by_category", dummy_fetch)

    db = make_async_db()
    user = SimpleNamespace(id="u1")
    # Bypass isinstance(user, User) check
    monkeypatch.setattr(budget_routes, "User", type(user))

    now = datetime.now(timezone.utc)
    result = await budget_routes.spent(user=user, db=db)
    data = json.loads(result.body.decode())

    assert data["data"] == {"ok": True}
    assert captured["args"] == (now.year, now.month)


@pytest.mark.asyncio
async def test_remaining_accepts_custom_date(monkeypatch):
    captured = {}

    def dummy_fetch(db, user_id, year, month):
        captured["args"] = (year, month)
        return {"rem": True}

    monkeypatch.setattr(budget_routes, "fetch_remaining_budget", dummy_fetch)

    db = make_async_db()
    user = SimpleNamespace(id="u1")
    monkeypatch.setattr(budget_routes, "User", type(user))

    result = await budget_routes.remaining(year=2030, month=12, user=user, db=db)
    data = json.loads(result.body.decode())

    assert data["data"] == {"rem": True}
    assert captured["args"] == (2030, 12)
