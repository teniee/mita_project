import os

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

    # The app registers a catch-all exception handler, so unexpected errors
    # surface as standardized 500 responses instead of propagating.
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500

    sentry_sdk.flush()
    # Server errors must reach Sentry even though the catch-all handler
    # converts them to 500 responses.
    assert transport.events
    event = transport.events[0].items[0].payload.json
    exception_types = [
        exc.get("type")
        for exc in event.get("exception", {}).get("values", [])
    ]
    assert "RuntimeError" in exception_types
