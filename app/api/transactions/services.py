
from app.db.models import Transaction
from sqlalchemy.orm import Session
from decimal import Decimal

def add_transaction(user_id: str, data, db: Session):
    txn = Transaction(
        user_id=user_id,
        category=data.category,
        amount=Decimal(str(data.amount)),
        currency=data.currency,
        spent_at=data.spent_at
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn

def list_user_transactions(user_id: str, db: Session):
    return db.query(Transaction).filter(Transaction.user_id == user_id).all()
