import collections
from typing import Optional

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

# APNS temporarily disabled due to dependency conflicts
# compat-fork-apns2==0.8.0 depends on hyper 0.7.0, which conflicts with h2>=4.0.0
# Alternative solutions for future implementation:
# 1. Use aioapns (async APNS library) 
# 2. Use original apns2 library when Python 3.10+ compatible
# 3. Use HTTP/2 APNS direct implementation
APNS_AVAILABLE = False

try:
    from apns2.client import APNsClient
    from apns2.payload import Payload
    APNS_AVAILABLE = True
except ImportError:
    # APNS library not available - will raise error if APNS is attempted
    pass

from app.core.config import settings
from app.services.notification_log_service import log_notification

if not firebase_admin._apps:
    try:
        # Try to use credentials from settings first
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
            firebase_admin.initialize_app(cred)
        else:
            # Fallback to Application Default Credentials (uses GOOGLE_APPLICATION_CREDENTIALS env var)
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
    except Exception as e:
        # Last resort: initialize without credentials (will fail for FCM but won't crash app startup)
        import logging
        logging.warning(f"Failed to initialize Firebase with credentials: {e}. FCM notifications will not work.")
        try:
            firebase_admin.initialize_app()
        except Exception:
            pass


def _record_log(
    db: Optional[Session], *, user_id: int, channel: str, message: str, success: bool
) -> None:
    if db:
        log_notification(
            db, user_id=user_id, channel=channel, message=message, success=success
        )


def send_push_notification(
    *,
    user_id: int,
    message: str = None,
    token: Optional[str] = None,
    db: Optional[Session] = None,
    title: Optional[str] = None,
    body: Optional[str] = None,
    data: Optional[dict] = None,
    image_url: Optional[str] = None,
) -> bool:
    """Send a push notification via Firebase Cloud Messaging.

    Args:
        user_id: Recipient user ID (for payload context only).
        message: Text to display in the push notification (legacy, use body instead).
        token: FCM device token. Required unless a default topic is used.
        db: Database session for logging.
        title: Notification title (defaults to "Mita Finance").
        body: Notification body text (defaults to message if not provided).
        data: Additional data payload (dict).
        image_url: Optional image URL for rich notifications.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not token:
        raise ValueError("FCM device token must be provided")

    # Use body if provided, otherwise fall back to message
    notification_body = body or message
    notification_title = title or "Mita Finance"

    if not notification_body:
        raise ValueError("Either 'body' or 'message' must be provided")

    # Build notification data
    notification_data = {"user_id": str(user_id)}
    if data:
        notification_data.update(data)

    # Build FCM message
    fcm_notification = messaging.Notification(
        title=notification_title,
        body=notification_body,
    )

    # Add image if provided
    if image_url:
        fcm_notification.image = image_url

    msg = messaging.Message(
        notification=fcm_notification,
        token=token,
        data=notification_data,
    )

    try:
        resp = messaging.send(msg)
        _record_log(db, user_id=user_id, channel="fcm", message=notification_body, success=True)
        return True
    except Exception as e:
        _record_log(db, user_id=user_id, channel="fcm", message=notification_body, success=False)
        import logging
        logging.error(f"Failed to send FCM notification: {e}")
        return False


def send_apns_notification(
    *,
    user_id: int,
    message: str,
    token: str,
    db: Optional[Session] = None,
) -> dict:
    """Send a push notification via Apple Push Notification service.
    
    Note: APNS is temporarily disabled due to dependency conflicts.
    Use FCM (send_push_notification) for all push notifications.
    """
    if not APNS_AVAILABLE:
        _record_log(db, user_id=user_id, channel="apns", message=message, success=False)
        raise RuntimeError(
            "APNS is temporarily disabled due to dependency conflicts. "
            "Use FCM (send_push_notification) instead or wait for library update."
        )
    
    # Legacy APNS code (will not execute until APNS_AVAILABLE is True)
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
