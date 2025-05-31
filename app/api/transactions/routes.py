
from fastapi import APIRouter, Depends
from app.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.api.transactions.schemas import TxnIn, TxnOut
from app.api.transactions.services import add_transaction, list_user_transactions
from app.core.session import get_db
from app.api.dependencies import get_current_user
from app.utils.response_wrapper import success_response
from typing import List

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.post("/", response_model=TxnOut)
async def create_transaction(txn: TxnIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(add_transaction(user.id, txn, db))

@router.get("/", response_model=List[TxnOut])
async def get_transactions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(list_user_transactions(user.id, db))