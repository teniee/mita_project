import importlib
import json
import sys
from types import SimpleNamespace

if isinstance(sys.modules.get("app.db.models"), object) and not hasattr(
    sys.modules.get("app.db.models"), "PushToken"
):
    sys.modules.pop("app.db.models", None)
    importlib.import_module("app.db.models")

import pytest

from app.api.notifications.routes import register_token, send_test_notification
from app.api.notifications.schemas import NotificationTest, TokenIn
from app.db.models import PushToken


class DummyDB:
    def __init__(self, record=None):
        self.added = []
        self.committed = False
        self.refreshed = []
        self.record = record

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed.append(obj)

    def query(self, model):
        assert model is PushToken
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.record


class DummyToken:
    def __init__(self, user_id, token):
        self.id = "t123"
        self.user_id = user_id
        self.token = token
        self.created_at = None


def parse_json(response):
    return json.loads(response.body.decode())


@pytest.mark.asyncio
async def test_register_token(monkeypatch):
    monkeypatch.setattr(
        "app.api.notifications.routes.PushToken",
        DummyToken,
    )
    db = DummyDB()
    user = SimpleNamespace(id="u1")

    resp = await register_token(TokenIn(token="abc"), db=db, user=user)
    payload = parse_json(resp)

    assert db.committed
    assert isinstance(db.added[0], DummyToken)
    assert payload["success"] is True
    assert payload["data"]["token"] == "abc"


@pytest.mark.asyncio
async def test_send_test_notification(monkeypatch):
    sent = {}

    def fake_push(user_id, message, token, **kwargs):
        sent["push"] = (user_id, message, token)

    def fake_email(email, subject, body, **kwargs):
        sent["email"] = (email, subject, body)

    monkeypatch.setattr(
        "app.api.notifications.routes.send_push_notification", fake_push
    )
    monkeypatch.setattr(
        "app.api.notifications.routes.send_reminder_email",
        fake_email,
    )

    db = DummyDB()
    user = SimpleNamespace(id="u1", email="u@example.com")

    resp = await send_test_notification(
        NotificationTest(message="hi", token="tok", email="e@mail.com"),
        db=db,
        user=user,
    )
    data = parse_json(resp)
    assert data["data"]["sent"] is True
    assert sent["push"] == ("u1", "hi", "tok")
    assert sent["email"] == ("e@mail.com", "Mita Notification", "hi")


@pytest.mark.asyncio
async def test_send_test_notification_fetches_token(monkeypatch):
    record = DummyToken("u1", "dbtoken")
    db = DummyDB(record)
    user = SimpleNamespace(id="u1", email="u@example.com")
    sent = {}
    monkeypatch.setattr(
        "app.api.notifications.routes.send_push_notification",
        lambda *a, **k: sent.setdefault(
            "push",
            (
                k.get("user_id"),
                k.get("message"),
                k.get("token"),
            ),
        ),
    )
    monkeypatch.setattr(
        "app.api.notifications.routes.send_reminder_email",
        lambda *a, **k: sent.setdefault("email", a),
    )
    resp = await send_test_notification(
        NotificationTest(message="hi"),
        db=db,
        user=user,
    )
    data = parse_json(resp)
    assert data["data"]["sent"] is True
    assert sent.get("push") == ("u1", "hi", "dbtoken")
    assert sent.get("email")[0] == "u@example.com"
