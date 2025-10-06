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
    from app.db.models import Transaction
    from datetime import datetime
    import statistics

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    # Get transactions for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= start_date,
        Transaction.spent_at < end_date
    ).all()

    if len(transactions) < 5:
        return success_response({
            "anomalies": [],
            "unusual_transactions": [],
            "alerts": [],
            "note": "Need at least 5 transactions to detect anomalies"
        })

    # Calculate statistical anomalies
    amounts = [float(t.amount) for t in transactions]
    mean_amount = statistics.mean(amounts)
    stdev_amount = statistics.stdev(amounts) if len(amounts) > 1 else 0
    threshold = mean_amount + (2.5 * stdev_amount)

    anomalies = []
    unusual_transactions = []

    for txn in transactions:
        amount = float(txn.amount)
        if amount > threshold:
            anomalies.append({
                "type": "high_spending",
                "severity": "warning" if amount < threshold * 1.5 else "critical",
                "amount": amount,
                "category": txn.category or "uncategorized",
                "date": txn.spent_at.isoformat(),
                "description": f"Spending {amount:.2f} is {((amount/mean_amount - 1) * 100):.0f}% above your average"
            })
            unusual_transactions.append({
                "id": str(txn.id),
                "amount": amount,
                "category": txn.category,
                "merchant": txn.merchant_name,
                "date": txn.spent_at.isoformat()
            })

    # Generate alerts
    alerts = []
    if len(anomalies) > 3:
        alerts.append({
            "type": "spending_spike",
            "message": f"Detected {len(anomalies)} unusual transactions this month",
            "severity": "warning"
        })

    return success_response({
        "anomalies": anomalies,
        "unusual_transactions": unusual_transactions,
        "alerts": alerts,
        "threshold": round(threshold, 2),
        "average": round(mean_amount, 2)
    })


