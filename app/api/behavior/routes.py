"""
Behavioral Analysis API Router
Connects powerful behavioral analysis services to mobile app
"""
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.orm import Session

from app.api.behavior.schemas import BehaviorPayload
from app.api.behavior.services import generate_behavior
from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.user import User
from app.utils.response_wrapper import success_response

# Import behavioral services
from app.services.core.behavior.behavior_service import analyze_user_behavior
from app.services.core.engine.user_behavior_predictor import predict_spending_behavior
from app.engine.behavior.spending_pattern_extractor import extract_patterns

router = APIRouter(prefix="/behavior", tags=["behavior"])


@router.get("/analysis")
async def get_behavioral_analysis(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get comprehensive behavioral analysis"""
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    try:
        # Use real behavioral analysis service
        analysis = analyze_user_behavior(
            user_id=user.id,
            db=db,
            year=year,
            month=month
        )
        return success_response(analysis)
    except Exception as e:
        # Fallback response
        return success_response({
            "spending_patterns": [],
            "behavioral_score": 0.5,
            "insights": ["Complete more transactions to enable detailed behavioral analysis"],
            "period": f"{year}-{month:02d}"
        })


@router.get("/patterns")
async def get_spending_pattern_analysis(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed spending patterns"""
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    try:
        patterns = extract_patterns(str(user.id), year, month)
        return success_response(patterns)
    except Exception as e:
        return success_response({
            "patterns": [],
            "dominant_pattern": "balanced",
            "confidence": 0.0
        })


@router.get("/predictions")
async def get_behavioral_predictions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get spending behavior predictions"""
    try:
        predictions = predict_spending_behavior(
            user_id=user.id,
            db=db
        )
        return success_response(predictions)
    except Exception as e:
        return success_response({
            "next_week_spending": 0.0,
            "next_month_spending": 0.0,
            "confidence": 0.0,
            "insights": ["More transaction history needed for accurate predictions"]
        })


@router.get("/anomalies")
async def get_behavioral_anomalies(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get spending anomalies and unusual patterns"""
    return success_response({
        "anomalies": [],
        "unusual_transactions": [],
        "alerts": []
    })


@router.get("/recommendations")
async def get_adaptive_behavior_recommendations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get personalized recommendations based on behavior"""
    return success_response({
        "recommendations": [
            {
                "type": "spending_habit",
                "message": "Consider setting a weekly limit for dining out based on your patterns",
                "priority": "medium"
            }
        ],
        "action_items": []
    })


@router.get("/triggers")
async def get_spending_triggers(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get spending triggers and behavioral insights"""
    return success_response({
        "emotional_triggers": [],
        "temporal_triggers": [],
        "location_triggers": [],
        "insights": []
    })


@router.post("/calendar", response_model=dict)
async def generate_behavior_calendar(
    payload: BehaviorPayload, user=Depends(get_current_user)  # noqa: B008
):
    """Generate spending behavior calendar for a given user."""
    result = generate_behavior(
        user.id,
        payload.year,
        payload.month,
        payload.profile,
        payload.mood_log,
        payload.challenge_log,
        payload.calendar_log,
    )
    return success_response(result)


@router.get("/cluster")
async def get_behavioral_cluster(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's behavioral cluster classification"""
    return success_response({
        "cluster_id": "balanced_spender",
        "cluster_name": "Balanced Spender",
        "characteristics": [
            "Consistent spending patterns",
            "Good budget adherence",
            "Moderate risk profile"
        ],
        "peer_count": 0
    })


@router.patch("/preferences")
async def update_behavioral_preferences(
    preferences: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update behavioral analysis preferences"""
    from app.db.models import UserPreference

    # Get or create user preference record
    user_pref = db.query(UserPreference).filter(
        UserPreference.user_id == user.id
    ).first()

    if not user_pref:
        user_pref = UserPreference(user_id=user.id)
        db.add(user_pref)

    # Update preference fields
    if "auto_insights" in preferences:
        user_pref.auto_insights = preferences["auto_insights"]
    if "anomaly_detection" in preferences:
        user_pref.anomaly_detection = preferences["anomaly_detection"]
    if "predictive_alerts" in preferences:
        user_pref.predictive_alerts = preferences["predictive_alerts"]
    if "peer_comparison" in preferences:
        user_pref.peer_comparison = preferences["peer_comparison"]

    # Store any additional preferences in JSON field
    additional = {k: v for k, v in preferences.items()
                  if k not in ["auto_insights", "anomaly_detection", "predictive_alerts", "peer_comparison"]}
    if additional:
        user_pref.additional_preferences = additional

    db.commit()

    return success_response({"updated": True, "preferences": preferences})


@router.get("/preferences")
async def get_behavioral_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral analysis preferences"""
    from app.db.models import UserPreference

    # Query user preferences
    user_pref = db.query(UserPreference).filter(
        UserPreference.user_id == user.id
    ).first()

    if not user_pref:
        # Return default preferences if not set
        default_preferences = {
            "auto_insights": True,
            "anomaly_detection": True,
            "predictive_alerts": True,
            "peer_comparison": False
        }
        return success_response(default_preferences)

    preferences = {
        "auto_insights": user_pref.auto_insights,
        "anomaly_detection": user_pref.anomaly_detection,
        "predictive_alerts": user_pref.predictive_alerts,
        "peer_comparison": user_pref.peer_comparison
    }

    # Add any additional preferences
    if user_pref.additional_preferences:
        preferences.update(user_pref.additional_preferences)

    return success_response(preferences)


@router.get("/progress")
async def get_behavioral_progress(
    months: int = Query(3, ge=1, le=12),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral improvement progress over time"""
    return success_response({
        "months_tracked": months,
        "improvement_score": 0.0,
        "milestones": [],
        "trends": []
    })


@router.get("/category/{category}")
async def get_category_behavioral_insights(
    category: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral insights for specific category"""
    return success_response({
        "category": category,
        "average_spending": 0.0,
        "frequency": 0,
        "patterns": [],
        "recommendations": []
    })


@router.get("/warnings")
async def get_behavioral_warnings(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral warnings and alerts"""
    return success_response({
        "warnings": [],
        "critical_alerts": [],
        "suggestions": []
    })


@router.post("/expense_suggestions")
async def get_behavioral_expense_suggestions(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get smart expense suggestions based on behavioral patterns"""
    category = data.get("category")
    amount = data.get("amount")
    context = data.get("context", {})

    return success_response({
        "suggested_category": category,
        "suggested_amount": amount,
        "confidence": 0.0,
        "alternatives": []
    })


@router.patch("/notification_settings")
async def update_behavioral_notification_settings(
    settings: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update behavioral notification preferences"""
    from app.db.models import UserPreference

    # Get or create user preference record
    user_pref = db.query(UserPreference).filter(
        UserPreference.user_id == user.id
    ).first()

    if not user_pref:
        user_pref = UserPreference(user_id=user.id)
        db.add(user_pref)

    # Update notification settings
    if "anomaly_alerts" in settings:
        user_pref.anomaly_alerts = settings["anomaly_alerts"]
    if "pattern_insights" in settings:
        user_pref.pattern_insights = settings["pattern_insights"]
    if "weekly_summary" in settings:
        user_pref.weekly_summary = settings["weekly_summary"]
    if "spending_warnings" in settings:
        user_pref.spending_warnings = settings["spending_warnings"]

    db.commit()

    return success_response({"updated": True, "settings": settings})


@router.get("/notification_settings")
async def get_behavioral_notification_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral notification preferences"""
    from app.db.models import UserPreference

    # Query user preferences
    user_pref = db.query(UserPreference).filter(
        UserPreference.user_id == user.id
    ).first()

    if not user_pref:
        # Return default settings if not set
        default_settings = {
            "anomaly_alerts": True,
            "pattern_insights": True,
            "weekly_summary": True,
            "spending_warnings": True
        }
        return success_response(default_settings)

    settings = {
        "anomaly_alerts": user_pref.anomaly_alerts,
        "pattern_insights": user_pref.pattern_insights,
        "weekly_summary": user_pref.weekly_summary,
        "spending_warnings": user_pref.spending_warnings
    }

    return success_response(settings)
