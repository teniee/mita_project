from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.core.engine.cron_task_subscription_refresh import (
    refresh_premium_status,
)


class DummyQuery:
    def __init__(self, items):
        self.items = items

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None


class DummyDB:
    def __init__(self, subs, user):
        self.subs = subs
        self.user = user
        self.committed = False

    def query(self, model):
        if model.__name__ == "Subscription":
            return DummyQuery(self.subs)
        return DummyQuery([self.user])

    def commit(self):
        self.committed = True


def test_refresh_premium_status_expires(monkeypatch):
    expired_sub = SimpleNamespace(
        user_id="u1",
        expires_at=datetime.utcnow() - timedelta(days=1),
        status="active",
    )
    user = SimpleNamespace(
        id="u1", is_premium=True, premium_until=expired_sub.expires_at
    )
    db = DummyDB([expired_sub], user)

    monkeypatch.setattr(
        "app.services.core.engine.cron_task_subscription_refresh.get_db",
        lambda: iter([db]),
    )

    refresh_premium_status()

    assert expired_sub.status == "expired"
    assert user.is_premium is False
    assert db.committed
