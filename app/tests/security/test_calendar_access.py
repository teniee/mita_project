import pytest
from types import SimpleNamespace

from app.api.calendar import routes as calendar_routes


@pytest.mark.asyncio
async def test_get_day_view_success(monkeypatch):
    # stub success_response to return raw data
    monkeypatch.setattr(
        "app.api.calendar.routes.success_response",
        lambda data=None, message="": data,
    )

    # stub fetch_calendar to return a day entry
    def dummy_fetch(uid, year, month):
        return {1: {"total": 0}}

    monkeypatch.setattr(calendar_routes, "fetch_calendar", dummy_fetch)

    user = SimpleNamespace(id="u1")
    result = await calendar_routes.get_day_view(2025, 1, 1, user=user)
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_get_day_view_missing_day(monkeypatch):
    # stub success_response
    monkeypatch.setattr(
        "app.api.calendar.routes.success_response",
        lambda data=None, message="": data,
    )

    # stub fetch_calendar to return an empty dict (day not found)
    monkeypatch.setattr(calendar_routes, "fetch_calendar", lambda *a, **k: {})

    user = SimpleNamespace(id="u1")
    with pytest.raises(calendar_routes.HTTPException) as exc:
        await calendar_routes.get_day_view(2025, 1, 1, user=user)

    assert exc.value.status_code == 404
