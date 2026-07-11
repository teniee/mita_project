from fastapi import APIRouter, HTTPException, status

from app.api.checkpoint.schemas import CheckpointInput

router = APIRouter(prefix="/checkpoint", tags=["checkpoint"])


@router.post("/today", deprecated=True)
async def today_checkpoint(payload: CheckpointInput):
    """DEFERRED — no backing implementation.

    The mounted contract (calendar list + income + day -> available_today)
    has never had a matching engine: every implementation of
    get_today_checkpoint takes (user_id, calendar-dict) and returns a status
    dict, so this endpoint raised TypeError -> 500 on every call since it
    shipped. Per the TASK-15 policy, a deferred feature answers 501
    explicitly instead of a permanent 500. Wire
    app/engine/daily_checkpoint.get_today_checkpoint (or define the
    available_today budget semantics) before re-enabling.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Daily checkpoint is a deferred feature and is not implemented yet",
    )
