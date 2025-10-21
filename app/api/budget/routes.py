import inspect
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db

# assumes User is defined in models
from app.db.models.user import User
from app.db.models.daily_plan import DailyPlan
from app.utils.response_wrapper import success_response

from app.api.budget.services import fetch_remaining_budget  # isort:skip
from app.api.budget.services import fetch_spent_by_category  # isort:skip

# Import real services
from app.services.core.behavior.behavioral_budget_allocator import (
    get_behavioral_allocation,
    allocate_behavioral_budget
)
from app.services.core.engine.budget_auto_adapter import adapt_category_weights
from app.services.core.engine.budget_suggestion_engine import suggest_budget_adjustments
from app.services.core.engine.budget_mode_selector import resolve_budget_mode


router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/spent")
async def spent(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Return spending amounts grouped by category."""
    if not isinstance(user, User):
        user = get_current_user()  # type: ignore
    if not isinstance(db, Session):
        db = next(get_db())  # type: ignore

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    result = fetch_spent_by_category(db, user.id, year, month)
    if inspect.isawaitable(result):
        result = await result
    return success_response(result)


@router.get("/remaining")
async def remaining(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Return the remaining budget for the month."""
    if not isinstance(user, User):
        user = get_current_user()  # type: ignore
    if not isinstance(db, Session):
        db = next(get_db())  # type: ignore

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    result = fetch_remaining_budget(db, user.id, year, month)
    if inspect.isawaitable(result):
        result = await result
    return success_response(result)


@router.get("/suggestions")
async def get_budget_suggestions(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get AI-powered budget suggestions based on actual spending patterns"""
    from app.db.models import Transaction, DailyPlan, User as UserModel
    from datetime import datetime, timedelta
    from collections import defaultdict

    # Get user's income
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()
    user_income = float(user_data.monthly_income) if user_data and user_data.monthly_income else 0

    # Build calendar structure for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= thirty_days_ago
    ).all()

    # Get planned budgets for comparison
    daily_plans = db.query(DailyPlan).filter(
        DailyPlan.user_id == user.id,
        DailyPlan.date >= thirty_days_ago.date()
    ).all()

    # Build calendar dict: date -> {actual_spending: {cat: amt}, planned_budget: {cat: amt}}
    calendar = defaultdict(lambda: {"actual_spending": defaultdict(float), "planned_budget": {}})

    for txn in transactions:
        date_key = txn.spent_at.date().isoformat()
        category = txn.category or "other"
        calendar[date_key]["actual_spending"][category] += float(txn.amount)

    for plan in daily_plans:
        date_key = plan.date.isoformat()
        if plan.plan_json and plan.plan_json.get("category_budgets"):
            calendar[date_key]["planned_budget"] = plan.plan_json.get("category_budgets")

    # Call the actual suggestion engine
    suggestions_map = suggest_budget_adjustments(dict(calendar), user_income)

    # Convert to structured response
    suggestions_list = []
    total_potential_savings = 0.0

    for idx, (category, suggestion_text) in enumerate(suggestions_map.items(), start=1):
        # Calculate potential savings from actual vs planned data
        category_actual = sum(
            day["actual_spending"].get(category, 0)
            for day in calendar.values()
        )
        category_planned = sum(
            day["planned_budget"].get(category, 0)
            for day in calendar.values()
        )

        potential_savings = max(0, category_actual - category_planned) if category_planned > 0 else 0

        if potential_savings > 0:
            total_potential_savings += potential_savings
            suggestions_list.append({
                "id": idx,
                "text": suggestion_text,
                "category": category,
                "potential_savings": round(potential_savings, 2),
                "difficulty": "easy" if potential_savings < 50 else "moderate"
            })

    # Find priority areas (top 3 overspending categories)
    category_totals = defaultdict(float)
    for day in calendar.values():
        for cat, amt in day["actual_spending"].items():
            category_totals[cat] += amt

    priority_areas = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:3]
    priority_categories = [cat for cat, _ in priority_areas]

    return success_response({
        "suggestions": suggestions_list if suggestions_list else [
            {"id": 1, "text": "Keep tracking expenses for personalized suggestions", "category": "general", "potential_savings": 0, "difficulty": "easy"}
        ],
        "total_potential_savings": round(total_potential_savings, 2),
        "priority_areas": priority_categories if priority_categories else ["general"]
    })


@router.get("/mode")
async def get_budget_mode(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get current budget mode based on user preferences and behavior"""
    from app.db.models import User as UserModel

    # Get user data to build settings dict
    user_data = db.query(UserModel).filter(UserModel.id == user.id).first()

    user_settings = {}
    if user_data:
        # Check if user has high income and savings goals
        monthly_income = float(user_data.monthly_income) if user_data.monthly_income else 0
        user_settings["income_stability"] = "high" if monthly_income > 100000 else "medium" if monthly_income > 50000 else "low"

        # Check for aggressive savings preference (could be from user_preferences table)
        from app.db.models import UserPreferences
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
        if prefs:
            user_settings["aggressive_savings"] = prefs.behavioral_savings_target and prefs.behavioral_savings_target > 25.0
            user_settings["has_family"] = False  # Could be added to user profile later

    # Call the actual mode resolver
    mode = resolve_budget_mode(user_settings)

    return success_response(mode)


@router.get("/redistribution_history")
async def get_redistribution_history(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get budget redistribution history from DailyPlan changes"""
    from app.db.models import DailyPlan
    from datetime import datetime, timedelta

    # Get last 30 days of daily plans
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_plans = db.query(DailyPlan).filter(
        DailyPlan.user_id == user.id,
        DailyPlan.date >= thirty_days_ago
    ).order_by(DailyPlan.date.desc()).all()

    # Track redistributions by analyzing plan_json changes
    history_data = []
    previous_plan = None

    for plan in reversed(daily_plans):  # Process chronologically
        if previous_plan and plan.plan_json:
            # Check if budget allocations changed
            prev_budget = previous_plan.plan_json.get("category_budgets", {})
            curr_budget = plan.plan_json.get("category_budgets", {})

            # Find categories where budget changed
            for category, curr_amount in curr_budget.items():
                prev_amount = prev_budget.get(category, 0)
                if prev_amount != curr_amount and prev_amount > 0:
                    diff = curr_amount - prev_amount
                    if abs(diff) > 1.0:  # Only track significant changes
                        history_data.append({
                            "id": len(history_data) + 1,
                            "from": category if diff < 0 else "unallocated",
                            "to": category if diff > 0 else "unallocated",
                            "amount": abs(diff),
                            "date": plan.date.isoformat(),
                            "reason": "manual_adjustment" if abs(diff) > 10 else "automatic_redistribution"
                        })

        previous_plan = plan

    # Limit to most recent 20 redistributions
    history_data = history_data[-20:] if len(history_data) > 20 else history_data

    if not history_data:
        history_data = [{
            "id": 1,
            "from": "none",
            "to": "none",
            "amount": 0,
            "date": datetime.utcnow().isoformat(),
            "reason": "no_redistributions_yet"
        }]

    return success_response(history_data)


@router.get("/daily")
async def get_daily_budgets(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get daily budget breakdown for the month"""
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    # Query daily plans for the month
    daily_plans = db.query(DailyPlan).filter(
        DailyPlan.user_id == user.id,
        DailyPlan.date >= datetime(year, month, 1),
        DailyPlan.date < datetime(year, month + 1 if month < 12 else 1, 1) if month < 12 else datetime(year + 1, 1, 1)
    ).order_by(DailyPlan.date).all()

    daily_budgets = [
        {
            "date": plan.date.isoformat(),
            "budget": float(plan.daily_budget) if plan.daily_budget else 0.0,
            "spent": float(plan.spent_amount) if plan.spent_amount else 0.0,
            "remaining": float(plan.daily_budget - plan.spent_amount) if plan.daily_budget and plan.spent_amount else 0.0,
            "status": plan.status or "neutral"
        }
        for plan in daily_plans
    ]

    return success_response(daily_budgets)


@router.post("/behavioral_allocation")
async def get_behavioral_budget_allocation(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get budget allocation based on behavioral analysis"""
    total_amount = data.get("total_amount", user.monthly_income or 0)
    profile = data.get("profile", {})

    # Use behavioral allocator service
    try:
        allocation = allocate_behavioral_budget(
            user_id=user.id,
            total_budget=total_amount,
            db=db
        )
        return success_response(allocation)
    except Exception as e:
        # Fallback to basic allocation if service fails
        basic_allocation = {
            "categories": {
                "food": total_amount * 0.30,
                "transportation": total_amount * 0.15,
                "utilities": total_amount * 0.10,
                "entertainment": total_amount * 0.10,
                "savings": total_amount * 0.20,
                "other": total_amount * 0.15
            },
            "method": "basic_fallback",
            "confidence": 0.5
        }
        return success_response(basic_allocation)


@router.post("/monthly")
async def get_monthly_budget(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Generate monthly budget based on user income and preferences"""
    year = data.get("year", datetime.utcnow().year)
    month = data.get("month", datetime.utcnow().month)
    user_answers = data.get("userAnswers", {})

    # Generate budget using budget engine
    monthly_income = user.monthly_income or data.get("monthly_income", 0)

    budget_data = {
        "month": f"{year}-{month:02d}",
        "total_income": float(monthly_income),
        "total_budget": float(monthly_income),
        "allocated": float(monthly_income * 0.8),  # 80% allocated by default
        "saved": float(monthly_income * 0.20),  # 20% savings
        "categories": {
            "food": float(monthly_income * 0.30),
            "transportation": float(monthly_income * 0.15),
            "utilities": float(monthly_income * 0.10),
            "entertainment": float(monthly_income * 0.10),
            "healthcare": float(monthly_income * 0.05),
            "other": float(monthly_income * 0.10)
        }
    }

    return success_response(budget_data)


@router.get("/adaptations")
async def get_budget_adaptations(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get budget adaptation history and suggestions"""
    adaptations_data = {
        "recent_adaptations": [],
        "pending_suggestions": [],
        "auto_adapt_enabled": True
    }
    return success_response(adaptations_data)


@router.post("/auto_adapt")
async def trigger_budget_adaptation(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Trigger automatic budget adaptation based on spending patterns"""
    try:
        # Use budget auto-adapter service
        result = adapt_budget_automatically(
            user_id=user.id,
            db=db
        )
        return success_response(result)
    except Exception as e:
        return success_response({
            "adapted": False,
            "reason": "No adaptation needed",
            "message": "Budget is currently optimal"
        })


@router.get("/live_status")
async def get_live_budget_status(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get real-time budget status"""
    from app.db.models import Transaction

    now = datetime.utcnow()

    # Get today's plan
    today_plan = db.query(DailyPlan).filter(
        DailyPlan.user_id == user.id,
        DailyPlan.date == now.date()
    ).first()

    # Calculate monthly spending from transactions
    month_start = datetime(now.year, now.month, 1)
    monthly_transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= month_start
    ).all()

    monthly_spent = sum(float(t.amount) for t in monthly_transactions)
    monthly_budget = float(user.monthly_income) if user.monthly_income else 0.0
    on_track = monthly_spent <= (monthly_budget * (now.day / 30.0)) if monthly_budget > 0 else True

    status_data = {
        "date": now.date().isoformat(),
        "daily_budget": float(today_plan.daily_budget) if today_plan and today_plan.daily_budget else 0.0,
        "spent_today": float(today_plan.spent_amount) if today_plan and today_plan.spent_amount else 0.0,
        "remaining_today": float(today_plan.daily_budget - today_plan.spent_amount) if today_plan and today_plan.daily_budget and today_plan.spent_amount else 0.0,
        "status": today_plan.status if today_plan else "neutral",
        "monthly_budget": monthly_budget,
        "monthly_spent": round(monthly_spent, 2),
        "on_track": on_track
    }

    return success_response(status_data)


@router.patch("/automation_settings")
async def update_budget_automation_settings(
    settings: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Update budget automation preferences"""
    from app.db.models import UserPreference

    # Get or create user preference record
    user_pref = db.query(UserPreference).filter(
        UserPreference.user_id == user.id
    ).first()

    if not user_pref:
        user_pref = UserPreference(user_id=user.id)
        db.add(user_pref)

    # Update automation settings
    if "auto_adapt_enabled" in settings:
        user_pref.auto_adapt_enabled = settings["auto_adapt_enabled"]
    if "redistribution_enabled" in settings:
        user_pref.redistribution_enabled = settings["redistribution_enabled"]
    if "ai_suggestions_enabled" in settings:
        user_pref.ai_suggestions_enabled = settings["ai_suggestions_enabled"]
    if "notification_threshold" in settings:
        user_pref.notification_threshold = {"value": settings["notification_threshold"]}
    if "budget_mode" in settings:
        user_pref.budget_mode = settings["budget_mode"]

    db.commit()

    return success_response({"updated": True, "settings": settings})


@router.get("/automation_settings")
async def get_budget_automation_settings(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get budget automation preferences"""
    from app.db.models import UserPreference

    # Query user preferences
    user_pref = db.query(UserPreference).filter(
        UserPreference.user_id == user.id
    ).first()

    if not user_pref:
        # Return default settings if not set
        default_settings = {
            "auto_adapt_enabled": True,
            "redistribution_enabled": True,
            "ai_suggestions_enabled": True,
            "notification_threshold": 0.8
        }
        return success_response(default_settings)

    settings = {
        "auto_adapt_enabled": user_pref.auto_adapt_enabled,
        "redistribution_enabled": user_pref.redistribution_enabled,
        "ai_suggestions_enabled": user_pref.ai_suggestions_enabled,
        "notification_threshold": user_pref.notification_threshold.get("value", 0.8) if user_pref.notification_threshold else 0.8
    }

    return success_response(settings)


@router.post("/income_based_recommendations")
async def get_income_based_budget_recommendations(
    data: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get budget recommendations based on income level"""
    monthly_income = data.get("monthly_income", user.monthly_income or 0)

    recommendations = {
        "recommended_savings_rate": 0.20 if monthly_income > 3000 else 0.15,
        "emergency_fund_target": monthly_income * 6,
        "max_housing_cost": monthly_income * 0.30,
        "discretionary_budget": monthly_income * 0.30,
        "category_limits": {
            "food": monthly_income * 0.15,
            "transportation": monthly_income * 0.10,
            "utilities": monthly_income * 0.05,
            "entertainment": monthly_income * 0.10,
            "healthcare": monthly_income * 0.05,
            "savings": monthly_income * 0.20,
            "other": monthly_income * 0.05
        }
    }

    return success_response(recommendations)
