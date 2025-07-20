import datetime
from types import SimpleNamespace

import pytest

from app.api.analytics import routes as analytics_routes


@pytest.mark.asyncio
async def test_trend_default(monkeypatch):
    monkeypatch.setattr(
        "app.api.analytics.routes.success_response", lambda data=None, message="": data
    )
    monkeypatch.setattr(
        analytics_routes,
        "get_trend",
        lambda *a, **k: [
            {"date": f"2025-01-{i:02d}", "amount": 1.0} for i in range(400)
        ],
    )
    user = SimpleNamespace(id="u1")
    result = await analytics_routes.trend(user=user, db=None)
    assert len(result["trend"]) == 365


@pytest.mark.asyncio
async def test_trend_custom_window(monkeypatch):
    captured = {}

    def fake(uid, db, start_date=None, end_date=None):
        captured["args"] = (start_date, end_date)
        return []

    monkeypatch.setattr(analytics_routes, "get_trend", fake)
    monkeypatch.setattr(
        "app.api.analytics.routes.success_response", lambda data=None, message="": data
    )
    user = SimpleNamespace(id="u1")
    start = datetime.date(2025, 1, 1)
    end = datetime.date(2025, 1, 31)
    result = await analytics_routes.trend(start, end, user=user, db=None)
    assert result["trend"] == []
    assert captured["args"] == (start, end)


@pytest.mark.asyncio
async def test_trend_pagination(monkeypatch):
    monkeypatch.setattr(
        analytics_routes,
        "get_trend",
        lambda *a, **k: [
            {"date": f"2025-01-{i:02d}", "amount": float(i)} for i in range(30)
        ],
    )
    monkeypatch.setattr(
        "app.api.analytics.routes.success_response", lambda data=None, message="": data
    )
    user = SimpleNamespace(id="u1")
    result = await analytics_routes.trend(limit=10, offset=10, user=user, db=None)
    assert [r["amount"] for r in result["trend"]] == list(range(10, 20))
