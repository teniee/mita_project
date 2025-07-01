from typing import Optional

import collections
if not hasattr(collections, "MutableMapping"):
    import collections.abc
    collections.MutableMapping = collections.abc.MutableMapping
if not hasattr(collections, "MutableSet"):
    import collections.abc
    collections.MutableSet = collections.abc.MutableSet
if not hasattr(collections, "Iterable"):
    import collections.abc
    collections.Iterable = collections.abc.Iterable
if not hasattr(collections, "Mapping"):
    import collections.abc
    collections.Mapping = collections.abc.Mapping

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session

from apns2.client import APNsClient
from apns2.payload import Payload

from app.core.config import settings
from app.services.notification_log_service import log_notification

if not firebase_admin._apps:
    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    except Exception:
        firebase_admin.initialize_app()


def _record_log(db: Session | None, *, user_id: int, channel: str, message: str, success: bool) -> None:
    if db:
        log_notification(db, user_id=user_id, channel=channel, message=message, success=success)


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

    try:
        resp = messaging.send(msg)
        _record_log(db, user_id=user_id, channel="fcm", message=message, success=True)
        return {"message_id": resp}
    except Exception:
        _record_log(db, user_id=user_id, channel="fcm", message=message, success=False)
        raise


def send_apns_notification(
    *,
    user_id: int,
    message: str,
    token: str,
    db: Optional[Session] = None,
) -> dict:
    """Send a push notification via Apple Push Notification service."""

    client = APNsClient(
        credentials=settings.apns_key,
        use_sandbox=settings.apns_use_sandbox,
        team_id=settings.apns_team_id,
        key_id=settings.apns_key_id,
    )
    payload = Payload(alert=message, sound="default")
    try:
        resp = client.send_notification(token, payload, topic=settings.apns_topic)
        _record_log(db, user_id=user_id, channel="apns", message=message, success=True)
        return {"apns_id": resp}
    except Exception:
        _record_log(db, user_id=user_id, channel="apns", message=message, success=False)
        raise