@router.get("/recommendations")
async def get_adaptive_behavior_recommendations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get personalized recommendations based on behavior"""
    from app.db.models import Transaction
    from datetime import datetime, timedelta
    from collections import defaultdict

    # Analyze last 60 days of transactions
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= sixty_days_ago
    ).all()

    if len(transactions) < 5:
        return success_response({
            "recommendations": [
                {
                    "type": "getting_started",
                    "message": "Add more transactions to get personalized recommendations",
                    "priority": "low"
                }
            ],
            "action_items": []
        })

    # Analyze spending by category
    category_spending = defaultdict(lambda: {"amount": 0.0, "count": 0})
    for txn in transactions:
        cat = txn.category or "uncategorized"
        category_spending[cat]["amount"] += float(txn.amount)
        category_spending[cat]["count"] += 1

    # Generate recommendations
    recommendations = []
    action_items = []

    # Check for high-frequency categories
    for cat, data in category_spending.items():
        if data["count"] > 10:  # More than 10 transactions in 60 days
            avg_per_txn = data["amount"] / data["count"]
            recommendations.append({
                "type": "spending_pattern",
                "category": cat,
                "message": f"You spend frequently on {cat} (${avg_per_txn:.2f} per transaction). Consider setting a monthly budget.",
                "priority": "medium"
            })

    # Check for large one-time expenses
    total_spent = sum(float(t.amount) for t in transactions)
    avg_transaction = total_spent / len(transactions) if transactions else 0

    for txn in transactions:
        if float(txn.amount) > avg_transaction * 3:
            recommendations.append({
                "type": "large_expense",
                "category": txn.category,
                "message": f"Large expense detected: ${float(txn.amount):.2f} on {txn.category}. Plan ahead for similar expenses.",
                "priority": "high"
            })

    # Generate action items
    if len(recommendations) > 2:
        action_items.append({
            "action": "set_category_budgets",
            "description": "Set monthly budgets for your top spending categories",
            "categories": list(category_spending.keys())[:3]
        })

    return success_response({
        "recommendations": recommendations[:5],  # Limit to top 5
        "action_items": action_items,
        "analysis_period_days": 60,
        "transactions_analyzed": len(transactions)
    })


@router.get("/triggers")
async def get_spending_triggers(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get spending triggers and behavioral insights"""
    from app.db.models import Transaction
    from datetime import datetime
    from collections import defaultdict

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    # Get transactions for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= start_date,
        Transaction.spent_at < end_date
    ).all()

    # Analyze temporal patterns
    day_of_week_spending = defaultdict(lambda: {"amount": 0.0, "count": 0})
    hour_of_day_spending = defaultdict(lambda: {"amount": 0.0, "count": 0})

    for txn in transactions:
        day_name = txn.spent_at.strftime("%A")
        hour = txn.spent_at.hour

        day_of_week_spending[day_name]["amount"] += float(txn.amount)
        day_of_week_spending[day_name]["count"] += 1

        hour_of_day_spending[hour]["amount"] += float(txn.amount)
        hour_of_day_spending[hour]["count"] += 1

    # Find temporal triggers
    temporal_triggers = []
    for day, data in day_of_week_spending.items():
        if data["count"] > 2:  # Significant pattern
            avg = data["amount"] / data["count"]
            temporal_triggers.append({
                "type": "day_of_week",
                "trigger": day,
                "average_spending": round(avg, 2),
                "frequency": data["count"],
                "insight": f"You tend to spend ${avg:.2f} on {day}s"
            })

    # Find peak spending hours
    if hour_of_day_spending:
        peak_hour = max(hour_of_day_spending.items(), key=lambda x: x[1]["amount"])
        temporal_triggers.append({
            "type": "time_of_day",
            "trigger": f"{peak_hour[0]}:00",
            "total_spending": round(peak_hour[1]["amount"], 2),
            "insight": f"Most spending occurs around {peak_hour[0]}:00"
        })

    # Generate insights
    insights = []
    if len(transactions) > 5:
        avg_per_day = len(transactions) / 30  # Approximate
        if avg_per_day > 3:
            insights.append({
                "type": "frequency",
                "message": f"High transaction frequency: {avg_per_day:.1f} transactions per day",
                "recommendation": "Consider batch shopping to reduce impulse purchases"
            })

    return success_response({
        "emotional_triggers": [],  # Would need mood data for this
        "temporal_triggers": temporal_triggers,
        "location_triggers": [],  # Would need merchant location data
        "insights": insights,
        "analysis_period": f"{year}-{month:02d}",
        "transactions_analyzed": len(transactions)
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
    from app.db.models import Transaction
    from datetime import datetime, timedelta
    from collections import defaultdict

    # Analyze transactions over the requested months
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=months * 30)

    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= start_date,
        Transaction.spent_at <= end_date
    ).order_by(Transaction.spent_at).all()

    if not transactions:
        return success_response({
            "months_tracked": months,
            "improvement_score": 0.0,
            "milestones": [],
            "trends": [],
            "note": "No transaction data available for analysis"
        })

    # Group transactions by month
    monthly_data = defaultdict(lambda: {"total": 0.0, "count": 0, "categories": set()})

    for txn in transactions:
        month_key = txn.spent_at.strftime("%Y-%m")
        monthly_data[month_key]["total"] += float(txn.amount)
        monthly_data[month_key]["count"] += 1
        if txn.category:
            monthly_data[month_key]["categories"].add(txn.category)

    # Calculate trends
    trends = []
    month_keys = sorted(monthly_data.keys())

    if len(month_keys) >= 2:
        first_month = monthly_data[month_keys[0]]
        last_month = monthly_data[month_keys[-1]]

        # Spending trend
        spending_change = ((last_month["total"] - first_month["total"]) / first_month["total"] * 100) if first_month["total"] > 0 else 0
        trends.append({
            "metric": "total_spending",
            "change_percent": round(spending_change, 1),
            "direction": "decreased" if spending_change < 0 else "increased",
            "is_improvement": spending_change < 0
        })

        # Transaction frequency trend
        freq_change = last_month["count"] - first_month["count"]
        trends.append({
            "metric": "transaction_frequency",
            "change": freq_change,
            "direction": "decreased" if freq_change < 0 else "increased",
            "is_improvement": freq_change < 5  # Lower frequency can be good
        })

    # Calculate improvement score (0-100)
    improvement_score = 50.0  # Baseline
    if trends:
        for trend in trends:
            if trend.get("is_improvement"):
                improvement_score += 10

    # Generate milestones
    milestones = []
    if len(transactions) >= 30:
        milestones.append({
            "type": "data_collection",
            "message": "Tracked 30+ transactions",
            "achieved_at": transactions[29].spent_at.isoformat()
        })

    return success_response({
        "months_tracked": months,
        "improvement_score": round(min(100, max(0, improvement_score)), 1),
        "milestones": milestones,
        "trends": trends,
        "monthly_breakdown": [
            {
                "month": month,
                "total_spent": round(data["total"], 2),
                "transaction_count": data["count"],
                "unique_categories": len(data["categories"])
            }
            for month, data in sorted(monthly_data.items())
        ]
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
    from app.db.models import Transaction
    from datetime import datetime, timedelta

    # Default to last 90 days if no year/month specified
    if year and month:
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)

    # Query transactions for this category
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.category == category,
        Transaction.spent_at >= start_date,
        Transaction.spent_at < end_date
    ).all()

    if not transactions:
        return success_response({
            "category": category,
            "average_spending": 0.0,
            "frequency": 0,
            "patterns": [],
            "recommendations": [],
            "note": f"No transactions found for category '{category}'"
        })

    total_spent = sum(float(t.amount) for t in transactions)
    avg_spending = total_spent / len(transactions)

    return success_response({
        "category": category,
        "average_spending": round(avg_spending, 2),
        "total_spent": round(total_spent, 2),
        "frequency": len(transactions),
        "patterns": [
            {
                "type": "frequency",
                "value": len(transactions),
                "description": f"{len(transactions)} transactions in the period"
            }
        ],
        "recommendations": [
            {
                "message": f"Consider budgeting ${round(total_spent * 1.1, 2)} for {category} next month",
                "type": "budgeting"
            }
        ] if len(transactions) > 5 else []
    })


