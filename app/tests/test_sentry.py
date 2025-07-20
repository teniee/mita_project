import os
import types

import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

os.environ.setdefault("FIREBASE_JSON", "{}")


class DummyTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events = []

    def capture_envelope(self, envelope):
        self.events.append(envelope)


def test_sentry_captures_error():
    transport = DummyTransport()
    sentry_sdk.init(
        dsn="http://example@localhost/1", transport=transport, integrations=[]
    )

    from app.main import app

    async def boom():
        raise RuntimeError("boom")

    app.add_api_route("/boom", boom, methods=["GET"])

    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get("/boom")

    sentry_sdk.flush()
    assert transport.events
    event = transport.events[0].items[0].payload.json
    assert "request_body" in event.get("extra", {})
