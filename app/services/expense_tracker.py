from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Transaction
from app.services.core.engine.expense_tracker import (
    apply_transaction_to_plan,
    local_day_start_utc,
    lock_user_ledger,
    run_transaction_plan_side_effects,
    user_timezone_of,
)


def record_expense(
    db: Session,
    user_id,
    day: date,
    category: str,
    amount: float,
    description: str = "",
):
    # 1. Save into the transactions table.
    # Transaction has no `date` column — the temporal column is spent_at.
    # Decimal(str(...)) avoids importing binary-float error into money.
    lock_user_ledger(db, user_id)
    user_timezone = user_timezone_of(db, user_id)
    txn = Transaction(
        user_id=user_id,
        spent_at=local_day_start_utc(day, user_timezone),
        category=category,
        amount=Decimal(str(amount)),
        description=description,
    )
    db.add(txn)
    db.flush()
    rebalance_result = apply_transaction_to_plan(
        db,
        txn,
        commit=False,
        run_side_effects=False,
    )
    db.commit()
    db.refresh(txn)
    run_transaction_plan_side_effects(db, txn, rebalance_result)

    return {
        "status": "recorded",
        "date": day.isoformat(),
        "category": category,
        "amount": float(amount),
    }
