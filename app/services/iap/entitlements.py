"""Entitlement state shared by the /iap/validate flow and store webhooks.

The single source of truth for "is this user premium" is the Subscription
row keyed by the store-side purchase identity (Apple originalTransactionId,
Google purchaseToken). Webhooks match subscriptions through that key —
a client-supplied user id is never trusted.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import IAPEvent, Subscription, User

logger = logging.getLogger(__name__)

# Statuses that keep the entitlement while expires_at is in the future.
ENTITLED_STATUSES = {"active", "grace", "canceled", "paused"}
# Statuses that end the entitlement immediately regardless of expires_at.
REVOKED_STATUSES = {"revoked", "refunded", "expired", "on_hold", "billing_retry"}


def record_event_once(
    db: Session,
    *,
    provider: str,
    event_id: str,
    event_type: Optional[str] = None,
    transaction_key: Optional[str] = None,
    result: str = "processed",
) -> bool:
    """Record a store notification; returns False if it was seen before.

    Uniqueness of (provider, event_id) is enforced by the database, so a
    concurrent duplicate delivery cannot be applied twice.
    """
    existing = (
        db.query(IAPEvent)
        .filter(IAPEvent.provider == provider, IAPEvent.event_id == event_id)
        .first()
    )
    if existing:
        return False
    try:
        db.add(
            IAPEvent(
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                transaction_key=transaction_key,
                result=result,
            )
        )
        db.flush()
        return True
    except IntegrityError:
        db.rollback()
        return False


def find_subscription_by_transaction(
    db: Session, platform: str, transaction_key: str
) -> Optional[Subscription]:
    return (
        db.query(Subscription)
        .filter(
            Subscription.platform == platform,
            Subscription.original_transaction_id == transaction_key,
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )


def compute_is_premium(
    status: str,
    expires_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> bool:
    if status in REVOKED_STATUSES:
        return False
    if status not in ENTITLED_STATUSES:
        return False
    if expires_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > now


def apply_subscription_state(
    db: Session,
    subscription: Subscription,
    *,
    status: str,
    expires_at: Optional[datetime],
    product_id: Optional[str] = None,
) -> bool:
    """Update a subscription and synchronize the owner's premium flag.

    Returns the resulting premium state.
    """
    subscription.status = status
    if expires_at is not None:
        subscription.expires_at = expires_at
    if product_id:
        subscription.product_id = product_id

    is_premium = compute_is_premium(status, subscription.expires_at)

    user = db.query(User).filter(User.id == subscription.user_id).first()
    if user:
        user.is_premium = is_premium
        user.premium_until = subscription.expires_at
    else:  # pragma: no cover - orphaned subscription
        logger.warning(
            "Subscription %s has no owning user %s",
            subscription.id,
            subscription.user_id,
        )
    return is_premium
