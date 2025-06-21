from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session

from apns2.client import APNsClient
from apns2.payload import Payload

from app.core.config import settings

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


def send_apns_notification(
    *,
    user_id: int,
    message: str,
    token: str,
    db: Optional[Session] = None,
) -> dict:
    """Send a push notification via Apple Push Notification service."""
    # Compatibility fix for older Python versions if needed
    import collections
    if not hasattr(collections, "MutableMapping"):
        import collections.abc
        collections.MutableMapping = collections.abc.MutableMapping
        collections.Iterable = collections.abc.Iterable

    client = APNsClient(
        credentials=settings.apns_key,
        use_sandbox=settings.apns_use_sandbox,
        team_id=settings.apns_team_id,
        key_id=settings.apns_key_id,
    )
    payload = Payload(alert=message, sound="default")
    resp = client.send_notification(token, payload, topic=settings.apns_topic)

    if db:
        from app.services.notification_log_service import log_notification

        log_notification(db, user_id=user_id, channel="apns", message=message, success=True)

    return {"apns_id": resp}
