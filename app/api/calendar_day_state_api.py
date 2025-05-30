from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.calendar_state_service import get_calendar_day_state
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/calendar", tags=["calendar"])

class DayInput(BaseModel):
    user_id: str
    year: int
    month: int
    day: int

@router.post("/day_state")
async def get_day_state(payload: DayInput):
    state = get_calendar_day_state(payload.user_id, payload.year, payload.month, payload.day)
    return success_response({"state": state})
