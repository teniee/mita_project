import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import DailyPlan

logger = logging.getLogger(__name__)


def save_calendar_for_user(
    db: Session, user_id: UUID, calendar: Union[Dict[str, Dict[str, float]], List[Dict]]
):
    """
    Save calendar data to DailyPlan table.

    Accepts two formats:
    1. Dict format: {"2025-01-01": {"food": 50, "transport": 20}, ...}
    2. List format: [{"date": "2025-01-01", "planned_budget": {"food": 50, ...}}, ...]

    CRITICAL FIX: Now includes explicit UUID generation and comprehensive error handling
    to prevent silent failures during calendar save.
    """
    try:
        # Handle list format (returned by build_monthly_budget)
        if isinstance(calendar, list):
            calendar_dict = {}
            for day_entry in calendar:
                date_str = day_entry.get("date")
                planned_budget = day_entry.get("planned_budget", {})
                if date_str and planned_budget:
                    calendar_dict[date_str] = planned_budget
            calendar = calendar_dict

        if not calendar:
            logger.warning(f"Empty calendar data for user {user_id}")
            return

        entries_created = 0

        # Now process as dict format
        for day_str, categories in calendar.items():
            day_date = date.fromisoformat(day_str)
            for category, amount in categories.items():
                # CRITICAL FIX: Explicit UUID generation to ensure id is never null
                db_plan = DailyPlan(
                    id=uuid.uuid4(),  # Explicit UUID - defensive programming
                    user_id=user_id,
                    date=day_date,
                    category=category,
                    planned_amount=Decimal(amount),
                    spent_amount=Decimal("0.00"),
                )
                db.add(db_plan)
                entries_created += 1

        db.commit()

        # Verify save succeeded
        saved_count = db.query(DailyPlan).filter_by(user_id=user_id).count()
        logger.info(
            f"Calendar saved successfully for user {user_id}: "
            f"{entries_created} entries created, {saved_count} total in DB"
        )

        if saved_count == 0:
            raise ValueError(
                f"Calendar save verification failed: 0 entries found after commit for user {user_id}"
            )

    except Exception as e:
        logger.error(f"Calendar save failed for user {user_id}: {e}", exc_info=True)
        db.rollback()
        raise


def fetch_calendar(
    db: Session, user_id: UUID, year: int, month: int
) -> Dict[str, Dict[str, float]]:
    results = (
        db.query(DailyPlan)
        .filter(DailyPlan.user_id == user_id)
        .filter(DailyPlan.date >= date(year, month, 1))
        .filter(DailyPlan.date < date(year + (month // 12), ((month % 12) + 1), 1))
        .all()
    )

    calendar = {}
    for plan in results:
        key = plan.date.isoformat()
        if key not in calendar:
            calendar[key] = {}
        calendar[key][plan.category] = float(plan.planned_amount)
    return calendar


def update_day_entry(db: Session, user_id: UUID, day: date, updates: Dict[str, Any]):
    for category, new_amount in updates.items():
        plan = (
            db.query(DailyPlan)
            .filter_by(user_id=user_id, date=day, category=category)
            .first()
        )
        if plan:
            plan.planned_amount = Decimal(new_amount)
        else:
            db.add(
                DailyPlan(
                    user_id=user_id,
                    date=day,
                    category=category,
                    planned_amount=Decimal(new_amount),
                    spent_amount=Decimal("0.00"),
                )
            )
    db.commit()


def get_calendar_for_user(user_id: UUID, year: int, month: int) -> Dict[str, Dict[str, float]]:
    """
    Wrapper function for backward compatibility.
    Creates its own database session to fetch calendar data.

    NOTE: This function is kept for compatibility with legacy code that doesn't pass db session.
    New code should use fetch_calendar() directly with proper dependency injection.
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        return fetch_calendar(db, user_id, year, month)
    finally:
        db.close()
