from fastapi import APIRouter
from pydantic import BaseModel

from app.engine.challenge_engine_auto import auto_run_challenge_streak
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/challenge", tags=["challenge"])


class ProgressInput(BaseModel):
    calendar: list
    user_id: str
    log_data: dict | None = None


@router.post("/progress")
async def challenge_progress(payload: ProgressInput):
    """Return streak progress and reward eligibility."""
    result = auto_run_challenge_streak(
        payload.calendar,
        payload.user_id,
        payload.log_data or {},
    )
    total_days = len(payload.calendar) or 1
    progress_pct = round(result.get("streak_days", 0) / total_days * 100, 1)
    return success_response({"progress_pct": progress_pct, **result})

