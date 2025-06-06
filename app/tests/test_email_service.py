from app.services.email_service import send_email


class DummySMTP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.messages = []
        self.started_tls = False
        self.logged_in = False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = True

    def send_message(self, msg):
        self.messages.append(msg)
        return {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


def test_send_email(monkeypatch):
    store = {}

    def smtp_factory(host, port):
        smtp = DummySMTP(host, port)
        store["smtp"] = smtp
        return smtp

    monkeypatch.setattr(
        "app.services.email_service.smtplib.SMTP",
        smtp_factory,
    )
    result = send_email("user@example.com", "Subject", "Body")
    assert result["accepted"] is True
    smtp = store["smtp"]
    assert smtp.messages[0]["To"] == "user@example.com"
