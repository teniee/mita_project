from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import AIAnalysisSnapshot
from app.services.core.engine.ai_snapshot_service import save_ai_snapshot
from app.services.ai_financial_analyzer import AIFinancialAnalyzer
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
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get AI-analyzed spending patterns for the user"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        patterns_data = analyzer.analyze_spending_patterns()
        return success_response(patterns_data)
    except Exception as e:
        # Fallback to basic response if analysis fails
        return success_response({
            "patterns": [],
            "confidence": 0.0,
            "analysis_date": "2025-01-29T00:00:00Z",
            "error": "Insufficient data for analysis"
        })


@router.get("/personalized-feedback")
async def get_personalized_feedback(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get personalized AI feedback for the user"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        feedback_data = analyzer.generate_personalized_feedback()
        return success_response(feedback_data)
    except Exception as e:
        # Fallback response
        return success_response({
            "feedback": "Continue tracking your expenses to receive personalized insights.",
            "tips": ["Log daily expenses", "Set category budgets", "Review spending weekly"],
            "confidence": 0.0,
            "category_focus": "general"
        })


@router.get("/weekly-insights")
async def get_weekly_insights(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get weekly AI insights for the user"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        insights_data = analyzer.generate_weekly_insights()
        return success_response(insights_data)
    except Exception as e:
        # Fallback response
        return success_response({
            "insights": "Continue tracking expenses to receive weekly insights.",
            "trend": "stable",
            "weekly_summary": {},
            "recommendations": ["Track daily expenses", "Set weekly spending goals"]
        })


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
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get AI-calculated financial health score"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        score_data = analyzer.calculate_financial_health_score()
        return success_response(score_data)
    except Exception as e:
        # Fallback response
        return success_response({
            "score": 50,
            "grade": "C",
            "components": {"budgeting": 50, "spending_efficiency": 50, "saving_potential": 50, "consistency": 50},
            "improvements": ["Track expenses regularly", "Set budget categories", "Monitor spending patterns"],
            "trend": "stable"
        })


@router.get("/spending-anomalies")
async def get_spending_anomalies(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get detected spending anomalies"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        anomalies = analyzer.detect_spending_anomalies()
        return success_response(anomalies)
    except Exception as e:
        # Fallback response
        return success_response([])


@router.get("/savings-optimization")
async def get_savings_optimization(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get AI-powered savings optimization suggestions"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        optimization_data = analyzer.generate_savings_optimization()
        return success_response(optimization_data)
    except Exception as e:
        # Fallback response
        return success_response({
            "potential_savings": 0.0,
            "suggestions": ["Track expenses to identify savings opportunities"],
            "difficulty_level": "easy",
            "impact_score": 0.0,
            "implementation_tips": ["Start by logging all expenses", "Set category budgets"]
        })
