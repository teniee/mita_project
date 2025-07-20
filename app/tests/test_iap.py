import os
from datetime import datetime

import httpx
import pytest

from app.api.iap.services import validate_receipt


@pytest.mark.asyncio
async def test_validate_receipt_expiration(monkeypatch):
    os.environ["APPLE_SHARED_SECRET"] = "secret"

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "status": 0,
                "latest_receipt_info": [
                    {
                        "expires_date_ms": "1735689600000",
                        "purchase_date_ms": "1711929600000",
                        "product_id": "com.example.app.yearly",
                    }
                ],
            }

    async def fake_post(self, *args, **kwargs):
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await validate_receipt("u1", "stub", "ios")

    assert result["status"] == "valid"
    assert result["platform"] == "ios"
    assert isinstance(result["expires_at"], datetime)
    assert result["plan"] == "annual"
    assert isinstance(result["starts_at"], datetime)
