import os
import smtplib
from email.message import EmailMessage


def send_email(to_email: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user or "noreply@example.com"
    msg["To"] = to_email
    msg.set_content(body)

    if not host:
        print("Email not configured; skipping send")
        return

    with smtplib.SMTP(host, port) as smtp:
        if user and password:
            smtp.starttls()
            smtp.login(user, password)
        smtp.send_message(msg)
