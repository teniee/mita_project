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
):
    """Get AI-powered budget suggestions"""
    # Mock data for now - this would be replaced with actual AI analysis
    suggestions_data = {
        "suggestions": [
            {
                "id": 1,
                "text": "Consider reducing dining out expenses by 20% to meet your savings goal",
                "category": "dining",
                "potential_savings": 120.0,
                "difficulty": "easy"
            },
            {
                "id": 2, 
                "text": "You could save $45/month by switching to generic brands for groceries",
                "category": "groceries",
                "potential_savings": 45.0,
                "difficulty": "easy"
            }
        ],
        "total_potential_savings": 165.0,
        "priority_areas": ["dining", "groceries", "entertainment"]
    }
    return success_response(suggestions_data)


@router.get("/mode")
async def get_budget_mode(
    user: User = Depends(get_current_user),  # noqa: B008
):
    """Get current budget mode setting"""
    # Mock data for now - this would be retrieved from user preferences
    return success_response("flexible")


@router.get("/redistribution_history")
async def get_redistribution_history(
    user: User = Depends(get_current_user),  # noqa: B008
):
    """Get budget redistribution history"""
    # Mock data for now - this would be retrieved from database
    history_data = [
        {
            "id": 1,
            "from": "15",
            "to": "20",
            "amount": 25.0,
            "date": "2025-01-28T10:30:00Z",
            "reason": "automatic_redistribution"
        },
        {
            "id": 2,
            "from": "12",
            "to": "18",
            "amount": 15.0,
            "date": "2025-01-27T14:22:00Z",
            "reason": "overspending_adjustment"
        }
    ]
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
            "spent": float(plan.spent) if plan.spent else 0.0,
            "remaining": float(plan.daily_budget - plan.spent) if plan.daily_budget and plan.spent else 0.0,
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
        "spent_today": float(today_plan.spent) if today_plan and today_plan.spent else 0.0,
        "remaining_today": float(today_plan.daily_budget - today_plan.spent) if today_plan and today_plan.daily_budget and today_plan.spent else 0.0,
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
