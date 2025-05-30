from fastapi import APIRouter
from pydantic import BaseModel
from app.services.core.api.challenge_engine import check_monthly_challenge_eligibility
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/challenge", tags=["challenge"])

class ChallengeRequest(BaseModel):
    calendar: list
    today_date: str
    challenge_log: dict

@router.post("/check")
async def check_challenge(payload: ChallengeRequest):
    result = check_monthly_challenge_eligibility(payload.calendar, payload.today_date, payload.challenge_log)
    return success_response(result)