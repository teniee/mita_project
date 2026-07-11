import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.limiter_setup import optional_rate_limit
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.iap.schemas import IAPReceipt
from app.api.iap.services import validate_receipt
from app.core.config import settings
from app.core.session import get_db
from app.db.models import Subscription, User
from app.services.iap.apple_verifier import (
    load_trusted_roots,
    verify_apple_notification,
)
from app.services.iap.entitlements import (
    apply_subscription_state,
    find_subscription_by_transaction,
    record_event_once,
)
from app.services.iap.errors import IAPNotConfiguredError, IAPVerificationError
from app.services.iap.google_verifier import (
    GooglePlayClient,
    decode_rtdn_envelope,
    verify_pubsub_push,
)
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iap", tags=["iap"])

# Apple notificationType/subtype → internal subscription status.
_APPLE_STATUS_MAP = {
    "SUBSCRIBED": "active",
    "DID_RENEW": "active",
    "OFFER_REDEEMED": "active",
    "DID_CHANGE_RENEWAL_PREF": "active",
    "REFUND_REVERSED": "active",
    "EXPIRED": "expired",
    "GRACE_PERIOD_EXPIRED": "expired",
    "REFUND": "refunded",
    "REVOKE": "revoked",
}

# Google RTDN event → internal subscription status.
_GOOGLE_STATUS_MAP = {
    "SUBSCRIPTION_PURCHASED": "active",
    "SUBSCRIPTION_RENEWED": "active",
    "SUBSCRIPTION_RECOVERED": "active",
    "SUBSCRIPTION_RESTARTED": "active",
    "SUBSCRIPTION_DEFERRED": "active",
    "SUBSCRIPTION_PRICE_CHANGE_CONFIRMED": "active",
    "SUBSCRIPTION_CANCELED": "canceled",
    "SUBSCRIPTION_IN_GRACE_PERIOD": "grace",
    "SUBSCRIPTION_ON_HOLD": "on_hold",
    "SUBSCRIPTION_PAUSED": "paused",
    "SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED": "paused",
    "SUBSCRIPTION_REVOKED": "revoked",
    "SUBSCRIPTION_EXPIRED": "expired",
}


def _allowed_product_ids() -> set:
    return {
        p.strip()
        for p in (settings.IAP_ALLOWED_PRODUCT_IDS or "").split(",")
        if p.strip()
    }


def _check_product_allowed(product_id: Optional[str]) -> None:
    """Product ids come from the store response — never from the client.

    In production an explicit allowlist is required; anything else fails
    closed so a foreign app's receipt can never grant MITA premium.
    """
    allowed = _allowed_product_ids()
    if allowed:
        if product_id not in allowed:
            raise HTTPException(
                status_code=422, detail="Product is not sold by this app"
            )
        return
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=503,
            detail="IAP_ALLOWED_PRODUCT_IDS is not configured",
        )
    logger.warning("IAP product allowlist empty — accepting %r (non-prod)", product_id)


@router.post(
    "/validate",
    response_model=dict,
    dependencies=[Depends(optional_rate_limit(times=5, seconds=60))],
)
async def validate(
    payload: IAPReceipt,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),  # noqa: B008
):
    result = await validate_receipt(
        user.id,
        payload.receipt,
        payload.platform,
    )
    if result.get("status") != "valid":
        return success_response(result)

    environment = result.get("environment", "production")
    if environment != "production" and not (
        settings.IAP_ALLOW_SANDBOX and settings.ENVIRONMENT != "production"
    ):
        raise HTTPException(status_code=422, detail="Sandbox receipts are not accepted")

    _check_product_allowed(result.get("product_id"))

    transaction_key = result.get("original_transaction_id")
    if not transaction_key:
        raise HTTPException(
            status_code=422, detail="Receipt has no transaction identity"
        )

    existing = find_subscription_by_transaction(db, result["platform"], transaction_key)
    if existing and str(existing.user_id) != str(user.id):
        # The same store purchase may not grant premium to a second account.
        logger.warning(
            "IAP receipt reuse across accounts blocked (subscription %s)",
            existing.id,
        )
        raise HTTPException(
            status_code=409,
            detail="This purchase is already linked to another account",
        )

    if existing:
        sub = existing
        sub.receipt = {"raw": payload.receipt}
        sub.plan = result.get("plan", sub.plan)
        sub.environment = environment
    else:
        sub = Subscription(
            user_id=user.id,
            platform=result["platform"],
            plan=result.get("plan", "standard"),
            receipt={"raw": payload.receipt},
            original_transaction_id=transaction_key,
            product_id=result.get("product_id"),
            environment=environment,
            starts_at=result.get("starts_at"),
            expires_at=result["expires_at"],
        )
        db.add(sub)
        db.flush()

    apply_subscription_state(
        db,
        sub,
        status="active",
        expires_at=result["expires_at"],
        product_id=result.get("product_id"),
    )
    db.commit()

    return success_response(
        {
            "status": "ok",
            "premium_until": result["expires_at"].isoformat(),
        }
    )


