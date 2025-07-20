from datetime import datetime
from decimal import Decimal

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.db.models import Transaction, User
from app.services.core.engine.expense_tracker import apply_transaction_to_plan
from app.utils.timezone_utils import from_user_timezone, to_user_timezone


def add_transaction(user: User, data, db: Session):
    if data.amount <= 0:
        raise ValueError("invalid amount")
    txn = Transaction(
        user_id=user.id,
        category=data.category,
        amount=Decimal(str(data.amount)),
        currency="USD",
        spent_at=from_user_timezone(data.spent_at, user.timezone),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    apply_transaction_to_plan(db, txn)
    txn.spent_at = to_user_timezone(txn.spent_at, user.timezone)
    return txn


def add_transaction_background(
    user: User, data, db: Session, background_tasks: BackgroundTasks
) -> Transaction:
    """Create a transaction and update the plan in a background task."""
    txn = Transaction(
        user_id=user.id,
        category=data.category,
        amount=Decimal(str(data.amount)),
        currency="USD",
        spent_at=from_user_timezone(data.spent_at, user.timezone),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    background_tasks.add_task(apply_transaction_to_plan, db, txn)
    txn.spent_at = to_user_timezone(txn.spent_at, user.timezone)
    return txn


def list_user_transactions(
    user: User,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    category: str | None = None,
):
    query = db.query(Transaction).filter(Transaction.user_id == user.id)
    if category:
        query = query.filter(Transaction.category == category)
    if start_date:
        query = query.filter(
            Transaction.spent_at >= from_user_timezone(start_date, user.timezone)
        )
    if end_date:
        query = query.filter(
            Transaction.spent_at <= from_user_timezone(end_date, user.timezone)
        )
    txns = query.order_by(Transaction.spent_at.desc()).offset(skip).limit(limit).all()
    for t in txns:
        t.spent_at = to_user_timezone(t.spent_at, user.timezone)
    return txns
