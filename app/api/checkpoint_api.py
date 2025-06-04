from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.daily_checkpoint import get_today_checkpoint
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/checkpoint", tags=["checkpoint"])

class CheckpointInput(BaseModel):
    calendar: list
    income: float
    day: int

@router.post("/today")
async def today_checkpoint(payload: CheckpointInput):
    value = get_today_checkpoint(payload.calendar, payload.income, payload.day)
    return success_response({"available_today": value})