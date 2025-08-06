from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.api.dependencies import get_current_user, require_premium_user
from app.core.session import get_db
from app.db.models import BudgetAdvice
from app.utils.response_wrapper import success_response

from .schemas import AdviceOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/", response_model=AdviceOut | None)
async def latest_insight(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    try:
        # Check if user is premium for full insights
        if not user.is_premium:
            logger.info(f"Non-premium user {user.id} accessing insights - providing basic advice")
            # Return basic insight for non-premium users
            basic_advice = {
                "id": "basic-001",
                "title": "Track Your Spending",
                "content": "Continue logging your expenses to unlock personalized insights with premium.",
                "category": "general",
                "priority": "medium",
                "date": "2025-01-29"
            }
            return success_response(basic_advice)
        
        # Premium user - get actual advice from database
        advice = (
            db.query(BudgetAdvice)
            .filter(BudgetAdvice.user_id == user.id)
            .order_by(BudgetAdvice.date.desc())
            .first()
        )
        
        if advice:
            data = AdviceOut.model_validate(advice).model_dump(mode="json")
            return success_response(data)
        else:
            # No advice available yet
            return success_response(None)
            
    except Exception as e:
        logger.error(f"Error fetching insights for user {user.id}: {e}")
        # Return fallback response instead of 500 error
        fallback_advice = {
            "id": "fallback-001",
            "title": "Keep Tracking",
            "content": "Continue logging your expenses to receive personalized insights.",
            "category": "general",
            "priority": "low",
            "date": "2025-01-29"
        }
        return success_response(fallback_advice)


@router.get("/history", response_model=list[AdviceOut])
async def insight_history(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    try:
        # Check if user is premium for full history
        if not user.is_premium:
            logger.info(f"Non-premium user {user.id} accessing insight history")
            # Return empty history for non-premium users with upgrade prompt
            upgrade_prompt = {
                "id": "upgrade-001",
                "title": "Unlock Insight History",
                "content": "Upgrade to premium to view your complete insight history and personalized financial advice.",
                "category": "upgrade",
                "priority": "high",
                "date": "2025-01-29"
            }
            return success_response([upgrade_prompt])
        
        # Premium user - get actual history from database
        items = (
            db.query(BudgetAdvice)
            .filter(BudgetAdvice.user_id == user.id)
            .order_by(BudgetAdvice.date.desc())
            .all()
        )
        
        if items:
            data = [AdviceOut.model_validate(it).model_dump(mode="json") for it in items]
            return success_response(data)
        else:
            # No history available yet
            return success_response([])
            
    except Exception as e:
        logger.error(f"Error fetching insight history for user {user.id}: {e}")
        # Return empty array instead of 500 error
        return success_response([])
