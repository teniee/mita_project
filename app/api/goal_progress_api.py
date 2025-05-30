from fastapi import APIRouter
from pydantic import BaseModel
from app.engine.goal_mode_ui_api import calculate_goal_progress
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/goal", tags=["goal"])

class GoalProgressInput(BaseModel):
    calendar: list
    target: float

@router.post("/progress")
async def goal_progress(payload: GoalProgressInput):
    result = calculate_goal_progress(payload.calendar, payload.target)
    return success_response({"progress": result})