from datetime import date
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import DailyPlan


def save_calendar_for_user(
    db: Session, user_id: UUID, calendar: Dict[str, Dict[str, float]]
):
    for day_str, categories in calendar.items():
        day_date = date.fromisoformat(day_str)
        for category, amount in categories.items():
            db_plan = DailyPlan(
                user_id=user_id,
                date=day_date,
                category=category,
                planned_amount=Decimal(amount),
                spent_amount=Decimal("0.00"),
            )
            db.add(db_plan)
    db.commit()


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
