import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.budget import routes as budget_routes


@pytest.mark.asyncio
async def test_spent_defaults_to_current_date(monkeypatch):
    captured = {}

    async def dummy_fetch(db, user_id, year, month):
        captured["args"] = (year, month)
        return {"ok": True}

    monkeypatch.setattr(budget_routes, "fetch_spent_by_category", dummy_fetch)
    monkeypatch.setattr(
        budget_routes, "get_current_user", lambda: SimpleNamespace(id="u1")
    )
    monkeypatch.setattr(budget_routes, "get_db", lambda: iter(["db"]))

    now = datetime.utcnow()
    result = await budget_routes.spent()
    data = json.loads(result.body.decode())

    assert data["data"] == {"ok": True}
    assert captured["args"] == (now.year, now.month)


@pytest.mark.asyncio
async def test_remaining_accepts_custom_date(monkeypatch):
    captured = {}

    async def dummy_fetch(db, user_id, year, month):
        captured["args"] = (year, month)
        return {"rem": True}

    monkeypatch.setattr(budget_routes, "fetch_remaining_budget", dummy_fetch)
    monkeypatch.setattr(
        budget_routes, "get_current_user", lambda: SimpleNamespace(id="u1")
    )
    monkeypatch.setattr(budget_routes, "get_db", lambda: iter(["db"]))

    result = await budget_routes.remaining(year=2030, month=12)
    data = json.loads(result.body.decode())

    assert data["data"] == {"rem": True}
    assert captured["args"] == (2030, 12)
