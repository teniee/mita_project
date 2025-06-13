from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import Transaction
from app.schemas.core_outputs import TransactionOut
from app.services.core.engine.expense_tracker import apply_transaction_to_plan
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TxnIn(BaseModel):
    category: str
    amount: float
    currency: str = "USD"
    spent_at: datetime = datetime.utcnow()


@router.post("/")
def add_txn(
    txn: TxnIn,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    t = Transaction(
        user_id=user.id,
        category=txn.category,
        amount=Decimal(str(txn.amount)),
        currency=txn.currency,
        spent_at=txn.spent_at,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    apply_transaction_to_plan(db, t)
    return success_response({"id": str(t.id)})


@router.get("/", response_model=List[TransactionOut])
def list_transactions(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    txns = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    return [
        {
            "id": str(t.id),
            "category": t.category,
            "amount": float(t.amount),
            "currency": t.currency,
            "spent_at": t.spent_at,
        }
        for t in txns
    ]