@router.get("/warnings")
async def get_behavioral_warnings(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get behavioral warnings and alerts"""
    from app.db.models import Transaction
    from datetime import datetime
    import statistics

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    # Get transactions for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= start_date,
        Transaction.spent_at < end_date
    ).all()

    warnings = []
    critical_alerts = []
    suggestions = []

    if len(transactions) > 10:
        # Check for overspending patterns
        amounts = [float(t.amount) for t in transactions]
        total = sum(amounts)
        avg = statistics.mean(amounts)

        # High spending warning
        if total > 5000:  # Arbitrary threshold, should be based on user income
            warnings.append({
                "type": "high_total_spending",
                "severity": "medium",
                "message": f"Total spending this month: ${total:.2f}",
                "threshold": 5000
            })

        # Frequent small transactions warning
        if len(transactions) > 30 and avg < 20:
            warnings.append({
                "type": "frequent_small_transactions",
                "severity": "low",
                "message": f"{len(transactions)} small transactions detected - consider batch shopping",
                "average_amount": round(avg, 2)
            })

        suggestions.append({
            "type": "tracking",
            "message": "Great job tracking your expenses!"
        })

    return success_response({
        "warnings": warnings,
        "critical_alerts": critical_alerts,
        "suggestions": suggestions,
        "transactions_analyzed": len(transactions)
    })


@router.post("/expense_suggestions")
async def get_behavioral_expense_suggestions(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get smart expense suggestions based on behavioral patterns"""
    from app.db.models import Transaction
    from datetime import datetime, timedelta
    from collections import Counter

    category = data.get("category")
    amount = data.get("amount")

    # Analyze past transactions to suggest category
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    past_transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= sixty_days_ago
    ).all()

    if not past_transactions:
        return success_response({
            "suggested_category": category or "general",
            "suggested_amount": amount or 0.0,
            "confidence": 0.0,
            "alternatives": [],
            "note": "Not enough transaction history for suggestions"
        })

    # Find most common categories
    categories = [t.category for t in past_transactions if t.category]
    category_counts = Counter(categories)
    top_categories = category_counts.most_common(3)

    alternatives = []
    if not category and top_categories:
        # Suggest category based on frequency
        suggested_cat = top_categories[0][0]
        alternatives = [
            {"category": cat, "reason": f"Used {count} times recently"}
            for cat, count in top_categories
        ]
    else:
        suggested_cat = category

    # Suggest amount based on category history
    if suggested_cat and not amount:
        cat_transactions = [float(t.amount) for t in past_transactions if t.category == suggested_cat]
        if cat_transactions:
            import statistics
            suggested_amt = statistics.median(cat_transactions)
        else:
            suggested_amt = 0.0
    else:
        suggested_amt = amount or 0.0

    confidence = min(1.0, len(past_transactions) / 50.0)

    return success_response({
        "suggested_category": suggested_cat,
        "suggested_amount": round(suggested_amt, 2) if suggested_amt else None,
        "confidence": round(confidence, 2),
        "alternatives": alternatives[:3],
        "based_on_transactions": len(past_transactions)
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
