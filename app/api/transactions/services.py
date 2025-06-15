from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Transaction
from app.services.core.engine.expense_tracker import apply_transaction_to_plan
from fastapi import BackgroundTasks


def add_transaction(user_id: str, data, db: Session):
    txn = Transaction(
        user_id=user_id,
        category=data.category,
        amount=Decimal(str(data.amount)),
        currency=data.currency,
        spent_at=data.spent_at,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    apply_transaction_to_plan(db, txn)
    return txn


def add_transaction_background(
    user_id: str, data, db: Session, background_tasks: BackgroundTasks
) -> Transaction:
    """Create a transaction and update the plan in a background task."""
    txn = Transaction(
        user_id=user_id,
        category=data.category,
        amount=Decimal(str(data.amount)),
        currency=data.currency,
        spent_at=data.spent_at,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    background_tasks.add_task(apply_transaction_to_plan, db, txn)
    return txn


def list_user_transactions(user_id: str, db: Session):
    return db.query(Transaction).filter(Transaction.user_id == user_id).all()
