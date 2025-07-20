import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.iap.schemas import IAPReceipt
from app.api.iap.services import validate_receipt
from app.core.session import get_db
from app.db.models import Subscription, User
from app.utils.response_wrapper import success_response
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/iap", tags=["iap"])


@router.post("/validate", response_model=dict)
async def validate(
    payload: IAPReceipt,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),  # noqa: B008
):
    result = validate_receipt(
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
async def iap_webhook(payload: dict):
    """Receive server notifications from App Store or Play Store."""
    logging.info("IAP webhook payload: %s", payload)
    return success_response({"received": True})
