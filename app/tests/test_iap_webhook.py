from types import SimpleNamespace

import pytest

from app.api.iap.routes import iap_webhook


class DummyQuery:
    def __init__(self, item):
        self.item = item

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.item


class DummyDB:
    def __init__(self, sub, user):
        self.sub = sub
        self.user = user
        self.committed = False

    def query(self, model):
        if model.__name__ == "Subscription":
            return DummyQuery(self.sub)
        return DummyQuery(self.user)

    def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_iap_webhook(monkeypatch):
    sub = SimpleNamespace(expires_at=None)
    user = SimpleNamespace(id="u1", is_premium=False, premium_until=None)
    db = DummyDB(sub, user)

    monkeypatch.setattr(
        "app.api.iap.routes.success_response", lambda data=None, message="": data
    )

    result = await iap_webhook(
        {"user_id": "u1", "expires_at": "2025-01-01T00:00:00"}, db=db
    )

    assert result["received"] is True
    assert sub.expires_at.isoformat() == "2025-01-01T00:00:00"
    assert user.is_premium is True
    assert user.premium_until.isoformat() == "2025-01-01T00:00:00"
    assert db.committed
