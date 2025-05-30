from app.utils.response_wrapper import success_response
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.session import get_db
from app.db.models import Subscription
from app.api.dependencies import get_current_user

router=APIRouter(prefix="/iap", tags=["iap"])

class ReceiptIn(BaseModel):
    platform:str  # ios / android
    receipt:str

@router.post("/validate")
def validate(receipt:ReceiptIn, user=Depends(get_current_user), db:Session=Depends(get_db)):
    # TODO: call AppStore/Play verification
    sub=Subscription(user_id=user.id, platform=receipt.platform,
                     receipt={"raw": receipt.receipt},
                     current_period_end=datetime.utcnow()+timedelta(days=365))
    db.add(sub); db.commit()
    return success_response({"status":"ok","premium_until": sub.current_period_end})