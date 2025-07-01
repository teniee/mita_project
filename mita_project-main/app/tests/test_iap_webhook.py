import pytest

from app.api.iap.routes import iap_webhook


@pytest.mark.asyncio
async def test_iap_webhook(monkeypatch):
    monkeypatch.setattr(
        "app.api.iap.routes.success_response",
        lambda data=None, message="": data,
    )
    result = await iap_webhook({"event": "TEST"})
    assert result["received"] is True
