import datetime
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.habits.routes import create_habit, delete_habit, list_habits, update_habit
from app.api.habits.schemas import HabitIn, HabitUpdate


class DummyHabit:
    user_id = "u1"

    def __init__(self, **kw):
        self.id = "h1"
        self.title = kw.get("title", "")
        self.description = kw.get("description", "")
        self.target_frequency = kw.get("target_frequency", "daily")
        self.created_at = datetime.datetime(2025, 1, 1)
        for k, v in kw.items():
            setattr(self, k, v)


class AsyncDummyDB:
    """Async-compatible DummyDB for AsyncSession-based routes."""

    def __init__(self, record=None, all_items=None):
        self.added = []
        self.committed = False
        self.refreshed = []
        self.record = record
        self.all_items = all_items or []
        self.deleted_obj = None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed.append(obj)

    async def delete(self, obj):
        self.deleted_obj = obj

    async def execute(self, stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = self.all_items
        result.scalar_one_or_none.return_value = self.record
        return result


@pytest.mark.asyncio
async def test_create_and_list_habits(monkeypatch):
    monkeypatch.setattr("app.api.habits.routes.Habit", DummyHabit)

    async def fake_get_habit_with_stats(habit, user_id, db):
        return {"title": habit.title, "description": habit.description}

    monkeypatch.setattr(
        "app.api.habits.routes.get_habit_with_stats", fake_get_habit_with_stats
    )

    db = AsyncDummyDB()
    user = SimpleNamespace(id="u1")

    result = await create_habit(HabitIn(title="T", description="D"), user=user, db=db)
    data = json.loads(result.body.decode())
    assert isinstance(db.added[0], DummyHabit)
    assert db.committed
    assert data["data"]["title"] == "T"

    habit_obj = db.added[0]
    db2 = AsyncDummyDB(all_items=[habit_obj])
    # list_habits uses select(Habit) which needs a real model,
    # so monkeypatch select to return a mock statement
    monkeypatch.setattr("app.api.habits.routes.select", lambda *a: MagicMock())
    result2 = await list_habits(user=user, db=db2)
    data2 = json.loads(result2.body.decode())
    assert len(data2["data"]) == 1
    assert data2["data"][0]["title"] == "T"


@pytest.mark.asyncio
async def test_update_and_delete_habit(monkeypatch):
    habit = DummyHabit(title="Old", description="Old")
    db = AsyncDummyDB(record=habit)

    async def fake_get_habit_with_stats(h, user_id, session):
        return {"status": "updated", "title": h.title}

    monkeypatch.setattr(
        "app.api.habits.routes.get_habit_with_stats", fake_get_habit_with_stats
    )
    monkeypatch.setattr("app.api.habits.routes.select", lambda *a: MagicMock())
    monkeypatch.setattr("app.api.habits.routes.and_", lambda *a: MagicMock())

    user = SimpleNamespace(id="u1")
    result = await update_habit("h1", HabitUpdate(title="New"), user=user, db=db)
    data = json.loads(result.body.decode())
    assert data["data"]["status"] == "updated"
    assert habit.title == "New"

    db2 = AsyncDummyDB(record=habit)
    result2 = await delete_habit("h1", user=user, db=db2)
    data2 = json.loads(result2.body.decode())
    assert data2["data"]["status"] == "deleted"
    assert db2.committed
