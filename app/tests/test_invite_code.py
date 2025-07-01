from types import SimpleNamespace

import pytest

from app.api.referral.routes import invite_code


@pytest.mark.asyncio
async def test_invite_code(monkeypatch):
    monkeypatch.setattr(
        "app.api.referral.routes.success_response",
        lambda data=None, message="": data,
    )
    user = SimpleNamespace(id="12345678-abcd-efgh-ijkl-1234567890ab")
    result = await invite_code(user=user)
    assert result["code"] == "123456"
