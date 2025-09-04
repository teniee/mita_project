from datetime import datetime
from decimal import Decimal

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.db.models import Transaction, User
from app.services.core.engine.expense_tracker import apply_transaction_to_plan
from app.utils.timezone_utils import from_user_timezone, to_user_timezone


def add_transaction(user: User, data, db: Session):
    # Ensure amount is a proper Decimal for financial accuracy
    amount = data.amount if isinstance(data.amount, Decimal) else Decimal(str(data.amount))
    
    # Validate amount is positive and reasonable
    if amount <= 0:
        raise ValueError("Transaction amount must be positive")
    if amount > Decimal('1000000'):  # 1 million limit
        raise ValueError("Transaction amount exceeds maximum limit")
    
    txn = Transaction(
        user_id=user.id,
        category=data.category,
        amount=amount,
        currency="USD",
        description=getattr(data, 'description', None),
        spent_at=from_user_timezone(data.spent_at, user.timezone),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    
    # Apply transaction to budget plan
    try:
        apply_transaction_to_plan(db, txn)
    except Exception as e:
        # Log error but don't fail the transaction
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to update budget plan: {e}")
    
    txn.spent_at = to_user_timezone(txn.spent_at, user.timezone)
    return txn


def add_transaction_background(
    user: User, data, db: Session, background_tasks: BackgroundTasks
) -> Transaction:
    """Create a transaction and update the plan in a background task."""
    # Ensure amount is a proper Decimal for financial accuracy
    amount = data.amount if isinstance(data.amount, Decimal) else Decimal(str(data.amount))
    
    # Validate amount is positive and reasonable
    if amount <= 0:
        raise ValueError("Transaction amount must be positive")
    if amount > Decimal('1000000'):  # 1 million limit
        raise ValueError("Transaction amount exceeds maximum limit")
    
    txn = Transaction(
        user_id=user.id,
        category=data.category,
        amount=amount,
        currency="USD",
        description=getattr(data, 'description', None),
        spent_at=from_user_timezone(data.spent_at, user.timezone),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    
    # Apply budget plan update in background
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
