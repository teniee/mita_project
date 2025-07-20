import io
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from fastapi_limiter import FastAPILimiter

from app.api.transactions.routes import router as tx_router
from app.ocr.ocr_receipt_service import OCRReceiptService


class DummyRedis:
    def __init__(self):
        self.count = {}

    async def script_load(self, script):
        return "sha"

    async def evalsha(self, sha, num_keys, key, limit, expire):
        self.count[key] = self.count.get(key, 0) + 1
        if self.count[key] > int(limit):
            return 1
        return 0

    async def close(self):
        pass


class DummyLimiter:
    def __init__(self):
        self.calls = 0

    async def __call__(self, request, response):
        self.calls += 1
        if self.calls > 5:
            raise HTTPException(status_code=429)


@pytest.mark.asyncio
async def test_rate_limit_receipt(monkeypatch):
    FastAPILimiter.redis = DummyRedis()
    FastAPILimiter.lua_sha = "sha"

    async def ident(req):
        return "ip"

    FastAPILimiter.identifier = ident

    async def noop(request, resp, p):
        return resp

    FastAPILimiter.http_callback = noop

    app = FastAPI()
    app.include_router(tx_router)
    from app.api import dependencies

    app.dependency_overrides[dependencies.get_current_user] = lambda: SimpleNamespace(
        id="u1"
    )
    monkeypatch.setattr(
        "app.api.transactions.routes.success_response",
        lambda data=None, message="": data,
    )

    monkeypatch.setattr(
        OCRReceiptService,
        "process_image",
        lambda self, path: {"ok": True},
    )

    limiter = DummyLimiter()
    file = ("a.jpg", b"x")

    for _ in range(5):
        await limiter(None, None)
        r = await tx_router.routes[-1].endpoint(
            UploadFile(filename=file[0], file=io.BytesIO(file[1])),
            user=SimpleNamespace(id="u1"),
            db=SimpleNamespace(),
        )
        assert r["ok"] is True

    with pytest.raises(HTTPException):
        await limiter(None, None)
        await tx_router.routes[-1].endpoint(
            UploadFile(filename=file[0], file=io.BytesIO(file[1])),
            user=SimpleNamespace(id="u1"),
            db=SimpleNamespace(),
        )
