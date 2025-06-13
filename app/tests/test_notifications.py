from pytest import raises

from app.services.email_service import send_email
from app.services.push_service import send_push_notification


def test_send_email_without_config(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    # Should not raise even if SMTP is not configured
    send_email("user@example.com", "Hi", "Body")


def test_push_notification_requires_token():
    with raises(ValueError):
        send_push_notification(user_id=1, message="test")
