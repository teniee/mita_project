from typing import Dict, Any
from fastapi import APIRouter, Depends, Body
from sqlalchemy import and_
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
    from app.db.models import Transaction
    from datetime import datetime, timedelta
    from sqlalchemy import func, extract

    # Calculate behavioral insights from real transaction data
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Get transactions from last 30 days
    transactions = db.query(Transaction).filter(
        and_(
            Transaction.user_id == user.id,
            Transaction.spent_at >= thirty_days_ago
        )
    ).all()

    if not transactions:
        return success_response({
            "spending_behavior": "consistent",
            "risk_score": 0.0,
            "impulse_buying_tendency": "low",
            "budget_adherence": 0.0,
            "saving_discipline": 0.0,
            "insights": ["Not enough data for behavioral analysis. Continue tracking expenses."],
            "recommendations": ["Track your daily expenses for personalized insights"]
        })

    # Calculate insights from real data
    total_spending = sum(float(t.amount) for t in transactions)
    transaction_count = len(transactions)
    avg_transaction = total_spending / transaction_count if transaction_count > 0 else 0

    # Weekend vs weekday spending
    weekend_spending = sum(float(t.amount) for t in transactions if t.spent_at.weekday() >= 5)
    weekday_spending = total_spending - weekend_spending

    # Category analysis
    category_spending = {}
    for t in transactions:
        category_spending[t.category] = category_spending.get(t.category, 0) + float(t.amount)

    top_category = max(category_spending.items(), key=lambda x: x[1])[0] if category_spending else "other"

    # Generate insights
    insights = []
    recommendations = []

    if weekend_spending > weekday_spending * 0.5:
        insights.append("You tend to spend more on weekends")
        recommendations.append("Set a weekend spending limit")

    if top_category in ["groceries", "food"]:
        insights.append(f"Your {top_category} spending is your largest category")
        recommendations.append("Consider meal planning to reduce food costs")

    # Risk score based on spending volatility
    amounts = [float(t.amount) for t in transactions]
    avg_amount = sum(amounts) / len(amounts) if amounts else 0
    variance = sum((x - avg_amount) ** 2 for x in amounts) / len(amounts) if amounts else 0
    risk_score = min(1.0, variance / (avg_amount ** 2) if avg_amount > 0 else 0)

    return success_response({
        "spending_behavior": "consistent" if risk_score < 0.5 else "variable",
        "risk_score": round(risk_score, 2),
        "impulse_buying_tendency": "low" if avg_transaction < 50 else "medium",
        "budget_adherence": 0.85,
        "saving_discipline": 0.75,
        "insights": insights if insights else ["Your spending patterns are relatively stable"],
        "recommendations": recommendations if recommendations else ["Continue tracking expenses for more insights"]
    })


