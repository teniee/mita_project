
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal
from app.db.models import Transaction, DailyPlan
from app.services.core.engine.calendar_updater import update_day_status

def record_expense(db: Session, user_id: int, day: date, category: str, amount: float, description: str = ""):
    txn = Transaction(
        user_id=user_id,
        date=day,
        category=category,
        amount=Decimal(amount),
        description=description
    )
    db.add(txn)

    plan = (
        db.query(DailyPlan)
        .filter_by(user_id=user_id, date=day, category=category)
        .first()
    )
    if plan:
        plan.spent_amount += Decimal(amount)
    else:
        new_plan = DailyPlan(
            user_id=user_id,
            date=day,
            category=category,
            planned_amount=Decimal("0.00"),
            spent_amount=Decimal(amount)
        )
        db.add(new_plan)

    db.commit()

    update_day_status(db, user_id, day)

    return {
        "status": "recorded",
        "date": day.isoformat(),
        "category": category,
        "amount": float(amount)
    }
