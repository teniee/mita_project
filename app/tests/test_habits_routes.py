import datetime
from types import SimpleNamespace

from app.api.habits.routes import create_habit, delete_habit, list_habits, update_habit
from app.api.habits.schemas import HabitIn, HabitUpdate


class DummyHabit:
    user_id = "u1"

    def __init__(self, **kw):
        self.id = "h1"
        self.created_at = datetime.datetime(2025, 1, 1)
        for k, v in kw.items():
            setattr(self, k, v)


class DummyDB:
    def __init__(self, record=None, all_items=None):
        self.added = []
        self.committed = False
        self.refreshed = []
        self.record = record
        self.all_items = all_items or []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.record

    def all(self):
        return self.all_items

    def delete(self, obj):
        self.deleted = obj


def test_create_and_list_habits(monkeypatch):
    monkeypatch.setattr("app.api.habits.routes.Habit", DummyHabit)
    monkeypatch.setattr(
        "app.api.habits.routes.success_response", lambda data=None, message="": data
    )
    db = DummyDB()
    user = SimpleNamespace(id="u1")

    result = create_habit(HabitIn(title="T", description="D"), user=user, db=db)
    assert isinstance(db.added[0], DummyHabit)
    assert db.committed
    assert result["title"] == "T"

    db2 = DummyDB(all_items=[db.added[0]])
    out = list_habits(user=user, db=db2)
    assert len(out) == 1
    assert out[0]["title"] == "T"


def test_update_and_delete_habit(monkeypatch):
    habit = DummyHabit(title="Old", description="Old")
    db = DummyDB(record=habit)
    monkeypatch.setattr(
        "app.api.habits.routes.success_response", lambda data=None, message="": data
    )

    user = SimpleNamespace(id="u1")
    result = update_habit("h1", HabitUpdate(title="New"), user=user, db=db)
    assert result["status"] == "updated"
    assert habit.title == "New"

    result = delete_habit("h1", user=user, db=db)
    assert result["status"] == "deleted"
    assert db.committed