@router.post("/webhook")
async def iap_webhook(request: Request, db: Session = Depends(get_db)):  # noqa: B008
    """Receive store server notifications (Apple V2 JWS / Google RTDN).

    Both paths are cryptographically verified and fail closed: without the
    required configuration nothing is processed and no entitlement changes.
    Client-supplied user ids are never trusted.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid notification body")

    try:
        if "signedPayload" in payload:
            return _handle_apple_notification(payload["signedPayload"], db)
        if "message" in payload:
            return _handle_google_notification(
                payload, request.headers.get("authorization"), db
            )
    except IAPNotConfiguredError as exc:
        # Fail closed; the store retries later once configuration is fixed.
        logger.error("IAP webhook rejected — not configured: %s", exc)
        raise HTTPException(
            status_code=503, detail="IAP verification is not configured"
        )
    except IAPVerificationError as exc:
        logger.warning("IAP webhook failed verification: %s", exc)
        raise HTTPException(status_code=401, detail="Notification not authentic")

    # Legacy/unknown payloads (including the old {user_id, expires_at}
    # format) are rejected without touching entitlements.
    raise HTTPException(status_code=400, detail="Unrecognized notification format")


def _ms_to_datetime(value) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _handle_apple_notification(signed_payload: str, db: Session):
    if not settings.APPLE_ROOT_CA_PATH or not settings.APPLE_BUNDLE_ID:
        raise IAPNotConfiguredError(
            "APPLE_ROOT_CA_PATH / APPLE_BUNDLE_ID not configured"
        )

    allowed_envs = ["Production"]
    if settings.IAP_ALLOW_SANDBOX and settings.ENVIRONMENT != "production":
        allowed_envs.append("Sandbox")

    notification = verify_apple_notification(
        signed_payload,
        trusted_roots=load_trusted_roots(settings.APPLE_ROOT_CA_PATH),
        bundle_id=settings.APPLE_BUNDLE_ID,
        allowed_environments=allowed_envs,
    )

    transaction_key = notification.transaction_info.get("originalTransactionId")

    if not record_event_once(
        db,
        provider="apple",
        event_id=notification.notification_uuid,
        event_type=notification.notification_type,
        transaction_key=transaction_key,
    ):
        db.commit()
        return success_response({"received": True, "result": "duplicate"})

    if not transaction_key:
        db.commit()
        return success_response({"received": True, "result": "no_transaction"})

    subscription = find_subscription_by_transaction(db, "ios", transaction_key)
    if subscription is None:
        # Unknown purchase — nothing to update; never create entitlements
        # from a webhook alone.
        logger.warning(
            "Apple notification %s for unknown transaction",
            notification.notification_type,
        )
        db.commit()
        return success_response({"received": True, "result": "unmatched"})

    status = _apple_status(notification)
    expires_at = _ms_to_datetime(notification.transaction_info.get("expiresDate"))
    if notification.notification_type in ("REFUND", "REVOKE"):
        revocation = _ms_to_datetime(
            notification.transaction_info.get("revocationDate")
        )
        expires_at = revocation or datetime.now(timezone.utc)

    apply_subscription_state(
        db,
        subscription,
        status=status,
        expires_at=expires_at,
        product_id=notification.transaction_info.get("productId"),
    )
    db.commit()
    return success_response({"received": True, "result": "processed"})


def _apple_status(notification) -> str:
    ntype = notification.notification_type
    subtype = notification.subtype or ""
    if ntype == "DID_FAIL_TO_RENEW":
        return "grace" if subtype == "GRACE_PERIOD" else "billing_retry"
    if ntype == "DID_CHANGE_RENEWAL_STATUS":
        return "canceled" if subtype == "AUTO_RENEW_DISABLED" else "active"
    return _APPLE_STATUS_MAP.get(ntype, "active")


def _handle_google_notification(
    envelope: dict, authorization_header: Optional[str], db: Session
):
    verify_pubsub_push(
        authorization_header,
        audience=settings.GOOGLE_PUBSUB_AUDIENCE,
        service_account_email=settings.GOOGLE_PUBSUB_SERVICE_ACCOUNT,
    )

    if not settings.GOOGLE_PACKAGE_NAME:
        raise IAPNotConfiguredError("GOOGLE_PACKAGE_NAME not configured")

    notification = decode_rtdn_envelope(
        envelope, expected_package=settings.GOOGLE_PACKAGE_NAME
    )

    if not record_event_once(
        db,
        provider="google",
        event_id=notification.message_id,
        event_type=notification.event_type,
        transaction_key=notification.purchase_token,
    ):
        db.commit()
        return success_response({"received": True, "result": "duplicate"})

    if notification.is_test or not notification.purchase_token:
        db.commit()
        return success_response({"received": True, "result": "ignored"})

    subscription = find_subscription_by_transaction(
        db, "android", notification.purchase_token
    )
    if subscription is None:
        logger.warning(
            "Google notification %s for unknown purchase token",
            notification.event_type,
        )
        db.commit()
        return success_response({"received": True, "result": "unmatched"})

    # The RTDN body itself carries no entitlement data; fetch the
    # authoritative state from the Play Developer API.
    play_client = GooglePlayClient(os.getenv("GOOGLE_SERVICE_ACCOUNT"))
    purchase = play_client.get_subscription(
        notification.package_name,
        notification.subscription_id or (subscription.product_id or ""),
        notification.purchase_token,
    )

    status = _GOOGLE_STATUS_MAP.get(notification.event_type, "active")
    expires_at = _ms_to_datetime(purchase.get("expiryTimeMillis"))

    apply_subscription_state(
        db,
        subscription,
        status=status,
        expires_at=expires_at,
        product_id=notification.subscription_id,
    )
    db.commit()
    return success_response({"received": True, "result": "processed"})


@router.get("/status")
async def subscription_status(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),  # noqa: B008
):
    """Current entitlement as the server sees it (for app restore flows)."""
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    fresh_user = db.query(User).filter(User.id == user.id).first()
    return success_response(
        {
            "is_premium": bool(fresh_user and fresh_user.is_premium),
            "premium_until": (
                fresh_user.premium_until.isoformat()
                if fresh_user and fresh_user.premium_until
                else None
            ),
            "subscription": (
                {
                    "platform": sub.platform,
                    "plan": sub.plan,
                    "status": sub.status,
                    "product_id": sub.product_id,
                    "expires_at": (
                        sub.expires_at.isoformat() if sub.expires_at else None
                    ),
                }
                if sub
                else None
            ),
        }
    )
