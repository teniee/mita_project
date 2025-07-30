from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.core.error_handler import (
    ValidationException, BusinessLogicException, InputValidator,
    validate_user_access, handle_database_errors
)
from app.schemas.expense import ExpenseEntry, ExpenseHistoryOut, ExpenseOut
from app.services.expense_service import add_user_expense  # noqa: E501
from app.services.expense_service import get_user_expense_history
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/expense", tags=["expense"])


@router.post("/add", response_model=ExpenseOut)
@handle_database_errors
async def add_expense(
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
    today = date.today()
    # This could query user's daily expenses and check against limits
    
    result = add_user_expense(expense_data)
    return success_response(result)


@router.post("/history", response_model=ExpenseHistoryOut)
async def get_history(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's expense history with security validation"""
    
    # Validate user access (already handled by get_current_user, but explicit check)
    if not user or not user.id:
        raise ValidationException("Invalid user session")
    
    result = get_user_expense_history(user.id)
    return success_response(result)
