from fastapi import APIRouter

from app.api.iap.schemas import IAPReceipt
from app.api.iap.services import validate_receipt
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/iap", tags=["iap"])


@router.post("/validate", response_model=dict)
async def validate(payload: IAPReceipt):
    return success_response(
        validate_receipt(payload.user_id, payload.receipt, payload.platform)
    )
