from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import DailyPlan, Transaction
from app.services.core.engine.calendar_updater import update_day_status


def apply_transaction_to_plan(db: Session, txn: Transaction) -> None:
    """Apply an already saved transaction to the DailyPlan table."""
    txn_day = txn.spent_at.date()

    plan = (
        db.query(DailyPlan)
        .filter_by(user_id=txn.user_id, date=txn_day, category=txn.category)
        .first()
    )
    if plan:
        plan.spent_amount += txn.amount
    else:
        new_plan = DailyPlan(
            user_id=txn.user_id,
            date=txn_day,
            category=txn.category,
            planned_amount=Decimal("0.00"),
            spent_amount=txn.amount,
        )
        db.add(new_plan)

    db.commit()
    update_day_status(db, txn.user_id, txn_day)


def record_expense(
    db: Session,
    user_id: UUID,
    day: date,
    category: str,
    amount: float,
    description: str = "",
):
    txn = Transaction(
        user_id=user_id,
        date=day,
        category=category,
        amount=Decimal(amount),
        description=description,
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
            spent_amount=Decimal(amount),
        )
        db.add(new_plan)

    db.commit()

    update_day_status(db, user_id, day)

    return {
        "status": "recorded",
        "date": day.isoformat(),
        "category": category,
        "amount": float(amount),
    }
