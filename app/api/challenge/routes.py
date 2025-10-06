"""
Challenge System API Router
Connects challenge services to mobile app
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.user import User
from app.schemas.challenge import (
    ChallengeEligibilityRequest,
    ChallengeEligibilityResponse,
)
from app.api.challenge.schemas import ChallengeFullCheckRequest, ChallengeResult
from app.api.challenge.schemas import StreakChallengeRequest, StreakChallengeResult
from app.services.challenge_service import check_eligibility, run_streak_challenge
from app.services.challenge_service import check_eligibility as evaluate_challenge
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/challenge", tags=["challenge"])


@router.post("/eligibility", response_model=ChallengeEligibilityResponse)
async def check_challenge_eligibility(request: ChallengeEligibilityRequest):
    """Check if user is eligible for challenges"""
    result = check_eligibility(request.user_id, request.current_month)
    return success_response(result)


@router.post("/check", response_model=ChallengeResult)
async def check_challenge(payload: ChallengeFullCheckRequest):
    """Check challenge completion status"""
    result = evaluate_challenge(
        payload.calendar, payload.today_date, payload.challenge_log
    )
    return success_response(result)


@router.post("/streak", response_model=StreakChallengeResult)
async def streak_challenge(payload: StreakChallengeRequest):
    """Run streak challenge evaluation"""
    result = run_streak_challenge(payload.calendar, payload.user_id, payload.log_data)
    return success_response(result)


# NEW ENDPOINTS for mobile app integration

@router.get("/available")
async def get_available_challenges(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get list of available challenges for user"""
    # TODO: Connect to real challenge discovery service
    available_challenges = [
        {
            "id": "savings_streak_7",
            "name": "7-Day Savings Streak",
            "description": "Stay under budget for 7 consecutive days",
            "type": "streak",
            "duration_days": 7,
            "reward_points": 100,
            "difficulty": "easy",
            "participants": 1250
        },
        {
            "id": "no_dining_out_30",
            "name": "30-Day No Dining Out",
            "description": "Avoid restaurant spending for 30 days",
            "type": "category_restriction",
            "duration_days": 30,
            "reward_points": 500,
            "difficulty": "hard",
            "participants": 380
        },
        {
            "id": "reduce_transport_15",
            "name": "Reduce Transport Costs 15%",
            "description": "Cut transportation spending by 15% this month",
            "type": "category_reduction",
            "duration_days": 30,
            "reward_points": 250,
            "difficulty": "medium",
            "participants": 820
        }
    ]
    return success_response(available_challenges)


@router.get("/stats")
async def get_challenge_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's challenge statistics"""
    # TODO: Query from database
    stats = {
        "total_challenges_completed": 0,
        "active_challenges": 0,
        "current_streak": 0,
        "total_points_earned": 0,
        "challenges_completed_this_month": 0,
        "success_rate": 0.0,
        "rank": None,
        "badges_earned": []
    }
    return success_response(stats)


@router.get("/{challenge_id}/progress")
async def get_challenge_progress(
    challenge_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's progress on specific challenge"""
    # TODO: Query from database
    progress = {
        "challenge_id": challenge_id,
        "status": "not_started",
        "progress_percentage": 0.0,
        "days_completed": 0,
        "days_remaining": 0,
        "current_streak": 0,
        "best_streak": 0,
        "started_at": None,
        "completed_at": None
    }
    return success_response(progress)


@router.post("/{challenge_id}/join")
async def join_challenge(
    challenge_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Join a challenge"""
    # TODO: Create challenge participation record in database
    result = {
        "joined": True,
        "challenge_id": challenge_id,
        "started_at": "2025-10-06T00:00:00Z",
        "message": "Successfully joined challenge!"
    }
    return success_response(result)


@router.post("/{challenge_id}/leave")
async def leave_challenge(
    challenge_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Leave a challenge"""
    # TODO: Update challenge participation record
    result = {
        "left": True,
        "challenge_id": challenge_id,
        "message": "You have left the challenge"
    }
    return success_response(result)


@router.patch("/{challenge_id}/progress")
async def update_challenge_progress(
    challenge_id: str,
    progress_data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update progress on a challenge"""
    # TODO: Update challenge progress in database
    result = {
        "updated": True,
        "challenge_id": challenge_id,
        "new_progress": progress_data
    }
    return success_response(result)


@router.get("/active")
async def get_active_challenges(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's active challenges"""
    # TODO: Query from database
    active_challenges: List[Dict[str, Any]] = []
    return success_response(active_challenges)


@router.get("/{challenge_id}")
async def get_challenge_details(
    challenge_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific challenge"""
    # TODO: Query from database
    challenge = {
        "id": challenge_id,
        "name": "Challenge Name",
        "description": "Challenge description",
        "type": "streak",
        "duration_days": 7,
        "reward_points": 100,
        "difficulty": "easy",
        "rules": [],
        "tips": []
    }
    return success_response(challenge)


@router.get("/leaderboard")
async def get_challenge_leaderboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get challenge leaderboard"""
    # TODO: Query from database
    leaderboard = {
        "top_users": [],
        "user_rank": None,
        "total_participants": 0,
        "period": "all_time"
    }
    return success_response(leaderboard)
