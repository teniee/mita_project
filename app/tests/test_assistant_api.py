from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_assistant_message(monkeypatch):
    def fake_ask(self, messages):
        assert messages == [{"role": "user", "content": "hi"}]
        return "hello"

    monkeypatch.setattr("app.api.assistant_api.gpt_agent.ask", fake_ask)

    resp = client.post(
        "/api/assistant/message",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["reply"] == "hello"
