"""
Savings Surplus Rollover Service
Carries unspent savings budget from one month to the next month's goal.
This preserves the meaning of the app: savings are sacred and accumulate.
"""
from typing import Optional, Dict
from uuid import UUID
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import DailyPlan, Goal
from app.core.category_priority import CATEGORY_PRIORITY, CategoryLevel
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Categories considered "savings" for surplus rollover
SAVINGS_CATEGORIES = {
    cat for cat, level in CATEGORY_PRIORITY.items()
    if level == CategoryLevel.SACRED and "savings" in cat
}
# Fallback if registry doesn't have savings categories
SAVINGS_CATEGORIES.update({"savings_goal", "savings_emergency"})


def calculate_savings_surplus(
    db: Session,
    user_id: UUID,
    year: int,
    month: int,
) -> Decimal:
    """
    Calculate total unspent savings budget for a completed month.
    Returns the surplus amount (planned - spent) across all savings categories.
    """
    start = date(year, month, 1)
    end = date(year + (month // 12), (month % 12) + 1, 1)

    entries = (
        db.query(DailyPlan)
        .filter(DailyPlan.user_id == user_id)
        .filter(DailyPlan.date >= start)
        .filter(DailyPlan.date < end)
        .filter(DailyPlan.category.in_(list(SAVINGS_CATEGORIES)))
        .all()
    )

    total_surplus = Decimal("0")
    for entry in entries:
        delta = Decimal(str(entry.planned_amount)) - Decimal(str(entry.spent_amount))
        if delta > 0:
            total_surplus += delta

    return total_surplus


def apply_surplus_to_goal(
    db: Session,
    user_id: UUID,
    surplus: Decimal,
) -> Optional[Dict]:
    """
    Add the surplus to the user's highest-priority active goal.
    Returns a dict with what was applied, or None if no active goal.
    """
    if surplus <= 0:
        return None

    goal = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.status == "active")
        .order_by(Goal.priority)
        .first()
    )

    if not goal:
        logger.info(f"No active goal found for user {user_id}, surplus {surplus:.2f} not applied")
        return None

    try:
        goal.add_savings(surplus)
        db.commit()
        db.refresh(goal)
        logger.info(f"Applied ${surplus:.2f} surplus to goal [{goal.title}] for user {user_id}")
        return {
            "goal_id": str(goal.id),
            "goal_title": goal.title,
            "surplus_applied": float(surplus),
            "new_saved_amount": float(goal.saved_amount),
            "new_progress": float(goal.progress),
        }
    except Exception as e:
        logger.error(f"Error applying surplus to goal: {e}")
        db.rollback()
        return None


def rollover_month_savings(
    db: Session,
    user_id: UUID,
    completed_year: int,
    completed_month: int,
) -> Dict:
    """
    Main entry point: calculate surplus for completed month and apply to goal.
    Call this at end of month (from cron or month-boundary logic).
    """
    surplus = calculate_savings_surplus(db, user_id, completed_year, completed_month)
    result = apply_surplus_to_goal(db, user_id, surplus)

    return {
        "user_id": str(user_id),
        "completed_month": f"{completed_year}-{completed_month:02d}",
        "surplus_calculated": float(surplus),
        "applied_to_goal": result,
    }
