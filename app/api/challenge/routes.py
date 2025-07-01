
from fastapi import APIRouter
from app.schemas.challenge import ChallengeEligibilityRequest, ChallengeEligibilityResponse
from app.services.challenge_service import check_eligibility
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/challenge", tags=["challenge"])

@router.post("/eligibility", response_model=ChallengeEligibilityResponse)
async def check_challenge_eligibility(request: ChallengeEligibilityRequest):
    result = check_eligibility(request.user_id, request.current_month)
    return success_response(result)


from app.api.challenge.schemas import ChallengeFullCheckRequest, ChallengeResult
from app.services.challenge_service import check_eligibility as evaluate_challenge

@router.post("/check", response_model=ChallengeResult)
async def check_challenge(payload: ChallengeFullCheckRequest):
    result = evaluate_challenge(payload.calendar, payload.today_date, payload.challenge_log)
    return success_response(result)


from app.api.challenge.schemas import StreakChallengeRequest, StreakChallengeResult
from app.services.challenge_service import run_streak_challenge

@router.post("/streak", response_model=StreakChallengeResult)
async def streak_challenge(payload: StreakChallengeRequest):
    result = run_streak_challenge(payload.calendar, payload.user_id, payload.log_data)
    return success_response(result)