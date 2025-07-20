import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.iap.schemas import IAPReceipt
from app.api.iap.services import validate_receipt
from app.core.session import get_db
from app.db.models import Subscription, User
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/iap", tags=["iap"])


@router.post("/validate", response_model=dict)
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

    sub = Subscription(
        user_id=user.id,
        platform=result["platform"],
        plan=result.get("plan", "standard"),
        receipt={"raw": payload.receipt},
        starts_at=result.get("starts_at"),
        expires_at=result["expires_at"],
    )
    db.add(sub)

    user = db.query(User).filter(User.id == user.id).first()
    if user:
        user.is_premium = True
        user.premium_until = result["expires_at"]

    db.commit()

    return success_response(
        {
            "status": "ok",
            "premium_until": result["expires_at"],
        }
    )


@router.post("/webhook")
async def iap_webhook(payload: dict, db: Session = Depends(get_db)):
    """Receive server notifications from App Store or Play Store."""
    logging.info("IAP webhook payload: %s", payload)

    user_id = payload.get("user_id")
    expires_at = payload.get("expires_at")
    if user_id and expires_at:
        try:
            expires = datetime.fromisoformat(expires_at)
        except Exception:  # pragma: no cover - bad format
            expires = None

        if expires:
            sub = (
                db.query(Subscription)
                .filter(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
                .first()
            )
            if sub:
                sub.expires_at = expires
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.is_premium = True
                user.premium_until = expires
            db.commit()

    return success_response({"received": True})
