from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date

from app.core.db import get_db
from app.db.models.user import User
from app.services.auth_dependency import get_current_user
from app.services.validation import validate_category, validate_amount
from app.services.expense_tracker import record_expense

router = APIRouter(prefix="/transactions", tags=["transactions"])

class TransactionIn(BaseModel):
    date: date
    category: str
    amount: float
    description: str = ""

@router.post("/")
def add_transaction(
    txn: TransactionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    validate_category(txn.category)
    validate_amount(txn.amount)
    result = record_expense(
        db=db,
        user_id=user.id,
        day=txn.date,
        category=txn.category,
        amount=txn.amount,
        description=txn.description
    )
    return result
