from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.iap.schemas import IAPReceipt
from app.api.iap.services import validate_receipt
from app.core.session import get_db
from app.db.models import Subscription, User
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/iap", tags=["iap"])


@router.post("/validate", response_model=dict)
async def validate(
    payload: IAPReceipt,
    db: Session = Depends(get_db),  # noqa: B008
):
    result = validate_receipt(
        payload.user_id,
        payload.receipt,
        payload.platform,
    )
    if result.get("status") != "valid":
        return success_response(result)

    sub = Subscription(
        user_id=payload.user_id,
        platform=result["platform"],
        plan=result.get("plan", "standard"),
        receipt={"raw": payload.receipt},
        starts_at=result.get("starts_at"),
        expires_at=result["expires_at"],
    )
    db.add(sub)

    user = db.query(User).filter(User.id == payload.user_id).first()
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
