from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session

if not firebase_admin._apps:
    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    except Exception:
        firebase_admin.initialize_app()


def send_push_notification(
    *,
    user_id: int,
    message: str,
    token: Optional[str] = None,
    db: Optional[Session] = None
) -> dict:
    """Send a push notification via Firebase Cloud Messaging.

    Args:
        user_id: Recipient user ID (for payload context only).
        message: Text to display in the push notification.
        token: FCM device token. Required unless a default topic is used.

    Returns:
        Firebase messaging response as a dict.
    """
    if not token:
        raise ValueError("FCM device token must be provided")

    msg = messaging.Message(
        notification=messaging.Notification(
            title="Mita Finance",
            body=message,
        ),
        token=token,
        data={"user_id": str(user_id)},
    )

    resp = messaging.send(msg)
    if db:
        from app.services.notification_log_service import log_notification

        log_notification(
            db, user_id=user_id, channel="push", message=message, success=True
        )
    return {"message_id": resp}
