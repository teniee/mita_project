from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.challenge_engine_auto import auto_run_challenge_streak
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/challenge", tags=["challenge"])

class StreakInput(BaseModel):
    calendar: list
    user_id: str
    log_data: dict

@router.post("/streak_auto")
async def check_streak(payload: StreakInput):
    result = auto_run_challenge_streak(payload.calendar, payload.user_id, payload.log_data)
    return success_response(result)