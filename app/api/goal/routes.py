
from fastapi import APIRouter
from app.api.goal.schemas import GoalState, GoalProgressInput, ProgressRequest, ProgressOut
from app.services.goal_service import compute_goal_progress, compute_calendar_progress, get_user_progress
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/goal", tags=["goal"])

@router.post("/state-progress", response_model=ProgressOut)
async def goal_from_state(payload: GoalState):
    result = compute_goal_progress(payload.dict())
    return success_response(result)

@router.post("/calendar-progress", response_model=dict)
async def goal_from_calendar(payload: GoalProgressInput):
    progress = compute_calendar_progress(payload.calendar, payload.target)
    return success_response({"progress": progress})

@router.post("/user-progress", response_model=dict)
async def full_progress(payload: ProgressRequest):
    result = get_user_progress(
        payload.user_id,
        payload.year,
        payload.month,
        {"currency": "USD", "locale": payload.locale},
    )
    return success_response(result)