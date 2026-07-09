from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.api.goal.schemas import (
    GoalProgressInput,
    GoalState,
    ProgressOut,
    ProgressRequest,
)
from app.services.goal_service import (
    compute_calendar_progress,
    compute_goal_progress,
    get_user_progress,
)
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/goal", tags=["goal"])


def _enforce_own_user_id(payload_user_id, current_user) -> str:
    """Identity comes from the session, never from the request body.

    A body-supplied user_id let authenticated user A issue B-scoped reads
    (N-P2-IDOR-1). If a client still sends one, it must match the session.
    """
    if payload_user_id and str(payload_user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id does not match the authenticated user",
        )
    return str(current_user.id)


@router.post("/state-progress", response_model=ProgressOut)
async def goal_from_state(
    payload: GoalState,
    user=Depends(get_current_user),  # noqa: B008
):
    data = payload.model_dump()
    data["user_id"] = _enforce_own_user_id(data.get("user_id"), user)
    result = compute_goal_progress(data)
    return success_response(result)


@router.post("/calendar-progress", response_model=dict)
async def goal_from_calendar(payload: GoalProgressInput):
    progress = compute_calendar_progress(payload.calendar, payload.target)
    return success_response({"progress": progress})


@router.post("/user-progress", response_model=dict)
async def full_progress(
    payload: ProgressRequest,
    user=Depends(get_current_user),  # noqa: B008
):
    user_id = _enforce_own_user_id(payload.user_id, user)
    result = get_user_progress(
        user_id,
        payload.year,
        payload.month,
        {"currency": "USD", "locale": payload.locale},
    )
    return success_response(result)
