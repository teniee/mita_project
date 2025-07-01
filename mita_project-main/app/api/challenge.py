from app.utils.response_wrapper import success_response

from fastapi import APIRouter
from app.schemas.challenge import ChallengeEligibilityRequest
from app.services.core.api.challenge_engine import check_monthly_challenge_eligibility

router = APIRouter()

@router.post("/eligibility")
def check_challenge_eligibility(request: ChallengeEligibilityRequest):
    return check_monthly_challenge_eligibility(request.user_id, request.current_month)