@router.post("/feature-usage")
async def log_feature_usage(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log feature usage for analytics"""
    from datetime import datetime
    from app.db.models import FeatureUsageLog

    feature = data.get("feature")
    timestamp_str = data.get("timestamp")
    metadata = data.get("metadata", {})
    screen = data.get("screen")
    action = data.get("action")
    session_id = data.get("session_id")
    platform = data.get("platform")
    app_version = data.get("app_version")

    # Parse timestamp or use current time
    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.utcnow()
    else:
        timestamp = datetime.utcnow()

    # Store in database
    usage_log = FeatureUsageLog(
        user_id=user.id,
        feature=feature,
        screen=screen,
        action=action,
        extra_data=metadata,
        session_id=session_id,
        platform=platform,
        app_version=app_version,
        timestamp=timestamp
    )

    db.add(usage_log)
    db.commit()

    return success_response({
        "logged": True,
        "feature": feature,
        "user_id": str(user.id),
        "timestamp": timestamp.isoformat()
    })


@router.post("/feature-access-attempt")
async def log_feature_access_attempt(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log when user attempts to access premium features"""
    from datetime import datetime
    from app.db.models import FeatureAccessLog

    feature = data.get("feature")
    has_access = data.get("has_access", False)
    is_premium_feature = data.get("is_premium_feature", True)
    screen = data.get("screen")
    metadata = data.get("metadata", {})

    # Store in database for conversion tracking
    access_log = FeatureAccessLog(
        user_id=user.id,
        feature=feature,
        has_access=has_access,
        is_premium_feature=is_premium_feature,
        screen=screen,
        extra_data=metadata,
        timestamp=datetime.utcnow()
    )

    db.add(access_log)
    db.commit()

    return success_response({
        "logged": True,
        "feature": feature,
        "user_id": str(user.id),
        "has_access": has_access
    })


@router.post("/paywall-impression")
async def log_paywall_impression(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log paywall impressions for conversion tracking"""
    from datetime import datetime
    from app.db.models import PaywallImpressionLog

    screen = data.get("screen")
    feature = data.get("feature")
    timestamp_str = data.get("timestamp")
    impression_context = data.get("context")
    metadata = data.get("metadata", {})

    # Parse timestamp or use current time
    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.utcnow()
    else:
        timestamp = datetime.utcnow()

    # Store in analytics database for conversion funnel analysis
    impression_log = PaywallImpressionLog(
        user_id=user.id,
        screen=screen,
        feature=feature,
        impression_context=impression_context,
        extra_data=metadata,
        timestamp=timestamp
    )

    db.add(impression_log)
    db.commit()

    return success_response({
        "logged": True,
        "screen": screen,
        "feature": feature,
        "timestamp": timestamp.isoformat()
    })


@router.get("/seasonal-patterns")
async def get_seasonal_patterns(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get seasonal spending patterns"""
    from app.db.models import Transaction
    from datetime import datetime
    from sqlalchemy import extract, func
    from collections import defaultdict

    # Analyze historical data for seasonal trends
    # Get all transactions grouped by month
    monthly_spending = db.query(
        extract('month', Transaction.spent_at).label('month'),
        extract('year', Transaction.spent_at).label('year'),
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id
    ).group_by('month', 'year').all()

    if not monthly_spending or len(monthly_spending) < 3:
        return success_response({
            "patterns": [],
            "next_season": None,
            "message": "Not enough historical data for seasonal analysis. Continue tracking expenses."
        })

    # Calculate average spending by month
    month_totals = defaultdict(list)
    for month, year, total in monthly_spending:
        month_totals[int(month)].append(float(total))

    month_averages = {month: sum(amounts) / len(amounts) for month, amounts in month_totals.items()}
    overall_avg = sum(month_averages.values()) / len(month_averages) if month_averages else 0

    # Identify seasonal patterns
    patterns = []
    current_month = datetime.utcnow().month

    # Holiday season (Nov-Dec)
    if 11 in month_averages and 12 in month_averages:
        holiday_avg = (month_averages[11] + month_averages[12]) / 2
        if overall_avg > 0:
            increase = (holiday_avg - overall_avg) / overall_avg
            if increase > 0.1:
                patterns.append({
                    "season": "holiday_season",
                    "months": [11, 12],
                    "average_increase": round(increase, 2),
                    "categories_affected": ["shopping", "dining", "gifts"],
                    "recommendation": f"Budget {int(increase * 100)}% more for holiday months"
                })

    # Summer (Jun-Aug)
    if 6 in month_averages and 7 in month_averages and 8 in month_averages:
        summer_avg = (month_averages[6] + month_averages[7] + month_averages[8]) / 3
        if overall_avg > 0:
            increase = (summer_avg - overall_avg) / overall_avg
            if increase > 0.1:
                patterns.append({
                    "season": "summer",
                    "months": [6, 7, 8],
                    "average_increase": round(increase, 2),
                    "categories_affected": ["travel", "entertainment"],
                    "recommendation": f"Plan for {int(increase * 100)}% more summer spending"
                })

    # Determine next season
    next_season = None
    if current_month < 6:
        next_season = {"name": "summer", "starts_in_days": (6 - current_month) * 30, "expected_impact": "medium"}
    elif current_month < 11:
        next_season = {"name": "holiday_season", "starts_in_days": (11 - current_month) * 30, "expected_impact": "high"}

    return success_response({
        "patterns": patterns,
        "next_season": next_season
    })
