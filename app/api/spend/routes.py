
from fastapi import APIRouter
from app.api.spend.schemas import SpendCheckRequest, LimitCheckRequest
from app.api.spend.services import check_spending, check_limit
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/spend", tags=["spend"])

@router.post("/check", response_model=dict)
async def check_spend(payload: SpendCheckRequest):
    value = check_spending(payload.calendar, payload.day, payload.category)
    return success_response({"spent": value})

@router.post("/limit", response_model=dict)
async def check_category_limit(payload: LimitCheckRequest):
    limit = check_limit(payload.calendar, payload.day, payload.category)
    return success_response({"limit": limit})