from fastapi import APIRouter, Depends

from app.api.behavior.schemas import BehaviorPayload
from app.api.behavior.services import generate_behavior
from app.api.dependencies import get_current_user
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/behavior", tags=["behavior"])


@router.post("/calendar", response_model=dict)
async def generate_behavior_calendar(
    payload: BehaviorPayload, user=Depends(get_current_user)  # noqa: B008
):
    """Generate spending behavior calendar for a given user."""

    result = generate_behavior(
        user.id,
        payload.year,
        payload.month,
        payload.profile,
        payload.mood_log,
        payload.challenge_log,
        payload.calendar_log,
    )
    return success_response(result)
