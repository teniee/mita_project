from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import AIAnalysisSnapshot
from app.services.core.engine.ai_snapshot_service import save_ai_snapshot
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/latest-snapshots")
async def get_latest_ai_snapshots(
    user=Depends(get_current_user), db: Session = Depends(get_db)  # noqa: B008
):
    snapshot = (
        db.query(AIAnalysisSnapshot)
        .filter_by(user_id=user.id)
        .order_by(AIAnalysisSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        return success_response({"count": 0, "data": []})
    data = {
        "user_id": user.id,
        "rating": snapshot.rating,
        "risk": snapshot.risk,
        "summary": snapshot.summary,
        "created_at": snapshot.created_at.isoformat(),
    }
    return success_response({"count": 1, "data": [data]})


@router.post("/snapshot")
async def create_ai_snapshot(
    *,
    year: int,
    month: int,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    result = save_ai_snapshot(user.id, db, year, month)
    return success_response(result)


@router.get("/spending-patterns")
async def get_spending_patterns(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
):
    """Get AI-analyzed spending patterns for the user"""
    # Mock data for now - this would be replaced with actual AI analysis
    patterns = [
        "frequent_small_purchases",
        "weekend_overspending",
        "subscription_accumulation",
        "impulse_buying",
        "social_spending"
    ]
    return success_response({
        "patterns": patterns[:3],  # Return first 3 patterns
        "confidence": 0.85,
        "analysis_date": "2025-01-29T00:00:00Z"
    })


@router.get("/personalized-feedback")
async def get_personalized_feedback(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
):
    """Get personalized AI feedback for the user"""
    # Mock data for now - this would be replaced with actual AI analysis
    feedback_data = {
        "feedback": "Based on your spending patterns, you're doing well with your budget management. Consider reducing dining out expenses to improve your savings rate.",
        "tips": [
            "Set a weekly limit for dining out expenses",
            "Use the 24-hour rule before making non-essential purchases",
            "Consider meal planning to reduce food costs",
            "Review your subscriptions monthly for unused services"
        ],
        "confidence": 0.92,
        "category_focus": "dining"
    }
    return success_response(feedback_data)


@router.get("/weekly-insights")
async def get_weekly_insights(
    user=Depends(get_current_user),  # noqa: B008
):
    """Get weekly AI insights for the user"""
    # Mock data for now - this would be replaced with actual AI analysis
    insights_data = {
        "insights": "This week you spent 15% less than last week, showing good progress toward your budget goals. Your largest expense category was groceries.",
        "trend": "improving",
        "weekly_summary": {
            "total_spent": 245.67,
            "vs_last_week": -15.2,
            "top_category": "groceries",
            "biggest_expense": 89.50
        },
        "recommendations": [
            "Continue your current spending patterns",
            "Consider bulk buying for groceries to save more"
        ]
    }
    return success_response(insights_data)


@router.get("/financial-profile")
async def get_financial_profile(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
):
    """Get AI financial profile analysis"""
    # Mock data for now - this would be replaced with actual AI analysis
    profile_data = {
        "spending_personality": "cautious_saver",
        "risk_tolerance": "moderate",
        "financial_goals_alignment": 0.78,
        "budgeting_style": "structured",
        "key_strengths": [
            "Consistent saving habits",
            "Good expense tracking",
            "Mindful spending decisions"
        ],
        "improvement_areas": [
            "Emergency fund building",
            "Investment diversification"
        ]
    }
    return success_response(profile_data)


@router.get("/financial-health-score")
async def get_financial_health_score(
    user=Depends(get_current_user),  # noqa: B008
):
    """Get AI-calculated financial health score"""
    # Mock data for now - this would be replaced with actual AI analysis
    score_data = {
        "score": 78,
        "grade": "B+",
        "components": {
            "budgeting": 85,
            "saving": 72,
            "debt_management": 90,
            "investment": 65
        },
        "improvements": [
            "Increase emergency fund to 6 months expenses",
            "Start investing 10% of income",
            "Review and optimize subscription services"
        ],
        "trend": "improving"
    }
    return success_response(score_data)


@router.get("/spending-anomalies")
async def get_spending_anomalies(
    user=Depends(get_current_user),  # noqa: B008
):
    """Get detected spending anomalies"""
    # Mock data for now - this would be replaced with actual AI analysis
    anomalies = [
        {
            "id": 1,
            "description": "Unusual spike in entertainment spending - 40% above average",
            "amount": 120.50,
            "category": "entertainment",
            "date": "2025-01-25",
            "severity": "medium"
        },
        {
            "id": 2,
            "description": "First time purchase in electronics category this month",
            "amount": 299.99,
            "category": "electronics",
            "date": "2025-01-28",
            "severity": "low"
        }
    ]
    return success_response(anomalies)


@router.get("/savings-optimization")
async def get_savings_optimization(
    user=Depends(get_current_user),  # noqa: B008
):
    """Get AI-powered savings optimization suggestions"""
    # Mock data for now - this would be replaced with actual AI analysis
    optimization_data = {
        "potential_savings": 185.50,
        "suggestions": [
            "Cancel unused Netflix subscription - save $15.99/month",
            "Switch to generic brands for groceries - save $45/month",
            "Reduce dining out by 2 meals per week - save $80/month",
            "Use public transport twice a week - save $44.51/month"
        ],
        "difficulty_level": "easy",
        "impact_score": 8.5,
        "implementation_tips": [
            "Start with the easiest changes first",
            "Track your progress weekly",
            "Reward yourself for meeting savings goals"
        ]
    }
    return success_response(optimization_data)
