import json
from types import SimpleNamespace

import pytest

from app.api.mood.routes import list_moods, log_mood
from app.api.mood.schemas import MoodIn
from app.db.models import Mood


class DummyDB:
    def __init__(self, record=None):
        self.added = []
        self.committed = False
        self.refreshed = []
        self.record = record
        self.queries = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)

    def query(self, model):
        assert model is Mood
        self.queries.append(model)
        return self

    def filter_by(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return [self.record] if self.record else []

    def first(self):
        return self.record


def parse_json(response):
    return json.loads(response.body.decode())


@pytest.mark.asyncio
async def test_log_mood_creates(monkeypatch):
    db = DummyDB()
    user = SimpleNamespace(id="u1")
    monkeypatch.setattr("app.api.mood.routes.Mood", Mood)
    resp = await log_mood(MoodIn(date="2025-01-01", mood="happy"), db=db, user=user)
    data = parse_json(resp)
    assert db.committed
    assert db.added
    assert data["data"]["mood"] == "happy"


@pytest.mark.asyncio
async def test_list_moods(monkeypatch):
    record = SimpleNamespace(id="m1", date="2025-01-01", mood="sad")
    db = DummyDB(record)
    user = SimpleNamespace(id="u1")
    resp = await list_moods(db=db, user=user)
    data = parse_json(resp)
    assert data["data"][0]["mood"] == "sad"
