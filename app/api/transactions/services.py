from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

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

    # MODULE 5: Parse goal_id if provided
    goal_id = None
    if hasattr(data, 'goal_id') and data.goal_id:
        try:
            from uuid import UUID as parse_uuid
            goal_id = parse_uuid(data.goal_id)
        except (ValueError, AttributeError):
            pass  # Invalid UUID, ignore

    txn = Transaction(
        user_id=user.id,
        category=data.category,
        amount=amount,
        currency=getattr(data, 'currency', 'USD'),
        description=getattr(data, 'description', None),
        merchant=getattr(data, 'merchant', None),
        location=getattr(data, 'location', None),
        tags=getattr(data, 'tags', None),
        is_recurring=getattr(data, 'is_recurring', False),
        confidence_score=getattr(data, 'confidence_score', None),
        receipt_url=getattr(data, 'receipt_url', None),
        notes=getattr(data, 'notes', None),
        spent_at=from_user_timezone(data.spent_at, user.timezone),
        goal_id=goal_id,  # Link to goal
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

    # MODULE 5: Update goal progress if linked
    if goal_id:
        try:
            from app.services.goal_transaction_service import GoalTransactionService
            GoalTransactionService.process_transaction_for_goal(db, txn, goal_id)
        except Exception as e:
            from app.core.logging_config import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Failed to update goal progress: {e}")

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
        currency=getattr(data, 'currency', 'USD'),
        description=getattr(data, 'description', None),
        merchant=getattr(data, 'merchant', None),
        location=getattr(data, 'location', None),
        tags=getattr(data, 'tags', None),
        is_recurring=getattr(data, 'is_recurring', False),
        confidence_score=getattr(data, 'confidence_score', None),
        receipt_url=getattr(data, 'receipt_url', None),
        notes=getattr(data, 'notes', None),
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
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    category: Optional[str] = None,
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


def get_transaction_by_id(user: User, transaction_id: UUID, db: Session) -> Optional[Transaction]:
    """Get a specific transaction by ID for the user"""
    txn = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user.id
    ).first()

    if txn:
        txn.spent_at = to_user_timezone(txn.spent_at, user.timezone)

    return txn


def update_transaction(user: User, transaction_id: UUID, data, db: Session) -> Optional[Transaction]:
    """Update an existing transaction"""
    txn = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user.id
    ).first()

    if not txn:
        return None

    # Update fields that are provided
    if hasattr(data, 'amount') and data.amount is not None:
        amount = data.amount if isinstance(data.amount, Decimal) else Decimal(str(data.amount))
        if amount <= 0:
            raise ValueError("Transaction amount must be positive")
        if amount > Decimal('1000000'):
            raise ValueError("Transaction amount exceeds maximum limit")
        txn.amount = amount

    if hasattr(data, 'category') and data.category is not None:
        txn.category = data.category

    if hasattr(data, 'description') and data.description is not None:
        txn.description = data.description

    if hasattr(data, 'currency') and data.currency is not None:
        txn.currency = data.currency

    if hasattr(data, 'merchant') and data.merchant is not None:
        txn.merchant = data.merchant

    if hasattr(data, 'location') and data.location is not None:
        txn.location = data.location

    if hasattr(data, 'tags') and data.tags is not None:
        txn.tags = data.tags

    if hasattr(data, 'is_recurring') and data.is_recurring is not None:
        txn.is_recurring = data.is_recurring

    if hasattr(data, 'spent_at') and data.spent_at is not None:
        txn.spent_at = from_user_timezone(data.spent_at, user.timezone)

    if hasattr(data, 'notes') and data.notes is not None:
        txn.notes = data.notes

    db.commit()
    db.refresh(txn)

    # Re-apply transaction to budget plan
    try:
        apply_transaction_to_plan(db, txn)
    except Exception as e:
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to update budget plan: {e}")

    txn.spent_at = to_user_timezone(txn.spent_at, user.timezone)
    return txn


def delete_transaction(user: User, transaction_id: UUID, db: Session) -> bool:
    """Delete a transaction"""
    txn = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user.id
    ).first()

    if not txn:
        return False

    db.delete(txn)
    db.commit()

    return True
