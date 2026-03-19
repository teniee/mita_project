from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.date_utils import day_to_range
from app.db.models import DailyPlan, Transaction


def record_expense(
    db: Session,
    user_id: int,
    day: date,
    category: str,
    amount: float,
    description: str = "",
):
    # 1. Save into the transactions table
    txn = Transaction(
        user_id=user_id,
        date=day,
        category=category,
        amount=Decimal(amount),
        description=description,
    )
    db.add(txn)

    # 2. Update the daily calendar plan
    day_start, day_end = day_to_range(day)
    plan = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= day_start,
            DailyPlan.date <= day_end,
            DailyPlan.category == category,
        )
        .first()
    )
    if plan:
        plan.spent_amount += Decimal(amount)
    else:
        # Create plan row if category is missing
        new_plan = DailyPlan(
            user_id=user_id,
            date=day,
            category=category,
            planned_amount=Decimal("0.00"),
            spent_amount=Decimal(amount),
        )
        db.add(new_plan)

    db.commit()
    return {
        "status": "recorded",
        "date": day.isoformat(),
        "category": category,
        "amount": float(amount),
    }
