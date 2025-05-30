from fastapi import APIRouter
from pydantic import BaseModel
from app.services.core.behavior.behavior_service import generate_behavioral_calendar
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/behavior", tags=["behavior"])

class BehaviorRequest(BaseModel):
    start_date: str
    days: int
    category_weights: dict

@router.post("/calendar")
async def get_behavior_calendar(payload: BehaviorRequest):
    calendar = generate_behavioral_calendar(payload.start_date, payload.days, payload.category_weights)
    return success_response({"calendar": calendar})