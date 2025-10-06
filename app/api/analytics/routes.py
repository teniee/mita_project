from typing import Dict, Any
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.api.analytics.schemas import (
    AggregateResult,
    AnomalyResult,
    CalendarPayload,
    MonthlyAnalyticsOut,
    TrendOut,
)
from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.user import User
from app.services.analytics_service import (
    analyze_aggregate,
    analyze_anomalies,
    get_monthly_category_totals,
    get_monthly_trend,
)
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/monthly", response_model=MonthlyAnalyticsOut)
async def monthly(
    user=Depends(get_current_user), db: Session = Depends(get_db)  # noqa: B008
):
    result = get_monthly_category_totals(user.id, db)
    return success_response({"categories": result})


@router.get("/trend", response_model=TrendOut)
async def trend(
    user=Depends(get_current_user), db: Session = Depends(get_db)  # noqa: B008
):
    result = get_monthly_trend(user.id, db)
    return success_response({"trend": result})


@router.post("/aggregate", response_model=AggregateResult)
async def aggregate(payload: CalendarPayload):
    return success_response(analyze_aggregate(payload.calendar))


@router.post("/anomalies", response_model=AnomalyResult)
async def anomalies(payload: CalendarPayload):
    return success_response(analyze_anomalies(payload.calendar))


# NEW ENDPOINTS for mobile app integration

@router.get("/behavioral-insights")
async def get_behavioral_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral insights from analytics"""
    # TODO: Connect to behavioral analytics service
    return success_response({
        "spending_behavior": "consistent",
        "risk_score": 0.3,
        "impulse_buying_tendency": "low",
        "budget_adherence": 0.85,
        "saving_discipline": 0.75,
        "insights": [
            "You tend to spend more on weekends",
            "Your grocery spending is above average for your income bracket",
            "You have strong saving discipline"
        ],
        "recommendations": [
            "Set a weekend spending limit",
            "Consider meal planning to reduce grocery costs"
        ]
    })


@router.post("/feature-usage")
async def log_feature_usage(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log feature usage for analytics"""
    feature = data.get("feature")
    timestamp = data.get("timestamp")
    metadata = data.get("metadata", {})

    # TODO: Store in analytics database
    return success_response({
        "logged": True,
        "feature": feature,
        "user_id": user.id
    })


@router.post("/feature-access-attempt")
async def log_feature_access_attempt(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log when user attempts to access premium features"""
    feature = data.get("feature")
    has_access = data.get("has_access", False)

    # TODO: Store in analytics for conversion tracking
    return success_response({
        "logged": True,
        "feature": feature,
        "user_id": user.id,
        "has_access": has_access
    })


@router.post("/paywall-impression")
async def log_paywall_impression(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log paywall impressions for conversion tracking"""
    screen = data.get("screen")
    feature = data.get("feature")
    timestamp = data.get("timestamp")

    # TODO: Store in analytics database
    return success_response({
        "logged": True,
        "screen": screen,
        "feature": feature
    })


@router.get("/seasonal-patterns")
async def get_seasonal_patterns(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get seasonal spending patterns"""
    # TODO: Analyze historical data for seasonal trends
    return success_response({
        "patterns": [
            {
                "season": "holiday_season",
                "months": [11, 12],
                "average_increase": 0.35,
                "categories_affected": ["shopping", "dining", "gifts"],
                "recommendation": "Budget 35% more for holiday months"
            },
            {
                "season": "summer",
                "months": [6, 7, 8],
                "average_increase": 0.20,
                "categories_affected": ["travel", "entertainment"],
                "recommendation": "Plan for increased summer activities spending"
            }
        ],
        "next_season": {
            "name": "holiday_season",
            "starts_in_days": 45,
            "expected_impact": "high"
        }
    })
