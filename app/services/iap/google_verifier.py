"""Verification of Google Play Real-Time Developer Notifications (RTDN).

RTDN arrives via a Pub/Sub push subscription. Authentication:

1. The push request carries a Google-signed OIDC JWT in the Authorization
   header (configure the push subscription with "Enable authentication").
   We verify its signature against Google's public keys, its audience, and
   the service-account email that is allowed to push.
2. The notification body only names a purchaseToken. Entitlement state is
   then fetched authoritatively from the Google Play Developer API
   (purchases.subscriptions.get) using our own service-account credentials
   — the notification content itself is never trusted for entitlement.
"""

import base64
import json
import logging
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from app.services.iap.errors import IAPNotConfiguredError, IAPVerificationError

logger = logging.getLogger(__name__)

# https://developer.android.com/google/play/billing/rtdn-reference
SUBSCRIPTION_NOTIFICATION_TYPES = {
    1: "SUBSCRIPTION_RECOVERED",
    2: "SUBSCRIPTION_RENEWED",
    3: "SUBSCRIPTION_CANCELED",
    4: "SUBSCRIPTION_PURCHASED",
    5: "SUBSCRIPTION_ON_HOLD",
    6: "SUBSCRIPTION_IN_GRACE_PERIOD",
    7: "SUBSCRIPTION_RESTARTED",
    8: "SUBSCRIPTION_PRICE_CHANGE_CONFIRMED",
    9: "SUBSCRIPTION_DEFERRED",
    10: "SUBSCRIPTION_PAUSED",
    11: "SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED",
    12: "SUBSCRIPTION_REVOKED",
    13: "SUBSCRIPTION_EXPIRED",
}


@dataclass
class GoogleNotification:
    """A verified + decoded RTDN subscription notification."""

    message_id: str
    package_name: str
    event_type: str
    purchase_token: Optional[str]
    subscription_id: Optional[str]
    is_test: bool = False


def _default_oidc_verifier(token: str, audience: Optional[str]) -> Dict:
    """Verify a Google-signed OIDC token (network call to Google certs)."""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:  # pragma: no cover - deps pinned in prod
        raise IAPNotConfiguredError("google-auth is not installed") from exc

    try:
        return google_id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=audience
        )
    except Exception as exc:
        raise IAPVerificationError("Google OIDC token verification failed") from exc


def verify_pubsub_push(
    authorization_header: Optional[str],
    *,
    audience: str,
    service_account_email: str,
    oidc_verifier: Optional[Callable[[str, Optional[str]], Dict]] = None,
) -> Dict:
    """Authenticate a Pub/Sub push request. Returns the verified claims."""
    if not audience or not service_account_email:
        raise IAPNotConfiguredError(
            "GOOGLE_PUBSUB_AUDIENCE / GOOGLE_PUBSUB_SERVICE_ACCOUNT not configured"
        )

    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise IAPVerificationError("Missing Pub/Sub bearer token")
    token = authorization_header.split(" ", 1)[1].strip()

    verifier = oidc_verifier or _default_oidc_verifier
    claims = verifier(token, audience)

    issuer = claims.get("iss", "")
    if issuer not in ("accounts.google.com", "https://accounts.google.com"):
        raise IAPVerificationError("Pub/Sub token has unexpected issuer")
    if claims.get("email") != service_account_email:
        raise IAPVerificationError("Pub/Sub token is not from the allowed account")
    if claims.get("email_verified") is False:
        raise IAPVerificationError("Pub/Sub token email is not verified")
    return claims


def decode_rtdn_envelope(
    envelope: Dict, *, expected_package: Optional[str] = None
) -> GoogleNotification:
    """Decode the Pub/Sub envelope into a subscription notification."""
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise IAPVerificationError("Pub/Sub envelope missing message")

    message_id = message.get("messageId") or message.get("message_id")
    if not message_id:
        raise IAPVerificationError("Pub/Sub message missing messageId")

    try:
        decoded = json.loads(base64.b64decode(message.get("data", "")))
    except Exception as exc:
        raise IAPVerificationError("Pub/Sub message data is not valid JSON") from exc

    package_name = decoded.get("packageName", "")
    if expected_package and package_name != expected_package:
        raise IAPVerificationError("RTDN packageName does not match app")

    if "testNotification" in decoded:
        return GoogleNotification(
            message_id=message_id,
            package_name=package_name,
            event_type="TEST_NOTIFICATION",
            purchase_token=None,
            subscription_id=None,
            is_test=True,
        )

    sub_notification = decoded.get("subscriptionNotification")
    if not isinstance(sub_notification, dict):
        # Voided purchases / one-time products are not entitlement-bearing
        # for MITA; acknowledge without acting.
        return GoogleNotification(
            message_id=message_id,
            package_name=package_name,
            event_type="UNSUPPORTED_NOTIFICATION",
            purchase_token=None,
            subscription_id=None,
        )

    notification_type = SUBSCRIPTION_NOTIFICATION_TYPES.get(
        sub_notification.get("notificationType"), "UNKNOWN"
    )
    return GoogleNotification(
        message_id=message_id,
        package_name=package_name,
        event_type=notification_type,
        purchase_token=sub_notification.get("purchaseToken"),
        subscription_id=sub_notification.get("subscriptionId"),
    )


class GooglePlayClient:
    """Thin adapter over the Google Play Developer API (androidpublisher).

    Kept as a class so tests and future providers can substitute an
    implementation without touching route logic.
    """

    def __init__(self, service_account_path: Optional[str]):
        self._service_account_path = service_account_path

    def get_subscription(
        self, package_name: str, subscription_id: str, token: str
    ) -> Dict:
        if not self._service_account_path:
            raise IAPNotConfiguredError("GOOGLE_SERVICE_ACCOUNT not configured")
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - deps pinned in prod
            raise IAPNotConfiguredError(
                "google-api-python-client is not installed"
            ) from exc

        credentials = service_account.Credentials.from_service_account_file(
            self._service_account_path
        )
        service = build(
            "androidpublisher", "v3", credentials=credentials, cache_discovery=False
        )
        return (
            service.purchases()
            .subscriptions()
            .get(
                packageName=package_name,
                subscriptionId=subscription_id,
                token=token,
            )
            .execute()
        )
