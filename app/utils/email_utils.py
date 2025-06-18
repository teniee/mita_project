import smtplib
from email.message import EmailMessage
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings


def send_reminder_email(
    to_address: str,
    subject: str,
    body: str,
    *,
    user_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_address
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_username:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)

    if db:
        from app.services.notification_log_service import log_notification

        log_notification(
            db,
            user_id=user_id,
            channel="email",
            message=subject,
            success=True,
        )


def send_password_reset_email(address: str, token: str) -> None:
    link = f"https://example.com/reset-password?token={token}"
    body = f"Reset your password: {link}"
    send_reminder_email(address, "Password Reset", body)


def send_verification_email(address: str, token: str) -> None:
    link = f"https://example.com/verify-email?token={token}"
    body = f"Verify your account: {link}"
    send_reminder_email(address, "Verify Email", body)
