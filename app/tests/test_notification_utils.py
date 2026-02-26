import pytest

from app.core.config import settings
from app.services.push_service import send_push_notification
from app.utils.email_utils import send_reminder_email


class DummySMTP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.logged_in = False
        self.starttls_called = False
        self.sent = []

    def starttls(self):
        self.starttls_called = True

    def login(self, username, password):
        self.logged_in = True

    def send_message(self, msg):
        self.sent.append(msg)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


def test_send_push_requires_token():
    with pytest.raises(ValueError):
        send_push_notification(user_id=1, message="hi", token=None)


def test_send_reminder_email(monkeypatch):
    dummy = DummySMTP("localhost", 25)

    monkeypatch.setattr(settings, "SMTP_HOST", "localhost")
    monkeypatch.setattr(settings, "SMTP_PORT", 25)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "")

    def smtp(host, port):
        assert host == "localhost"
        assert port == 25
        return dummy

    monkeypatch.setattr("smtplib.SMTP", smtp)
    send_reminder_email("to@example.com", "Hi", "Body")
    assert dummy.sent


def test_send_push_notification_builds_message(monkeypatch):
    class DummyMessage:
        def __init__(self, notification=None, token=None, data=None):
            self.notification = notification
            self.token = token
            self.data = data

    class DummyNotification:
        def __init__(self, title=None, body=None):
            self.title = title
            self.body = body

    sent = {}

    def dummy_send(msg):
        sent["msg"] = msg
        return "id-1"

    monkeypatch.setattr(
        "app.services.push_service.messaging.Message",
        DummyMessage,
    )
    monkeypatch.setattr(
        "app.services.push_service.messaging.Notification", DummyNotification
    )
    monkeypatch.setattr(
        "app.services.push_service.messaging.send",
        dummy_send,
    )

    resp = send_push_notification(user_id=123, message="Hello", token="tok")

    assert resp == {"message_id": "id-1"}
    assert sent["msg"].token == "tok"
    assert sent["msg"].notification.body == "Hello"


def test_send_reminder_email_with_login(monkeypatch):
    dummy = DummySMTP("mail.example.com", 587)

    def smtp(host, port):
        assert host == "mail.example.com"
        assert port == 587
        return dummy

    monkeypatch.setattr("smtplib.SMTP", smtp)
    monkeypatch.setattr(settings, "SMTP_HOST", "mail.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "pass")
    send_reminder_email("to@example.com", "Hi", "Body")
    assert dummy.starttls_called
    assert dummy.logged_in
    assert dummy.sent
