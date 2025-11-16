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
    from datetime import datetime
    from app.db.models import Challenge, ChallengeParticipation
    from sqlalchemy import and_, func

    current_month = datetime.utcnow().strftime("%Y-%m")

    # Get all active challenges for this month
    active_challenges = db.query(Challenge).filter(
        and_(
            Challenge.start_month <= current_month,
            Challenge.end_month >= current_month
        )
    ).all()

    # Get all user's participations for current month in ONE query
    user_participation_ids = set(
        db.query(ChallengeParticipation.challenge_id).filter(
            and_(
                ChallengeParticipation.user_id == user.id,
                ChallengeParticipation.month == current_month
            )
        ).scalars().all()
    )

    # Get participant counts for all challenges in ONE query
    participant_counts = dict(
        db.query(
            ChallengeParticipation.challenge_id,
            func.count(ChallengeParticipation.id)
        ).group_by(ChallengeParticipation.challenge_id).all()
    )

    available_challenges = []
    for ch in active_challenges:
        # Check if user already joined using in-memory set (no query)
        if ch.id not in user_participation_ids:
            # Get participant count from pre-loaded dict (no query)
            participants_count = participant_counts.get(ch.id, 0)

            available_challenges.append({
                "id": ch.id,
                "name": ch.name,
                "description": ch.description,
                "type": ch.type,
                "duration_days": ch.duration_days,
                "reward_points": ch.reward_points,
                "difficulty": ch.difficulty,
                "participants": participants_count
            })

    return success_response(available_challenges)


@router.get("/stats")
async def get_challenge_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's challenge statistics"""
    from datetime import datetime
    from app.db.models import ChallengeParticipation, Challenge
    from sqlalchemy import func

    current_month = datetime.utcnow().strftime("%Y-%m")

    # Count completed challenges
    total_completed = db.query(func.count(ChallengeParticipation.id)).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.status == "completed"
        )
    ).scalar() or 0

    # Count active challenges
    active_count = db.query(func.count(ChallengeParticipation.id)).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.status == "active"
        )
    ).scalar() or 0

    # Get current streak (max streak from active challenges)
    max_streak = db.query(func.max(ChallengeParticipation.current_streak)).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.status == "active"
        )
    ).scalar() or 0

    # Calculate total points earned using JOIN to avoid N+1
    from sqlalchemy.orm import joinedload

    completed_participations = db.query(ChallengeParticipation).options(
        joinedload(ChallengeParticipation.challenge)
    ).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.status == "completed"
        )
    ).all()

    total_points = 0
    for cp in completed_participations:
        if cp.challenge:
            total_points += cp.challenge.reward_points

    # Count challenges completed this month
    completed_this_month = db.query(func.count(ChallengeParticipation.id)).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.status == "completed",
            ChallengeParticipation.month == current_month
        )
    ).scalar() or 0

    # Calculate success rate
    total_participations = db.query(func.count(ChallengeParticipation.id)).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.status.in_(["completed", "failed"])
        )
    ).scalar() or 0

    success_rate = (total_completed / total_participations) if total_participations > 0 else 0.0

    stats = {
        "total_challenges_completed": total_completed,
        "active_challenges": active_count,
        "current_streak": max_streak,
        "total_points_earned": total_points,
        "challenges_completed_this_month": completed_this_month,
        "success_rate": round(success_rate, 2),
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
    from datetime import datetime
    from app.db.models import ChallengeParticipation, Challenge

    current_month = datetime.utcnow().strftime("%Y-%m")

    # Query participation record
    participation = db.query(ChallengeParticipation).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.month == current_month
        )
    ).first()

    if not participation:
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
    else:
        # Get challenge details for duration
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        days_remaining = challenge.duration_days - participation.days_completed if challenge else 0

        progress = {
            "challenge_id": challenge_id,
            "status": participation.status,
            "progress_percentage": float(participation.progress_percentage),
            "days_completed": participation.days_completed,
            "days_remaining": max(0, days_remaining),
            "current_streak": participation.current_streak,
            "best_streak": participation.best_streak,
            "started_at": participation.started_at.isoformat() if participation.started_at else None,
            "completed_at": participation.completed_at.isoformat() if participation.completed_at else None
        }

    return success_response(progress)


