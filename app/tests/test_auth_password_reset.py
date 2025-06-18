import json

import pytest

from app.api.auth.routes import (
    password_reset_confirm,
    password_reset_request,
    verify_email,
)
from app.api.auth.schemas import (
    EmailVerifyIn,
    PasswordResetConfirm,
    PasswordResetRequest,
)
from app.db.models import PasswordResetToken, User


class DummyQuery:
    def __init__(self, record):
        self.record = record

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self.record


class DummyDB:
    def __init__(self, user=None, token=None):
        self.user = user
        self.token = token
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def query(self, model):
        if model is User:
            return DummyQuery(self.user)
        return DummyQuery(self.token)


class DummyUser:
    def __init__(self, email="e@mail.com"):
        self.id = "u1"
        self.email = email
        self.password_hash = "old"
        self.is_email_verified = False


class DummyToken:
    def __init__(self, user_id, token):
        self.user_id = user_id
        self.token = token
        self.used = False


def parse_json(resp):
    return json.loads(resp.body.decode())


@pytest.mark.asyncio
async def test_password_reset_request(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        "app.api.auth.routes.send_password_reset_email",
        lambda addr, tok: sent.setdefault("email", (addr, tok)),
    )
    user = DummyUser()
    db = DummyDB(user=user)
    resp = await password_reset_request(
        PasswordResetRequest(email=user.email),
        db=db,
    )
    data = parse_json(resp)
    assert data["data"]["sent"] is True
    assert db.committed
    assert isinstance(db.added[0], PasswordResetToken)
    assert sent["email"][0] == user.email


@pytest.mark.asyncio
async def test_password_reset_confirm(monkeypatch):
    user = DummyUser()
    token = DummyToken(user.id, "tok")
    db = DummyDB(user=user, token=token)
    monkeypatch.setattr(
        "app.api.auth.services.hash_password",
        lambda p: f"hashed:{p}",
    )
    resp = await password_reset_confirm(
        PasswordResetConfirm(token="tok", new_password="new"),
        db=db,
    )
    data = parse_json(resp)
    assert data["data"]["reset"] is True
    assert user.password_hash == "hashed:new"
    assert token.used is True


@pytest.mark.asyncio
async def test_verify_email(monkeypatch):
    user = DummyUser()
    token = DummyToken(user.id, "tok")
    db = DummyDB(user=user, token=token)
    resp = await verify_email(EmailVerifyIn(token="tok"), db=db)
    data = parse_json(resp)
    assert data["data"]["verified"] is True
    assert user.is_email_verified is True
    assert token.used is True
