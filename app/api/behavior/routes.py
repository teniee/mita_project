
from fastapi import APIRouter

from app.api.behavior.schemas import BehaviorPayload
from app.services.behavior_service import generate_behavior
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/behavior", tags=["behavior"])


@router.post("/calendar", response_model=dict)
async def generate_behavior_calendar(payload: BehaviorPayload):
    """Generate spending behavior calendar for a given user."""

    result = generate_behavior(
        payload.user_id,
        payload.year,
        payload.month,
        payload.profile,
        payload.mood_log,
        payload.challenge_log,
        payload.calendar_log,
    )
    return success_response(result)
