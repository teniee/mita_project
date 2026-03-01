from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.core.error_handler import (
    ValidationException, BusinessLogicException, InputValidator,
    handle_database_errors
)
from app.schemas.expense import ExpenseEntry, ExpenseHistoryOut, ExpenseOut
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/expense", tags=["expense"])


@router.post("/add", response_model=ExpenseOut)
@handle_database_errors
def add_expense(
    entry: ExpenseEntry, 
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new expense with comprehensive validation"""
    
    # Validate and sanitize input data
    expense_data = InputValidator.validate_expense_data(entry.dict())
    expense_data["user_id"] = user.id
    
    # Business logic validation
    if expense_data['amount'] > 10000:  # High amount threshold
        raise BusinessLogicException(
            "Expense amount unusually high. Please verify the amount.",
            details={"amount": expense_data['amount'], "threshold": 10000}
        )
    
    # Check user's daily spending limit (optional business rule)
    from datetime import datetime, date
    date.today()
    # This could query user's daily expenses and check against limits
    
    # Note: expense_service expects AsyncSession but we have sync Session
    # Use Transaction model instead for now (more complete implementation)
    from app.db.models import Transaction

    # Create transaction record (expense tracking via Transaction model)
    transaction = Transaction(
        user_id=user.id,
        amount=expense_data['amount'],
        category=expense_data.get('action', 'expense'),
        description=f"Expense: {expense_data.get('action', 'general')}",
        spent_at=datetime.utcnow()
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    result = {
        "id": str(transaction.id),
        "user_id": str(user.id),
        "amount": float(transaction.amount) if transaction.amount else 0.0,
        "action": transaction.category,
        "date": transaction.spent_at.date().isoformat()
    }
    return success_response(result)


@router.post("/history", response_model=ExpenseHistoryOut)
def get_history(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's expense history with security validation"""
    
    # Validate user access (already handled by get_current_user, but explicit check)
    if not user or not user.id:
        raise ValidationException("Invalid user session")

    # Query transactions (expenses) from database
    from app.db.models import Transaction
    from datetime import datetime, timedelta

    # Get last 90 days of expenses
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.spent_at >= ninety_days_ago
    ).order_by(Transaction.spent_at.desc()).all()

    result = {
        "expenses": [
            {
                "id": str(t.id),
                "user_id": str(user.id),
                "amount": float(t.amount) if t.amount else 0.0,
                "action": t.category or "expense",
                "date": t.spent_at.date().isoformat()
            }
            for t in transactions
        ],
        "total_count": len(transactions),
        "period_days": 90
    }
    return success_response(result)