@router.post("/{challenge_id}/join")
async def join_challenge(
    challenge_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Join a challenge"""
    from datetime import datetime
    from app.db.models import ChallengeParticipation, Challenge

    current_month = datetime.utcnow().strftime("%Y-%m")

    # Check if challenge exists
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        return success_response({
            "joined": False,
            "message": "Challenge not found"
        })

    # Check if already joined
    existing = db.query(ChallengeParticipation).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.month == current_month
        )
    ).first()

    if existing:
        return success_response({
            "joined": False,
            "message": "Already joined this challenge"
        })

    # Create participation record
    participation = ChallengeParticipation(
        user_id=user.id,
        challenge_id=challenge_id,
        month=current_month,
        status="active",
        progress_percentage=0,
        days_completed=0,
        current_streak=0,
        best_streak=0,
        started_at=datetime.utcnow()
    )

    db.add(participation)
    db.commit()

    result = {
        "joined": True,
        "challenge_id": challenge_id,
        "started_at": participation.started_at.isoformat(),
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
    from datetime import datetime
    from app.db.models import ChallengeParticipation

    current_month = datetime.utcnow().strftime("%Y-%m")

    # Find participation record
    participation = db.query(ChallengeParticipation).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.month == current_month
        )
    ).first()

    if not participation:
        return success_response({
            "left": False,
            "message": "You are not participating in this challenge"
        })

    # Update status to abandoned
    participation.status = "abandoned"
    db.commit()

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
    from datetime import datetime
    from app.db.models import ChallengeParticipation

    current_month = datetime.utcnow().strftime("%Y-%m")

    # Find participation record
    participation = db.query(ChallengeParticipation).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.challenge_id == challenge_id,
            ChallengeParticipation.month == current_month
        )
    ).first()

    if not participation:
        return success_response({
            "updated": False,
            "message": "You are not participating in this challenge"
        })

    # Update progress fields
    if "days_completed" in progress_data:
        participation.days_completed = progress_data["days_completed"]
    if "current_streak" in progress_data:
        participation.current_streak = progress_data["current_streak"]
        participation.best_streak = max(participation.best_streak, progress_data["current_streak"])
    if "progress_percentage" in progress_data:
        participation.progress_percentage = progress_data["progress_percentage"]
    if "status" in progress_data:
        participation.status = progress_data["status"]
        if progress_data["status"] == "completed":
            participation.completed_at = datetime.utcnow()

    participation.last_updated = datetime.utcnow()
    db.commit()

    result = {
        "updated": True,
        "challenge_id": challenge_id,
        "new_progress": {
            "days_completed": participation.days_completed,
            "current_streak": participation.current_streak,
            "progress_percentage": participation.progress_percentage,
            "status": participation.status
        }
    }
    return success_response(result)


@router.get("/active")
async def get_active_challenges(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's active challenges"""
    from datetime import datetime
    from app.db.models import ChallengeParticipation, Challenge
    from sqlalchemy.orm import joinedload

    # Query active participations with eager-loaded challenge (no N+1)
    participations = db.query(ChallengeParticipation).options(
        joinedload(ChallengeParticipation.challenge)
    ).filter(
        and_(
            ChallengeParticipation.user_id == user.id,
            ChallengeParticipation.status == "active"
        )
    ).all()

    active_challenges: List[Dict[str, Any]] = []
    for p in participations:
        if p.challenge:
            active_challenges.append({
                "id": p.challenge.id,
                "name": p.challenge.name,
                "description": p.challenge.description,
                "type": p.challenge.type,
                "duration_days": p.challenge.duration_days,
                "reward_points": p.challenge.reward_points,
                "difficulty": p.challenge.difficulty,
                "progress_percentage": float(p.progress_percentage),
                "days_completed": p.days_completed,
                "current_streak": p.current_streak,
                "started_at": p.started_at.isoformat() if p.started_at else None
            })

    return success_response(active_challenges)


@router.get("/{challenge_id}")
async def get_challenge_details(
    challenge_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific challenge"""
    from app.db.models import Challenge

    challenge_obj = db.query(Challenge).filter(Challenge.id == challenge_id).first()

    if not challenge_obj:
        return success_response({
            "error": "Challenge not found"
        })

    challenge = {
        "id": challenge_obj.id,
        "name": challenge_obj.name,
        "description": challenge_obj.description,
        "type": challenge_obj.type,
        "duration_days": challenge_obj.duration_days,
        "reward_points": challenge_obj.reward_points,
        "difficulty": challenge_obj.difficulty,
        "start_month": challenge_obj.start_month,
        "end_month": challenge_obj.end_month,
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
    from app.db.models import ChallengeParticipation, Challenge
    from sqlalchemy import func, desc

    # Count completed challenges per user
    leaderboard_query = db.query(
        ChallengeParticipation.user_id,
        func.count(ChallengeParticipation.id).label('completed_count')
    ).filter(
        ChallengeParticipation.status == "completed"
    ).group_by(
        ChallengeParticipation.user_id
    ).order_by(
        desc('completed_count')
    ).limit(10).all()

    top_users = []
    user_rank = None
    for idx, (uid, count) in enumerate(leaderboard_query, 1):
        top_users.append({
            "rank": idx,
            "user_id": str(uid),
            "completed_challenges": count
        })
        if uid == user.id:
            user_rank = idx

    # Total participants
    total_participants = db.query(
        func.count(func.distinct(ChallengeParticipation.user_id))
    ).scalar() or 0

    leaderboard = {
        "top_users": top_users,
        "user_rank": user_rank,
        "total_participants": total_participants,
        "period": "all_time"
    }
    return success_response(leaderboard)
