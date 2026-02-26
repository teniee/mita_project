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
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_address
    msg.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USERNAME:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
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
