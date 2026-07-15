import os

import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

os.environ.setdefault("FIREBASE_JSON", "{}")


class DummyTransport(Transport):
    """Captures both SDK delivery paths.

    sentry-sdk 1.x sends error events through Transport.capture_event and
    only sessions/transactions through capture_envelope; 2.x sends
    everything as envelopes. Capturing only envelopes silently dropped the
    error event on 1.x and failed the assertion below.
    """

    def __init__(self, options=None):
        super().__init__(options)
        self.envelopes = []
        self.plain_events = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

    def capture_event(self, event):
        self.plain_events.append(event)


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
    # converts them to 500 responses. Collect exception events from both
    # delivery paths and every envelope item (session envelopes ride along).
    event_payloads = list(transport.plain_events) + [
        item.payload.json
        for envelope in transport.envelopes
        for item in envelope.items
        if isinstance(getattr(item.payload, "json", None), dict)
    ]
    exception_types = [
        exc.get("type")
        for event in event_payloads
        for exc in event.get("exception", {}).get("values", [])
    ]
    assert "RuntimeError" in exception_types
