from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.iap.services import validate_receipt
from app.core.session import get_db
from app.db.models import Subscription
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/iap", tags=["iap"])


class ReceiptIn(BaseModel):
    platform: str  # ios / android
    receipt: str


@router.post("/validate")
def validate(
    receipt: ReceiptIn,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    result = validate_receipt(user.id, receipt.receipt, receipt.platform)
    if result.get("status") != "valid":
        raise HTTPException(status_code=400, detail="Invalid receipt")

    sub = Subscription(
        user_id=user.id,
        platform=result["platform"],
        receipt={"raw": receipt.receipt},
        current_period_end=datetime.utcnow() + timedelta(days=365),
    )
    db.add(sub)
    db.commit()
    return success_response(
        {
            "status": "ok",
            "premium_until": sub.current_period_end,
        }
    )
